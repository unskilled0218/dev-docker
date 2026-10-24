"""Bounded process and HTTPS boundaries, adapted from release-template 0.4.0."""

import fcntl
import hashlib
import json
import os
from pathlib import Path
import selectors
import signal
import subprocess
import time
from urllib.parse import quote, urlencode, urlsplit


API_LIMIT = 4 * 1024 * 1024
CONFIG_LIMIT = 1024 * 1024
SMALL_LIMIT = 65536
REF_LIMIT = 16 * 1024 * 1024
INVENTORY_BUDGET = None


class Refusal(Exception):
  pass


class CommandFailed(Refusal):
  pass


def require(value, message):
  if not value:
    raise Refusal(message)


def canonical(value):
  return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def sha(value):
  return "sha256:" + hashlib.sha256(value).hexdigest()


def unique(pairs):
  result = {}
  for key, value in pairs:
    require(key not in result, "Duplicate JSON field")
    result[key] = value
  return result


def decode(value):
  return json.loads(value.decode("utf-8"), object_pairs_hook=unique,
                    parse_constant=lambda _: (_ for _ in ()).throw(Refusal("Invalid JSON number")))


def read(path, limit=API_LIMIT):
  with Path(path).open("rb") as source:
    value = source.read(limit + 1)
  require(len(value) <= limit, "Input exceeds byte limit")
  return value


def document(path, limit=API_LIMIT):
  return decode(read(path, limit))


def write(path, value):
  Path(path).write_bytes(canonical(value) + b"\n")


def capture(arguments, limit=REF_LIMIT, seconds=60, input_data=None, streams=None):
  """Drain every pipe concurrently and terminate the owned group on interruption."""
  pipes = {name: os.pipe() for name in (streams or {})}
  arguments = [str(arg) for arg in arguments]
  for name, (_, writer) in pipes.items():
    arguments = [arg.replace("{" + name + "}", f"/dev/fd/{writer}") for arg in arguments]
  selector = selectors.DefaultSelector()
  process = None
  try:
    environment = {key: value for key, value in os.environ.items() if key not in (
      "GIT_TOKEN", "GIT_USERNAME", "FORGEJO_TOKEN_FILE", "FORGEJO_USERNAME")}
    process = subprocess.Popen(arguments, stdin=subprocess.PIPE if input_data is not None else subprocess.DEVNULL,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=environment,
                               start_new_session=True, pass_fds=tuple(writer for _, writer in pipes.values()))
    for _, writer in pipes.values():
      os.close(writer)
    readers = {name: reader for name, (reader, _) in pipes.items()}
    readers |= {"stdout": process.stdout.fileno(), "stderr": process.stderr.fileno()}
    limits = (streams or {}) | {"stdout": limit, "stderr": CONFIG_LIMIT}
    buffers = {name: bytearray() for name in readers}
    for name, descriptor in readers.items():
      os.set_blocking(descriptor, False)
      selector.register(descriptor, selectors.EVENT_READ, name)
    pending = memoryview(input_data or b"")
    if input_data is not None:
      os.set_blocking(process.stdin.fileno(), False)
      selector.register(process.stdin.fileno(), selectors.EVENT_WRITE, "stdin")
    deadline = time.monotonic() + seconds
    while selector.get_map():
      require(time.monotonic() < deadline, "Command timed out; outcome may be uncertain")
      for key, _ in selector.select(min(0.1, max(0, deadline - time.monotonic()))):
        name = key.data
        if name == "stdin":
          if pending:
            try:
              pending = pending[os.write(key.fd, pending[:65536]):]
            except BrokenPipeError:
              pending = memoryview(b"")
          if not pending:
            selector.unregister(key.fd)
            process.stdin.close()
          continue
        chunk = os.read(key.fd, min(65536, limits[name] + 1 - len(buffers[name])))
        if not chunk:
          selector.unregister(key.fd)
          continue
        buffers[name].extend(chunk)
        require(len(buffers[name]) <= limits[name], "Command output exceeds byte limit")
    status = process.wait(timeout=max(0.001, deadline - time.monotonic()))
    return status, {name: bytes(value) for name, value in buffers.items()}
  finally:
    selector.close()
    if process is not None:
      try:
        os.killpg(process.pid, signal.SIGKILL)
      except ProcessLookupError:
        pass
      process.wait()
      for pipe in (process.stdout, process.stderr, process.stdin):
        if pipe is not None:
          pipe.close()
    for reader, _ in pipes.values():
      os.close(reader)
    if process is None:
      for _, writer in pipes.values():
        os.close(writer)


def command(arguments, limit=REF_LIMIT, seconds=60, input_data=None):
  status, output = capture(arguments, limit, seconds, input_data)
  if status:
    raise CommandFailed("Command failed: " + Path(arguments[0]).name)
  return output["stdout"]


def git(root, *arguments, limit=REF_LIMIT, input_data=None):
  return command(["git", "-C", str(root), *arguments], limit=limit, input_data=input_data)


def http(work, method, url, auth="api.curl", payload=None, limit=API_LIMIT, seconds=60):
  require(urlsplit(url).scheme == "https", "HTTPS is required")
  if INVENTORY_BUDGET is not None:
    seconds = min(seconds, INVENTORY_BUDGET["deadline"] - time.monotonic())
    require(seconds > 0, "Inventory time budget exceeded")
  arguments = ["curl", "-q", "--silent", "--show-error", "--proto", "=https", "--max-time", str(seconds),
               "--config", str(Path(work) / auth), "--request", method,
               "--header", "Accept: application/json, application/vnd.oci.image.index.v1+json, application/vnd.oci.image.manifest.v1+json, application/vnd.docker.distribution.manifest.list.v2+json, application/vnd.docker.distribution.manifest.v2+json",
               "--dump-header", "{headers}", "--output", "{body}", "--write-out", "%{http_code}"]
  if payload:
    arguments += ["--header", "Content-Type: application/json", "--data-binary", "@" + str(payload)]
  status, output = capture(arguments + [url], 16, seconds, streams={"body": limit, "headers": SMALL_LIMIT})
  if status:
    raise CommandFailed("HTTPS transport failed; outcome may be uncertain")
  if INVENTORY_BUDGET is not None:
    INVENTORY_BUDGET["bytes"] += len(output["body"])
    require(INVENTORY_BUDGET["bytes"] <= 64 * 1024 * 1024 and
            time.monotonic() < INVENTORY_BUDGET["deadline"], "Inventory byte/time budget exceeded")
  require(len(output["stdout"]) == 3 and output["stdout"].isdigit(), "Invalid HTTP status")
  code = int(output["stdout"])
  require(code in (200, 201, 401, 404), "Unexpected HTTP status")
  headers = {}
  for line in output["headers"].decode("iso-8859-1").splitlines():
    if line.startswith("HTTP/"):
      headers = {}
    elif ":" in line:
      key, value = line.split(":", 1)
      key = key.strip().lower()
      require(key not in headers or key not in ("docker-content-digest", "www-authenticate"), "Duplicate evidence header")
      headers[key] = value.strip()
  return code, headers, output["body"]


def registry(work, origin, image, kind, reference, missing=False):
  repository = image.split("/", 1)[1]
  route = "/v2/" + repository + "/" + kind + "/" + quote(reference, safe="")
  limit = API_LIMIT if kind == "manifests" else CONFIG_LIMIT
  status, headers, value = http(work, "GET", origin + route, "registry.curl", limit=limit)
  if status == 401:
    import re
    challenge = headers.get("www-authenticate", "")
    require(challenge.lower().startswith("bearer "), "Unsupported registry challenge")
    pairs = re.findall(r'([a-z]+)="([^"\r\n]*)"', challenge)
    require(len(dict(pairs)) == len(pairs), "Duplicate registry challenge field")
    fields = dict(pairs)
    realm, base = urlsplit(fields.get("realm", "")), urlsplit(origin)
    require((realm.scheme, realm.netloc) == (base.scheme, base.netloc) and not realm.username and
            not realm.password and not realm.fragment and realm.path.startswith("/") and
            not realm.path.startswith("//"), "Registry token realm must be same-origin")
    query = urlencode({"service": fields.get("service", ""), "scope": "repository:" + repository + ":pull"})
    url = origin + realm.path + "?" + (realm.query + "&" if realm.query else "") + query
    status, _, value = http(work, "GET", url, "registry.curl", limit=CONFIG_LIMIT)
    require(status == 200, "Registry authentication failed")
    token = decode(value)
    token = token.get("token", token.get("access_token")) if isinstance(token, dict) else None
    require(isinstance(token, str) and re.fullmatch(r"[A-Za-z0-9._~-]+", token), "Invalid registry token")
    (Path(work) / "bearer.curl").write_text('header = "Authorization: Bearer ' + token + '"\n')
    status, headers, value = http(work, "GET", origin + route, "bearer.curl", limit=limit)
  if status == 404 and missing:
    evidence = decode(value)
    errors = evidence.get("errors") if isinstance(evidence, dict) else None
    require(isinstance(errors, list) and errors and
            all(isinstance(error, dict) and error.get("code") in ("MANIFEST_UNKNOWN", "NAME_UNKNOWN") for error in errors),
            "Unrecognized registry absence evidence")
    return None
  require(status == 200, "Registry evidence unavailable")
  actual = sha(value)
  require(not reference.startswith("sha256:") or actual == reference, "Registry digest differs")
  require(headers.get("docker-content-digest", actual) == actual, "Registry digest header differs")
  return actual, decode(value)


def locked(root, arguments):
  descriptor = os.open(Path(root) / ".release-operation.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
  try:
    try:
      fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as exc:
      raise Refusal("Another operation holds this checkout's release lock") from exc
    # Only the launcher creates this descriptor. The script validates the inherited inode.
    child = subprocess.Popen(["bash", str(Path(root) / "build-all.sh"), *arguments],
                             env=os.environ | {"RELEASE_LOCK_FD": str(descriptor)},
                             pass_fds=(descriptor,), start_new_session=True)
    def forward(number, _frame):
      try:
        os.killpg(child.pid, number)
      except ProcessLookupError:
        pass
    signal.signal(signal.SIGINT, forward)
    signal.signal(signal.SIGTERM, forward)
    return child.wait()
  finally:
    os.close(descriptor)
