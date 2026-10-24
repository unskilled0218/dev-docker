"""HTTP status diagnostics exercise real parsing with synthetic capture results."""

from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from test_build_all import data, ports


class HttpDiagnosticsTests(unittest.TestCase):
  def setUp(self):
    temporary = tempfile.TemporaryDirectory(dir="/tmp/opencode")
    self.addCleanup(temporary.cleanup)
    self.work = Path(temporary.name)
    self.config = {"gitea": "https://registry.invalid", "repository": "owner/repo"}
    self.markers = ("synthetic-body-secret", "synthetic-header-secret", "synthetic-stderr-secret",
                    "synthetic-query-secret", "synthetic-auth-path", "synthetic-payload-path")

  def packet(self, code, body=b'{"secret":"synthetic-body-secret"}', headers=b""):
    return 0, {"stdout": str(code).encode(), "stderr": b"synthetic-stderr-secret",
               "body": body, "headers": headers or b"HTTP/1.1 200 synthetic-header-secret\r\nX-Secret: synthetic-header-secret\r\n\r\n"}

  def request(self):
    return ports.http(self.work, "POST", "https://registry.invalid/api?token=synthetic-query-secret",
                      auth="synthetic-auth-path", payload=self.work / "synthetic-payload-path")

  def assert_private(self, message):
    for marker in self.markers:
      self.assertNotIn(marker, message)
    self.assertNotIn("https://", message)
    self.assertNotIn(str(self.work), message)

  def refusal(self, action, code):
    with self.assertRaises(ports.Refusal) as caught:
      action()
    self.assertNotIsInstance(caught.exception, ports.CommandFailed)
    message = str(caught.exception)
    self.assertRegex(message, rf"HTTP(?: status:)? {code}\b")
    self.assert_private(message)
    return message

  def test_rejected_transport_statuses_report_only_the_parsed_code(self):
    for code in (302, 400, 403, 429, 500):
      with self.subTest(code=code), patch.object(ports, "capture", return_value=self.packet(code)):
        self.refusal(self.request, code)

  def test_transport_allowlist_and_response_return_values_are_unchanged(self):
    for code in (200, 201, 401, 404):
      with self.subTest(code=code), patch.object(ports, "capture", return_value=self.packet(code)):
        actual, headers, body = self.request()
        self.assertEqual(actual, code)
        self.assertEqual(headers["x-secret"], "synthetic-header-secret")
        self.assertIn(b"synthetic-body-secret", body)  # Internal data is not diagnostic output.

  def test_malformed_status_output_stays_sanitized(self):
    for value in (b"", b"40", b"403\n", b"abc", b"synthetic-body-secret", b"\xff\xff\xff"):
      with self.subTest(value=value):
        status, output = self.packet(403)
        output["stdout"] = value
        with patch.object(ports, "capture", return_value=(status, output)):
          with self.assertRaisesRegex(ports.Refusal, "Invalid HTTP status") as caught:
            self.request()
        self.assertNotIsInstance(caught.exception, ports.CommandFailed)
        self.assert_private(str(caught.exception))

  def test_nonzero_curl_exit_preserves_transport_failure_and_hides_status(self):
    _, output = self.packet(403)
    with patch.object(ports, "capture", return_value=(7, output)):
      with self.assertRaises(ports.CommandFailed) as caught:
        self.request()
    message = str(caught.exception)
    self.assertIn("HTTPS transport failed", message)
    self.assertNotIn("403", message)
    self.assert_private(message)

  def test_capture_and_inventory_limits_keep_precedence_over_status(self):
    with patch.object(ports, "capture", side_effect=ports.Refusal("Command output exceeds byte limit")):
      with self.assertRaisesRegex(ports.Refusal, "exceeds byte limit") as caught:
        self.request()
      self.assert_private(str(caught.exception))
    budget = {"deadline": time.monotonic() + 60, "bytes": 64 * 1024 * 1024}
    with patch.object(ports, "INVENTORY_BUDGET", budget), patch.object(ports, "capture", return_value=self.packet(403)):
      with self.assertRaisesRegex(ports.Refusal, "Inventory byte/time budget exceeded") as caught:
        self.request()
      self.assertNotIn("403", str(caught.exception))
      self.assert_private(str(caught.exception))
    with patch.object(ports, "INVENTORY_BUDGET", {"deadline": 0, "bytes": 0}), patch.object(ports, "capture") as capture:
      with self.assertRaisesRegex(ports.Refusal, "Inventory time budget exceeded"):
        self.request()
      capture.assert_not_called()

  def test_api_read_and_inventory_rejections_include_transport_allowed_codes(self):
    for code in (201, 401, 404):
      with self.subTest(code=code), patch.object(ports, "capture", return_value=self.packet(code)):
        self.refusal(lambda: data.api_read(self.work, self.config, "user"), code)
        self.refusal(lambda: data.inventory(self.work, self.work, self.config), code)
      self.assertIsNone(ports.INVENTORY_BUDGET)

  def test_package_link_rejection_preserves_code_and_refusal_type(self):
    ports.write(self.work / "state.json", {"digests": {"base": "fixture", "npm": "fixture"}, "link_attempts": []})
    observed = {"packages": {"base": "unlinked", "npm": "unlinked"}}
    with patch.object(data, "guard", return_value=observed), patch.object(ports, "capture", return_value=self.packet(200)):
      message = self.refusal(lambda: data.link_package(self.work, self.work, self.config, "base"), 200)
    self.assertIn("inspect without reassignment", message)
    self.assertEqual(ports.document(self.work / "state.json")["link_attempts"], ["base"])

  def test_release_creation_rejection_preserves_code_and_refusal_type(self):
    ports.write(self.work / "settings.json", self.config)
    with patch.object(data, "payload"), patch.object(ports, "capture", return_value=self.packet(404)):
      self.refusal(lambda: data.dispatch(["post-release", str(self.work), str(self.work)]), 404)

  def test_registry_token_and_evidence_rejections_include_code(self):
    challenge = b'HTTP/1.1 401 Unauthorized\r\nWWW-Authenticate: Bearer realm="https://registry.invalid/token"\r\n\r\n'
    for code in (401, 404):
      with self.subTest(token_status=code), patch.object(ports, "capture", side_effect=[
          self.packet(401, headers=challenge), self.packet(code)]):
        self.refusal(lambda: ports.registry(self.work, "https://registry.invalid", "registry.invalid/owner/base",
                                            "manifests", "latest"), code)
    with patch.object(ports, "capture", return_value=self.packet(404)):
      self.refusal(lambda: ports.registry(self.work, "https://registry.invalid", "registry.invalid/owner/base",
                                          "manifests", "latest"), 404)

  def test_registry_challenge_and_confirmed_absence_remain_normal_control_flow(self):
    challenge = b'HTTP/1.1 401 Unauthorized\r\nWWW-Authenticate: Bearer realm="https://registry.invalid/token"\r\n\r\n'
    content = ports.canonical({"schemaVersion": 2})
    with patch.object(ports, "capture", side_effect=[self.packet(401, headers=challenge),
        self.packet(200, b'{"token":"synthetic-bearer"}'), self.packet(200, content)]):
      self.assertEqual(ports.registry(self.work, "https://registry.invalid", "registry.invalid/owner/base",
                                     "manifests", "latest"), (ports.sha(content), {"schemaVersion": 2}))
    missing = ports.canonical({"errors": [{"code": "MANIFEST_UNKNOWN"}]})
    with patch.object(ports, "capture", return_value=self.packet(404, missing)):
      self.assertIsNone(ports.registry(self.work, "https://registry.invalid", "registry.invalid/owner/base",
                                      "manifests", "latest", missing=True))

  def test_success_status_with_invalid_json_is_not_a_status_failure(self):
    with patch.object(ports, "capture", return_value=self.packet(200, b"synthetic-body-secret")):
      with self.assertRaises(ValueError) as caught:
        data.api_read(self.work, self.config, "user")
    self.assertNotIn("HTTP 200", str(caught.exception))
    self.assert_private(str(caught.exception))


if __name__ == "__main__":
  unittest.main()
