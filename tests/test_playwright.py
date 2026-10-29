"""Offline remote-browser configuration contracts; no Docker or network needed."""
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]


def app_source_has_4096_port(content):
  """Conservatively detect port 4096 in the app's block-style ports section."""
  app = re.search(r"(?ms)^  app:\s*\n(.*?)(?=^  [\w.-]+:\s*(?:#.*)?$|^\S|\Z)", content)
  if not app:
    raise ValueError("app service not found")
  ports = re.search(r"(?ms)^    ports:\s*[^\n]*\n?(.*?)(?=^    [\w.-]+:|\Z)", app.group(1))
  if not ports:
    return bool(re.search(r"(?m)^    ports:.*\b4096\b", app.group(1)))
  return bool(re.search(r"\b4096\b", ports.group(0)))


class PlaywrightConfigurationTests(unittest.TestCase):
  def test_image_server_and_client_versions_match(self):
    server = (ROOT / "compose/playwright-compose.yml").read_text()
    npm = (ROOT / "Dockerfile/npm.Dockerfile").read_text()
    image_version = re.search(r"mcr\.microsoft\.com/playwright:v(\d+\.\d+\.\d+)-noble", server).group(1)
    self.assertIn('"playwright@' + image_version + '"', server)
    self.assertIn("@playwright/test@" + image_version, npm)
    self.assertIn("PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1 npm install --save-exact", npm)
    self.assertIn('PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD: "1"', server)

  def test_development_images_do_not_install_browsers(self):
    for name in ("base", "npm"):
      with self.subTest(image=name):
        content = (ROOT / f"Dockerfile/{name}.Dockerfile").read_text()
        self.assertNotRegex(content, r"playwright\s+install(?:-deps)?\b")
    self.assertTrue((ROOT / "Dockerfile/npm.Dockerfile").read_text().startswith(
      "ARG BASE_IMAGE=base:latest\nFROM ${BASE_IMAGE}\n"))
    base = (ROOT / "Dockerfile/base.Dockerfile").read_text()
    self.assertIn("FROM ubuntu:24.04", base)
    self.assertIn("scripts/setup.sh | bash", base)
    self.assertNotIn("mcr.microsoft.com/playwright", base)

  def test_server_is_private_and_non_root(self):
    server = (ROOT / "compose/playwright-compose.yml").read_text()
    for contract in ("user: pwuser", "working_dir: /home/pwuser", "init: true", 'shm_size: "1gb"'):
      self.assertIn(contract, server)
    for forbidden in ("ports:", "privileged:", "cap_add:", "ipc:", "docker.sock", ".ssh", ".config/git"):
      self.assertNotIn(forbidden, server)
    self.assertIn("source: ../scripts/playwright-healthcheck.cjs", server)
    self.assertIn("target: /opt/playwright-healthcheck.cjs", server)
    self.assertIn("read_only: true", server)
    self.assertIn("create_host_path: false", server)
    self.assertNotIn("workdir:", server)

  def test_independent_clients_use_the_owned_shared_network(self):
    server = (ROOT / "compose/playwright-compose.yml").read_text()
    client = (ROOT / "compose/docker-compose.yml").read_text()
    self.assertIn("name: development-playwright", server)
    self.assertIn("name: development\n", server)
    self.assertIn("driver: bridge", server)
    self.assertIn("external: true", client)
    self.assertIn("name: development\n", client)
    self.assertIn("PW_TEST_CONNECT_WS_ENDPOINT: ws://playwright:3000/", client)
    self.assertIn("image: git.lan/dev/base:latest", client)
    self.assertFalse(app_source_has_4096_port(client))
    self.assertEqual(client.count("create_host_path: false"), 3)
    self.assertEqual(client.count("read_only: true"), 3)

  def test_port_check_rejects_alternative_mappings(self):
    for ports in ('      - "8080:4096"\n', '      - target: 4096\n        published: "8080"\n'):
      with self.subTest(ports=ports):
        self.assertTrue(app_source_has_4096_port("services:\n  app:\n    ports:\n" + ports))

  def test_healthcheck_has_bounded_timing_and_no_package_download(self):
    server = (ROOT / "compose/playwright-compose.yml").read_text()
    for contract in ('test: ["CMD", "node", "/opt/playwright-healthcheck.cjs"]',
                     "interval: 5s", "timeout: 3s", "start_period: 45s", "retries: 12"):
      self.assertIn(contract, server)
    probe = (ROOT / "scripts/playwright-healthcheck.cjs").read_text()
    self.assertNotIn("npx", probe)
    self.assertIn("process.exitCode = 1", probe)


if __name__ == "__main__":
  unittest.main()
