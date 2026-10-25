"""Filtered build records and bounded delivery, separate from release evidence."""

import base64
import binascii
from collections import deque
import os
from pathlib import Path
import re
import struct
import subprocess
import sys
import time
from urllib.parse import quote, quote_plus, unquote, urlsplit

from release_io import Refusal, require, stop_process


RECORD_LIMIT = 65536
DISPLAY_LIMIT = 128 * 1024
PENDING_LIMIT = 256 * 1024
DELIVERY_SECONDS = 5
OMITTED = b"[build log record omitted]\n"
ESCAPES = re.compile(r"\x1b(?:\[[0-?]*[ -/]*[@-~]|\][^\x07\x1b]*(?:\x07|\x1b\\)|[@-_])")
CONTROLS = re.compile(r"[\x00-\x1f\x7f-\x9f]")
CREDENTIAL = re.compile(r"(?i)(?<![\w-])(?:authorization\s*:|[\"']?(?:password|passwd|token|secret|auth|identitytoken|registrytoken)[\"']?\s*[:=])")
URL = re.compile(r"(?i)\b[a-z][a-z0-9+.-]*://[^\s<>\"']+")


def credential_values(config):
  """Extract only supported credentials already present in the effective config."""
  message = "Invalid Docker credentials for build log filtering"
  auths = config.get("auths", {})
  require(isinstance(auths, dict), message)
  values = []
  for registry, fields in auths.items():
    require(isinstance(registry, str) and isinstance(fields, dict), message)
    for key in ("auth", "username", "password", "identitytoken", "registrytoken"):
      if key in fields:
        require(isinstance(fields[key], str) and not CONTROLS.search(fields[key]), message)
        values.append(fields[key])
    encoded = fields.get("auth", "")
    if encoded:
      try:
        pair = base64.b64decode(encoded, validate=True).decode("utf-8")
      except (ValueError, UnicodeError, binascii.Error):
        raise Refusal(message) from None
      require(":" in pair and not CONTROLS.search(pair), message)
      values.extend((pair, pair.split(":", 1)[1]))
  return values


def proxy_values(proxies):
  values = []
  for endpoint, fields in (proxies or {}).items():
    values.append(endpoint)
    for value in fields.values():
      values.append(value)
      try:
        parsed = urlsplit(value)
        for item in (parsed.username, parsed.password):
          if item:
            values.extend((item, unquote(item)))
      except ValueError:
        # Arbitrary literal proxy values are supported; the entire value is hidden.
        pass
  return values


class RecordFilter:
  def __init__(self, values, emit):
    require(all(isinstance(value, str) and not CONTROLS.search(value) for value in values),
            "Invalid build log redaction value")
    self.values = sorted({variant for value in values if value
                          for variant in (value, quote(value, safe=""), quote_plus(value))}, key=len, reverse=True)
    self.emit = emit
    self.buffers = {"stdout": bytearray(), "stderr": bytearray()}
    self.dropping = {"stdout": False, "stderr": False}

  def record(self, raw):
    text = CONTROLS.sub("", ESCAPES.sub("", raw.decode("utf-8", errors="replace")))
    for value in self.values:
      text = text.replace(value, "[redacted]")
    if CREDENTIAL.search(text):
      return b"[build credential record omitted]\n"
    text = URL.sub("[URL]", text)
    result = (text + "\n").encode("utf-8")
    return result if len(result) <= DISPLAY_LIMIT else OMITTED

  def feed(self, stream, chunk):
    # Records stay private until complete, including secrets split across reads.
    for part in re.split(b"([\r\n])", chunk):
      if part in (b"\r", b"\n"):
        self.eof(stream)
      elif not self.dropping[stream]:
        if len(self.buffers[stream]) + len(part) > RECORD_LIMIT:
          self.buffers[stream].clear()
          self.dropping[stream] = True
        else:
          self.buffers[stream].extend(part)

  def eof(self, stream):
    if self.dropping[stream]:
      self.emit(OMITTED)
    elif self.buffers[stream]:
      self.emit(self.record(bytes(self.buffers[stream])))
    self.buffers[stream].clear()
    self.dropping[stream] = False


class Delivery:
  """Only the owned helper can block on the caller's stderr destination."""
  def __init__(self, sink=None):
    self.sink = sink
    self.process = None
    self.queue = deque()
    self.pending_bytes = 0

  def start(self):
    self.process = subprocess.Popen([sys.executable, "-B", str(Path(__file__).resolve()), "--writer"],
                                    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self.sink,
                                    env={}, start_new_session=True)
    os.set_blocking(self.process.stdin.fileno(), False)
    os.set_blocking(self.process.stdout.fileno(), False)

  def enqueue(self, record):
    packet = struct.pack("!I", len(record)) + record
    require(self.pending_bytes + len(packet) <= PENDING_LIMIT, "Build log delivery queue exceeded")
    self.queue.append([packet, 0, time.monotonic()])
    self.pending_bytes += len(packet)

  def tick(self):
    require(self.process.poll() is None, "Build log writer failed")
    try:
      acknowledgments = os.read(self.process.stdout.fileno(), 4096)
    except BlockingIOError:
      acknowledgments = None
    require(acknowledgments != b"", "Build log writer disconnected")
    for acknowledgment in acknowledgments or b"":
      require(acknowledgment == 1 and self.queue and self.queue[0][1] == len(self.queue[0][0]),
              "Invalid build log delivery acknowledgment")
      self.pending_bytes -= len(self.queue.popleft()[0])
    if self.queue:
      require(time.monotonic() - self.queue[0][2] < DELIVERY_SECONDS, "Build log delivery timed out")
    for record in self.queue:
      packet, offset, _ = record
      if offset < len(packet):
        try:
          record[1] += os.write(self.process.stdin.fileno(), packet[offset:offset + 65536])
        except BlockingIOError:
          break
        except OSError:
          raise Refusal("Build log delivery failed") from None
        if record[1] < len(packet):
          break

  def close(self):
    if self.process is not None:
      try:
        stop_process(self.process)
      finally:
        self.process.stdin.close()
        self.process.stdout.close()


class BuildLogs:
  def __init__(self, values, sink=None):
    self.delivery = Delivery(sink)
    self.filter = RecordFilter(values, self.delivery.enqueue)

  def start(self):
    self.delivery.start()

  def feed(self, stream, chunk):
    self.filter.feed(stream, chunk)

  def eof(self, stream):
    self.filter.eof(stream)

  def tick(self):
    self.delivery.tick()

  def pending(self):
    return bool(self.delivery.queue)

  def close(self):
    self.delivery.close()


def writer():
  def receive(size):
    value = bytearray()
    while len(value) < size:
      chunk = os.read(0, size - len(value))
      if not chunk:
        raise EOFError
      value.extend(chunk)
    return bytes(value)
  while True:
    size = struct.unpack("!I", receive(4))[0]
    if not 0 < size <= DISPLAY_LIMIT:
      return 1
    record = memoryview(receive(size))
    while record:
      record = record[os.write(2, record):]
    os.write(1, b"\x01")


if __name__ == "__main__":
  try:
    sys.exit(writer() if sys.argv[1:] == ["--writer"] else 1)
  except EOFError:
    sys.exit(0)
  except (OSError, ValueError, struct.error):
    sys.exit(1)
