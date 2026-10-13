import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


PROJECT = Path(__file__).resolve().parents[1]


class BuildAllTests(unittest.TestCase):
  def setUp(self):
    self.temp = tempfile.TemporaryDirectory()
    self.addCleanup(self.temp.cleanup)
    self.root = Path(self.temp.name)
    self.project = self.root / "project with spaces"
    self.project.mkdir()
    shutil.copy(PROJECT / "build-all.sh", self.project)
    shutil.copytree(PROJECT / "Dockerfile", self.project / "Dockerfile")
    self.bin = self.root / "bin"
    self.bin.mkdir()
    self.log = self.root / "docker.jsonl"
    self.token = self.root / "token"
    self.token.write_text("test-secret\n")
    self.cert = self.root / "cert"
    self.cert.write_text("test-certificate\n")
    self.write_command("git", '#!/bin/bash\nprintf "%s\\n" "$TEST_REMOTE"\n')
    self.write_command("docker", """#!/usr/bin/env python3
import json, os, pathlib, sys
args = sys.argv[1:]
with open(os.environ['TEST_LOG'], 'a') as log:
  log.write(json.dumps(args) + '\\n')
command = args[2] if args[0] == '--config' else args[0]
if command == 'login':
  assert sys.stdin.read() == 'test-secret\\n'
  pathlib.Path(args[1], 'config.json').write_text('test-secret')
if command == 'build':
  context = pathlib.Path(args[-1])
  assert not (context / 'forgejo-token').exists()
  assert (context / 'git.lanCA.crt').exists()
if command == os.environ.get('TEST_FAIL'):
  sys.exit(9)
""")
    self.env = dict(os.environ, PATH=f"{self.bin}:{os.environ['PATH']}",
                    TEST_REMOTE="ssh://git@git.lan/dev/dev-docker.git",
                    TEST_LOG=str(self.log), FORGEJO_TOKEN_FILE=str(self.token),
                    BUILD_CERT_FILE=str(self.cert), FORGEJO_USERNAME="dev")

  def write_command(self, name, content):
    path = self.bin / name
    path.write_text(content)
    path.chmod(0o755)

  def run_script(self, *args):
    return subprocess.run(["bash", str(self.project / "build-all.sh"), *args],
                          env=self.env, cwd=self.root, capture_output=True, text=True)

  def calls(self):
    return [json.loads(line) for line in self.log.read_text().splitlines()]

  def test_release_and_cleanup(self):
    result = self.run_script("v1.2.3")
    self.assertEqual(result.returncode, 0, result.stderr)
    calls = self.calls()
    builds = [call for call in calls if call[0] == "build"]
    pushes = [call for call in calls if "push" in call]
    self.assertEqual(len(builds), 4)
    self.assertEqual(len(pushes), 4)
    for build, image in zip(builds, ["my-base", "npm-non-root", "android-dev", "tauri-dev"]):
      self.assertIn(f"{image}:latest", build)
      self.assertIn(f"git.lan/dev/{image}:v1.2.3", build)
      self.assertIn("org.opencontainers.image.source=https://git.lan/dev/dev-docker", build)
      self.assertFalse(Path(build[-1]).exists())
    self.assertIn("--secret", builds[0])
    self.assertTrue(all("--secret" not in build for build in builds[1:]))
    self.assertFalse(Path(pushes[0][1]).exists())
    self.assertLess(calls.index(builds[-1]), calls.index(pushes[0]))
    self.assertFalse((self.project / "forgejo-token").exists())

  def test_build_only_and_remote_forms(self):
    for remote in ["git@git.lan:dev/dev-docker.git", "https://git.lan/dev/dev-docker.git",
                   "ssh://git@git.lan:2222/dev/dev-docker.git"]:
      with self.subTest(remote=remote):
        self.env["TEST_REMOTE"] = remote
        self.log.unlink(missing_ok=True)
        result = self.run_script("--build-only")
        self.assertEqual(result.returncode, 0, result.stderr)
        calls = self.calls()
        self.assertEqual(len(calls), 5)
        self.assertIn("git.lan/dev/my-base:latest", calls[1])

  def test_failures_stop_and_cleanup(self):
    for failure in ["login", "build", "push"]:
      with self.subTest(failure=failure):
        self.env["TEST_FAIL"] = failure
        self.log.unlink(missing_ok=True)
        result = self.run_script()
        self.assertEqual(result.returncode, 9)
        calls = self.calls()
        self.assertFalse(Path(calls[1][1]).exists())
        if failure != "push":
          self.assertFalse(any("push" in call for call in calls))
        else:
          self.assertEqual(sum("push" in call for call in calls), 1)

  def test_invalid_inputs_do_not_call_docker(self):
    for args in [("bad/tag",), ("one", "two"), ("--unknown",)]:
      self.assertNotEqual(self.run_script(*args).returncode, 0)
      self.assertFalse(self.log.exists())
    self.env["TEST_REMOTE"] = "/local/repository"
    self.assertNotEqual(self.run_script().returncode, 0)
    self.assertFalse(self.log.exists())


if __name__ == "__main__":
  unittest.main()
