"""Offline record privacy, live delivery, and subprocess supervision contracts."""

import base64
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import termios
import threading
import time
import unittest
from unittest.mock import patch

from test_build_all import PROJECT, ReleaseFixture, data, ports
import release_logs as logs


class FilterTests(unittest.TestCase):
  def filtered(self, chunks, values=()):
    records = []
    filtering = logs.RecordFilter(values, records.append)
    for stream, chunk in chunks:
      filtering.feed(stream, chunk)
    for stream in ("stdout", "stderr"):
      filtering.eof(stream)
    return b"".join(records)

  def test_sensitive_values_split_at_every_byte_boundary(self):
    auth = base64.b64encode(b"other-user:other-password:with-colons").decode()
    config = {"auths": {"foreign": {"auth": auth, "password": "explicit-password",
                                  "identitytoken": "identity-value", "registrytoken": "registry-value"}}}
    values = ["release-token", "/private/token", *logs.credential_values(config),
              *logs.proxy_values({"default": {"httpsProxy": "https://proxy-user:proxy%2Dpassword@proxy.invalid"}})]
    markers = [auth, "other-password:with-colons", "other-user:other-password:with-colons",
               "explicit-password", "identity-value", "registry-value", "release-token", "/private/token",
               "proxy-password", "proxy%2Dpassword", "https://proxy-user:proxy%2Dpassword@proxy.invalid"]
    for marker in markers:
      raw = ("useful error " + marker + " finished\n").encode()
      for split in range(len(raw) + 1):
        with self.subTest(marker=marker, split=split):
          output = self.filtered([("stderr", raw[:split]), ("stderr", raw[split:])], values)
          self.assertNotIn(marker.encode(), output)
          self.assertIn(b"useful error", output)
          self.assertIn(b"finished", output)

  def test_structured_secrets_urls_and_terminal_controls(self):
    raw = (b"Authorization: Bearer unknown\nPASSWORD=unknown\n{\"identitytoken\":\"unknown\"}\n"
           b"fetch https://user:unknown@host/file?signed=unknown failed\n"
           b"normal\x1b[31m error\x1b[0m\x00 text\n")
    output = self.filtered([("stderr", raw)])
    self.assertNotIn(b"unknown", output)
    self.assertNotIn(b"\x1b", output)
    self.assertIn(b"fetch [URL] failed", output)
    self.assertIn(b"normal error text", output)

  def test_utf8_carriage_returns_independent_streams_and_final_record(self):
    chunks = [("stdout", b"caf\xc3"), ("stderr", b"error sec"), ("stdout", b"\xa9\rnext\n"),
              ("stderr", b"ret"), ("stdout", b"final")]
    output = self.filtered(chunks, ["secret"])
    self.assertIn("café\nnext\n".encode(), output)
    self.assertIn(b"error [redacted]\n", output)
    self.assertIn(b"final\n", output)

  def test_overlong_record_is_omitted_without_exposing_prefix(self):
    output = self.filtered([("stderr", b"private-prefix" + b"x" * logs.RECORD_LIMIT),
                            ("stderr", b"tail\nuseful next\n")])
    self.assertEqual(output, logs.OMITTED + b"useful next\n")

  def test_display_expansion_is_bounded(self):
    output = self.filtered([("stderr", b"x" * logs.RECORD_LIMIT + b"\n")], ["x"])
    self.assertEqual(output, logs.OMITTED)

  def test_empty_auth_forms_are_valid_and_bad_supported_fields_refuse(self):
    self.assertEqual(logs.credential_values({}), [])
    self.assertEqual([value for value in logs.credential_values({"auths": {"r": {"auth": "", "password": ""}}}) if value], [])
    invalid = [{"auths": []}, {"auths": {"r": None}}, {"auths": {"r": {"auth": "not-base64"}}},
               {"auths": {"r": {"auth": base64.b64encode(b"no-separator").decode()}}},
               {"auths": {"r": {"auth": base64.b64encode(b"u:\xff").decode()}}},
               {"auths": {"r": {"auth": base64.b64encode(b"u:split\npassword").decode()}}},
               {"auths": {"r": {"password": "split\rpassword"}}}]
    invalid += [{"auths": {"r": {key: 7}}} for key in ("auth", "username", "password", "identitytoken", "registrytoken")]
    for config in invalid:
      with self.subTest(config=config):
        self.assertRaisesRegex(ports.Refusal, "Invalid Docker credentials", logs.credential_values, config)


class StreamingTests(unittest.TestCase):
  def setUp(self):
    self.temporary = tempfile.TemporaryDirectory(dir="/tmp/opencode")
    self.addCleanup(self.temporary.cleanup)
    self.root = Path(self.temporary.name)

  def invoke(self, source, observer, **options):
    return ports.command([sys.executable, "-B", "-c", source], observer=observer, **options)

  def test_live_delivery_precedes_child_exit_and_capture_is_unchanged(self):
    read_fd, write_fd = os.pipe()
    marker = self.root / "continue"
    received = []
    def consume():
      with os.fdopen(read_fd, "rb", buffering=0) as reader:
        received.append(reader.readline())
        marker.touch()
        received.append(reader.read())
    thread = threading.Thread(target=consume)
    thread.start()
    observer = logs.BuildLogs(["secret"], sink=write_fd)
    source = ("import pathlib,time,sys; print('live secret',flush=True); "
              "p=pathlib.Path(" + repr(str(marker)) + "); deadline=time.monotonic()+3\n"
              "while not p.exists() and time.monotonic()<deadline: time.sleep(.01)\n"
              "assert p.exists(); sys.stderr.write('final error'); print('done',flush=True)")
    try:
      result = self.invoke(source, observer, seconds=5)
    finally:
      os.close(write_fd)
      thread.join(timeout=5)
    self.assertFalse(thread.is_alive())
    self.assertEqual(result, b"live secret\ndone\n")
    self.assertIn(b"live [redacted]\n", b"".join(received))
    self.assertIn(b"final error\n", b"".join(received))
    self.assertIsNotNone(observer.delivery.process.returncode)

  def test_nonzero_exit_shows_error_without_replaying_or_changing_exception(self):
    with tempfile.TemporaryFile() as sink:
      observer = logs.BuildLogs(["secret"], sink=sink)
      with self.assertRaisesRegex(ports.CommandFailed, "Command failed"):
        self.invoke("import sys; print('useful secret failure',file=sys.stderr); sys.exit(9)", observer)
      sink.seek(0)
      self.assertEqual(sink.read(), b"useful [redacted] failure\n")

  def test_short_record_burst_drains_before_delivery_deadline(self):
    with tempfile.TemporaryFile() as sink, patch.object(logs, "DELIVERY_SECONDS", 1):
      observer = logs.BuildLogs([], sink=sink)
      self.invoke("import os; os.write(2,b'useful step\\n'*200)", observer, seconds=3)
      sink.seek(0)
      self.assertEqual(sink.read(), b"useful step\n" * 200)
      self.assertFalse(observer.pending())

  def test_concurrent_streams_are_drained_and_bounded(self):
    source = "import os; os.write(1,b'a'*60000+b'\\n'); os.write(2,b'b'*60000+b'\\n')"
    with tempfile.TemporaryFile() as sink:
      result = self.invoke(source, logs.BuildLogs([], sink=sink))
      sink.seek(0)
      self.assertEqual(result, b"a" * 60000 + b"\n")
      self.assertIn(b"b" * 60000, sink.read())

  def test_overflow_chunk_is_not_sent_to_observer(self):
    class Observer:
      def start(self): pass
      def tick(self): pass
      def pending(self): return False
      def eof(self, stream): pass
      def feed(self, stream, chunk): raise AssertionError("overflow must stay private")
      def close(self): pass
    self.assertRaisesRegex(ports.Refusal, "exceeds byte limit", self.invoke,
                           "import os; os.write(1,b'x'*100)", Observer(), limit=10)

  def test_stalled_open_sink_refuses_and_reaps_writer_and_child(self):
    read_fd, write_fd = os.pipe()
    fcntl.fcntl(write_fd, fcntl.F_SETPIPE_SZ, 4096)
    pidfile = self.root / "child"
    source = ("import os,pathlib,time; pathlib.Path(" + repr(str(pidfile)) + ").write_text(str(os.getpid())); "
              "os.write(2,b'x'*60000+b'\\n'); time.sleep(30)")
    observer = logs.BuildLogs([], sink=write_fd)
    started = time.monotonic()
    try:
      with patch.object(logs, "DELIVERY_SECONDS", .3):
        with self.assertRaisesRegex(ports.Refusal, "delivery timed out") as caught:
          self.invoke(source, observer, seconds=3)
      self.assertNotIsInstance(caught.exception, ports.CommandFailed)
      self.assertLess(time.monotonic() - started, 3)
      self.assertLessEqual(observer.delivery.pending_bytes, logs.PENDING_LIMIT)
      self.assertIsNotNone(observer.delivery.process.returncode)
      self.assertRaises(ProcessLookupError, os.kill, int(pidfile.read_text()), 0)
    finally:
      os.close(read_fd)
      os.close(write_fd)

  def test_queue_exhaustion_is_bounded_refusal(self):
    delivery = logs.Delivery()
    delivery.enqueue(b"x" * logs.DISPLAY_LIMIT)
    self.assertRaisesRegex(ports.Refusal, "queue exceeded", delivery.enqueue, b"x" * logs.DISPLAY_LIMIT)
    self.assertLessEqual(delivery.pending_bytes, logs.PENDING_LIMIT)

  def test_broken_sink_and_failed_writer_refuse_without_raw_fallback(self):
    read_fd, write_fd = os.pipe()
    os.close(read_fd)
    observer = logs.BuildLogs(["secret"], sink=write_fd)
    try:
      with self.assertRaises(ports.Refusal) as caught:
        self.invoke("import sys; print('secret error',file=sys.stderr)", observer, seconds=3)
      self.assertNotIsInstance(caught.exception, ports.CommandFailed)
      self.assertNotIn("secret", str(caught.exception))
      self.assertIsNotNone(observer.delivery.process.returncode)
    finally:
      os.close(write_fd)

  def test_timeout_and_interruption_reap_owned_processes(self):
    with tempfile.TemporaryFile() as sink:
      observer = logs.BuildLogs([], sink=sink)
      self.assertRaisesRegex(ports.Refusal, "timed out", self.invoke, "import time; time.sleep(30)", observer, seconds=.1)
      self.assertIsNotNone(observer.delivery.process.returncode)
      observer = logs.BuildLogs([], sink=sink)
      with patch.object(observer, "tick", side_effect=ports.Refusal("Operation interrupted")):
        self.assertRaisesRegex(ports.Refusal, "interrupted", self.invoke, "import time; time.sleep(30)", observer)
      self.assertIsNotNone(observer.delivery.process.returncode)

  def test_slow_consumer_resumes_and_eof_waits_for_delivery(self):
    read_fd, write_fd = os.pipe()
    fcntl.fcntl(write_fd, fcntl.F_SETPIPE_SZ, 4096)
    observer = logs.BuildLogs([], sink=write_fd)
    received = []
    ready = threading.Event()
    def consume():
      # Delivery has queued a record and the helper is blocked on this small pipe.
      if not ready.wait(timeout=3):
        return
      with os.fdopen(read_fd, "rb", buffering=0) as reader:
        received.append(reader.read())
    original_tick = observer.tick
    def tick():
      original_tick()
      if observer.delivery.queue:
        ready.set()
    thread = threading.Thread(target=consume)
    thread.start()
    try:
      with patch.object(observer, "tick", side_effect=tick):
        self.invoke("import os; os.write(2,b'x'*60000+b'\\n')", observer, seconds=5)
      self.assertFalse(observer.pending())
    finally:
      ready.set()
      os.close(write_fd)
      thread.join(timeout=5)
    self.assertFalse(thread.is_alive())
    self.assertEqual(b"".join(received), b"x" * 60000 + b"\n")

  def test_writer_crash_and_policy_failure_are_sanitized_refusals(self):
    with tempfile.TemporaryFile() as sink:
      observer = logs.BuildLogs([], sink=sink)
      start = observer.start
      def crash():
        start()
        observer.delivery.process.kill()
        observer.delivery.process.wait(timeout=2)
      with patch.object(observer, "start", side_effect=crash):
        self.assertRaisesRegex(ports.Refusal, "writer failed", self.invoke, "print('hello')", observer)
      observer = logs.BuildLogs([], sink=sink)
      with patch.object(observer, "feed", side_effect=RuntimeError("private-secret")):
        with self.assertRaisesRegex(ports.Refusal, "observer failed") as caught:
          self.invoke("print('hello')", observer)
      self.assertNotIn("private-secret", str(caught.exception))
      self.assertNotIsInstance(caught.exception, ports.CommandFailed)
      self.assertIsNotNone(observer.delivery.process.returncode)

  def test_signal_during_blocked_delivery_cleans_up_both_processes(self):
    read_fd, write_fd = os.pipe()
    fcntl.fcntl(write_fd, fcntl.F_SETPIPE_SZ, 4096)
    child_pid = self.root / "child.pid"
    writer_pid = self.root / "writer.pid"
    child = ("import os,pathlib,time; pathlib.Path(" + repr(str(child_pid)) + ").write_text(str(os.getpid())); "
             "os.write(2,b'x'*60000+b'\\n'); time.sleep(30)")
    driver = ("import sys,signal,pathlib; sys.path.insert(0," + repr(str(PROJECT / "scripts")) + "); "
              "import release_io as p,release_logs as l\n"
              "def interrupt(*args): raise p.Refusal('interrupted')\n"
              "signal.signal(signal.SIGTERM,interrupt)\n"
              "observer=l.BuildLogs([])\n"
              "original=observer.start\n"
              "def start():\n original(); pathlib.Path(" + repr(str(writer_pid)) + ").write_text(str(observer.delivery.process.pid))\n"
              "observer.start=start\n"
              "try: p.command([sys.executable,'-B','-c'," + repr(child) + "],seconds=10,observer=observer)\n"
              "except p.Refusal: print('refused',flush=True)\n")
    process = subprocess.Popen([sys.executable, "-B", "-c", driver], stdout=subprocess.PIPE, stderr=write_fd)
    try:
      deadline = time.monotonic() + 4
      # A full readable pipe proves actual delivery has begun, not only helper startup.
      while time.monotonic() < deadline:
        occupied = fcntl.ioctl(read_fd, termios.FIONREAD, b"\0" * 4)
        if int.from_bytes(occupied, sys.byteorder) >= 4096 and child_pid.exists() and writer_pid.exists():
          break
        time.sleep(.01)
      else:
        self.fail("Blocked delivery did not start")
      process.terminate()
      output, _ = process.communicate(timeout=4)
      self.assertEqual(output, b"refused\n")
      for path in (child_pid, writer_pid):
        self.assertRaises(ProcessLookupError, os.kill, int(path.read_text()), 0)
    finally:
      if process.poll() is None:
        process.kill()
        process.communicate(timeout=3)
      os.close(read_fd)
      os.close(write_fd)


class BuildLogIntegrationTests(ReleaseFixture):
  def test_logging_module_is_bound_to_script_identity(self):
    before = data.settings(self.project)["script_hash"]
    with (self.project / "scripts/release_logs.py").open("a") as source:
      source.write("\n# Changed log policy.\n")
    self.assertNotEqual(data.settings(self.project)["script_hash"], before)

  def test_invalid_or_oversized_filter_config_refuses_before_local_build(self):
    path = self.docker_config / "config.json"
    for content in ("not-json", "{}" + " " * ports.CONFIG_LIMIT):
      with self.subTest(size=len(content)):
        path.write_text(content)
        result = self.run_script("--build-only")
        self.assert_refused_without_writes(result)
        self.assertIn("Release stopped:", result.stderr)
        self.assertFalse(list(self.root.glob("dev-docker-release.*")))

  def test_filter_preparation_sanitizes_invalid_config_errors(self):
    work = self.root / "private"
    work.mkdir()
    (work / "token").write_text("test-secret")
    (work / "login").write_text("dev")
    path = self.docker_config / "config.json"
    for content in ("private-not-json", "{}" + " " * ports.CONFIG_LIMIT):
      with self.subTest(size=len(content)), patch.dict(os.environ, self.env, clear=True):
        path.write_text(content)
        with self.assertRaisesRegex(ports.Refusal, "build log filtering inputs") as caught:
          data.build_logs(self.project, work, data.settings(self.project))
        self.assertNotIn("private-not-json", str(caught.exception))

  def test_local_progress_and_private_markers(self):
    password = "foreign-password:colons"
    encoded = base64.b64encode(("foreign:" + password).encode()).decode()
    (self.docker_config / "config.json").write_text(json.dumps({"auths": {"r": {"auth": encoded}}}))
    self.change(build_log_markers=[password, encoded, "test-secret", str(self.token), "https://u:unknown@host/?secret=x"])
    result = self.run_script("--build-only")
    self.assert_success(result)
    self.assertIn("#1 building base", result.stderr)
    self.assertIn("#2 running setup for npm", result.stderr)
    self.assertIn("Release phase: verify npm", result.stderr)
    self.assertNotIn("#1 building", result.stdout)
    for value in (password, encoded, "test-secret", str(self.token), "unknown"):
      self.assertNotIn(value, result.stdout + result.stderr)

  def test_failure_shows_instruction_error_and_stops_before_publication(self):
    self.change(fail="build:base", build_log_markers=["test-secret"])
    result = self.run_script()
    self.assertNotEqual(result.returncode, 0)
    self.assertIn("ERROR: synthetic setup instruction failed", result.stderr)
    self.assertNotIn("test-secret", result.stdout + result.stderr)
    self.assertEqual(self.state()["effects"], [["login", "git.lan"]])
    self.assertFalse(list(self.root.glob("dev-docker-release.*")))

  def test_publication_phase_order_and_completed_retry(self):
    result = self.run_script()
    self.assert_success(result)
    phases = ["local preflight", "read-only startup classification", "staging inventory", "snapshot preparation",
              "prepare base", "registry login", "build base", "verify base", "prepare npm", "build npm", "verify npm",
              "associate package base", "associate package npm", "tag publication", "promote base:", "promote npm:",
              "release creation", "final verification"]
    positions = [result.stderr.index("Release phase: " + phase) for phase in phases]
    self.assertEqual(positions, sorted(positions))
    self.change(effects=[], calls=[])
    retry = self.run_script()
    self.assert_success(retry)
    self.assertIn("completed release verified", retry.stderr)
    self.assertNotIn("#1 building", retry.stderr)
    self.assertEqual(self.state()["effects"], [])

  def test_staging_retry_reports_reuse_and_only_builds_missing_child(self):
    self.change(fail="build:npm")
    self.assertNotEqual(self.run_script().returncode, 0)
    state = self.state()
    state.pop("fail")
    state["effects"] = []
    self.store(state)
    result = self.run_script()
    self.assert_success(result)
    self.assertIn("reuse verified base", result.stderr)
    self.assertNotIn("#1 building base", result.stderr)
    self.assertIn("#1 building npm", result.stderr)

  def test_malformed_local_auth_refuses_without_build_or_helper(self):
    (self.docker_config / "config.json").write_text(json.dumps({"auths": {"r": {"auth": "private-invalid"}},
                                                               "credsStore": "must-not-run"}))
    result = self.run_script("--build-only")
    self.assert_refused_without_writes(result)
    self.assertIn("build log filtering inputs", result.stderr)
    self.assertNotIn("private-invalid", result.stderr)
    self.assertFalse(list(self.root.glob("dev-docker-release.*")))


if __name__ == "__main__":
  unittest.main()
