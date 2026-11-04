"""Offline image defaults and isolated OpenCode file-substitution contracts."""

import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("configure_penpot", ROOT / "scripts/configure-penpot.py")
configure = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(configure)


class PenpotConfigTests(unittest.TestCase):
  def setUp(self):
    temporary = tempfile.TemporaryDirectory(dir="/tmp/opencode")
    self.addCleanup(temporary.cleanup)
    self.root = Path(temporary.name)
    self.directory = self.root / "config/opencode"

  def test_creates_private_config_without_reading_runtime_token(self):
    configure.configure(self.directory)
    path = self.directory / "opencode.json"
    content = json.loads(path.read_text())
    self.assertEqual(content["mcp"]["servers"]["penpot"], configure.SERVER)
    self.assertEqual(content["$schema"], "https://opencode.ai/config.json")
    self.assertEqual(path.stat().st_uid, os.getuid())
    self.assertEqual(path.stat().st_mode & 0o777, 0o600)
    self.assertEqual(self.directory.stat().st_mode & 0o777, 0o700)
    self.assertEqual(sorted(path.name for path in self.directory.iterdir()), ["opencode.json"])

  def test_preserves_settings_and_other_servers_and_is_repeatable(self):
    self.directory.mkdir(parents=True)
    path = self.directory / "opencode.json"
    other = {"type": "local", "command": ["example"]}
    original = {"username": "Test", "permissions": [], "mcp": {"timeout": {"startup": 45000},
                "servers": {"other": other, "penpot": {"type": "remote", "url": "https://old.invalid"}}}}
    path.write_text(json.dumps(original))
    configure.configure(self.directory)
    first = path.read_bytes()
    configure.configure(self.directory)
    self.assertEqual(path.read_bytes(), first)
    result = json.loads(first)
    self.assertEqual(result["username"], "Test")
    self.assertEqual(result["permissions"], [])
    self.assertEqual(result["mcp"]["timeout"], original["mcp"]["timeout"])
    self.assertEqual(result["mcp"]["servers"], {"other": other, "penpot": configure.SERVER})

  def test_preserves_jsonc_settings_without_creating_second_config(self):
    self.directory.mkdir(parents=True)
    path = self.directory / "opencode.jsonc"
    path.write_text('''{
      // JSONC strings must not be mistaken for comments or trailing commas.
      "username": "https://example.invalid/a,}",
      "instructions": ["/*literal*/", /* comment */],
      "mcp": {"servers": {"other": {"type": "local", "command": ["example",],},},},
    }''')
    configure.configure(self.directory)
    result = json.loads(path.read_text())
    self.assertEqual(result["username"], "https://example.invalid/a,}")
    self.assertEqual(result["instructions"], ["/*literal*/"])
    self.assertEqual(result["mcp"]["servers"]["other"]["command"], ["example"])
    self.assertEqual(result["mcp"]["servers"]["penpot"], configure.SERVER)
    self.assertFalse((self.directory / "opencode.json").exists())

  def test_invalid_or_duplicate_config_refuses_without_overwrite(self):
    self.directory.mkdir(parents=True)
    path = self.directory / "opencode.json"
    for value in ('{"private":"do-not-print",', '{"mcp": {}, "mcp": {}}', '[]',
                  '{"mcp": null}', '{"mcp":{"servers":[]}}'):
      with self.subTest(value=value):
        path.write_text(value)
        with self.assertRaises(ValueError):
          configure.configure(self.directory)
        self.assertEqual(path.read_text(), value)
        self.assertEqual(list(self.directory.iterdir()), [path])

  def test_malformed_jsonc_refuses_without_changing_original_bytes(self):
    self.directory.mkdir(parents=True)
    path = self.directory / "opencode.jsonc"
    cases = (
      '{"username":"example",,}',
      '{"instructions":["example",,]}',
      '{"username":"example", , }',
      '{"instructions":["example", /* gap */ ,]}',
      '{"username":"example", // gap\n ,}',
      '{,}',
      '{ /* gap */ , }',
      '{"instructions":[,]}',
      '{"instructions":[ /* gap */ , ]}',
      '{"username":,}',
      '{"username": /* missing value */ ,}',
      '{"instructions":[,"example"]}',
      '{"instructions":["example",,"next"]}',
      '{"username":"first", /* duplicate */ "username":"second",}',
      '{"username":"unterminated}',
    )
    for value in cases:
      with self.subTest(value=value):
        original = ("// Existing private config\r\n" + value + "\r\n").encode()
        path.write_bytes(original)
        before = sorted(entry.name for entry in self.directory.iterdir())
        with self.assertRaises(ValueError):
          configure.configure(self.directory)
        self.assertEqual(path.read_bytes(), original)
        self.assertEqual(sorted(entry.name for entry in self.directory.iterdir()), before)

  def test_valid_jsonc_comments_and_trailing_commas_preserve_values(self):
    self.directory.mkdir(parents=True)
    path = self.directory / "opencode.jsonc"
    strings = ['https://example.invalid/a,}', 'quote: " // text', 'slash: \\', '/*literal*/ ,]']
    cases = (
      ('{"instructions":[' + ",".join(json.dumps(value) for value in strings) + ', // closing\n],}',
       {"instructions": strings}),
      ('{"extra":{"flag":true, /* closing */}, "instructions":["example" /* value */, /* closing */],}',
       {"extra": {"flag": True}, "instructions": ["example"]}),
      ('{"extra":[0, -1, 1.5, true, false, null, {}, [],], // closing\n}',
       {"extra": [0, -1, 1.5, True, False, None, {}, []]}),
    )
    for value, expected in cases:
      with self.subTest(value=value):
        path.write_text(value)
        configure.configure(self.directory)
        result = json.loads(path.read_text())
        for key, item in expected.items():
          self.assertEqual(result[key], item)
        self.assertEqual(result["mcp"]["servers"]["penpot"], configure.SERVER)
        self.assertFalse((self.directory / "opencode.json").exists())

  def test_conflicting_files_or_symlink_refuse_without_changes(self):
    self.directory.mkdir(parents=True)
    first, second = self.directory / "opencode.json", self.directory / "opencode.jsonc"
    first.write_text("{}")
    second.write_text("{}")
    with self.assertRaises(ValueError):
      configure.configure(self.directory)
    self.assertEqual(first.read_text(), "{}")
    self.assertEqual(second.read_text(), "{}")
    second.unlink()
    second.symlink_to(first)
    with self.assertRaises(ValueError):
      configure.configure(self.directory)
    self.assertTrue(second.is_symlink())

  def test_cli_failure_hides_existing_private_config(self):
    directory = self.root / ".config/opencode"
    directory.mkdir(parents=True)
    path = directory / "opencode.json"
    path.write_text('{"secret":"synthetic-private-value",')
    result = subprocess.run([shutil.which("python3"), str(ROOT / "scripts/configure-penpot.py")],
                            env={"HOME": str(self.root)}, capture_output=True, text=True, timeout=10)
    self.assertNotEqual(result.returncode, 0)
    self.assertIn("Penpot configuration refused", result.stderr)
    self.assertNotIn("synthetic-private-value", result.stdout + result.stderr)

  def test_cli_malformed_jsonc_refuses_and_preserves_private_input(self):
    directory = self.root / ".config/opencode"
    directory.mkdir(parents=True)
    path = directory / "opencode.jsonc"
    original = b'// Private config\r\n{"username":"synthetic-private-value",,}\r\n'
    path.write_bytes(original)
    result = subprocess.run([shutil.which("python3"), str(ROOT / "scripts/configure-penpot.py")],
                            env={"HOME": str(self.root)}, capture_output=True, text=True, timeout=10)
    self.assertNotEqual(result.returncode, 0)
    self.assertIn("Penpot configuration refused", result.stderr)
    self.assertNotIn("synthetic-private-value", result.stdout + result.stderr)
    self.assertNotIn("Traceback", result.stderr)
    self.assertEqual(path.read_bytes(), original)
    self.assertEqual(list(directory.iterdir()), [path])

  @unittest.skipUnless(shutil.which("opencode"), "OpenCode is required for runtime substitution checks")
  def test_runtime_loader_substitutes_synthetic_files_and_empty_failures(self):
    configure.configure(self.directory)
    path = self.directory / "opencode.json"
    token = self.root / "synthetic-token"
    env = {key: value for key, value in os.environ.items() if not key.startswith(("OPENCODE_", "XDG_"))}
    env.update(HOME=str(self.root), XDG_CONFIG_HOME=str(self.root / "config"),
               XDG_DATA_HOME=str(self.root / "data"), XDG_STATE_HOME=str(self.root / "state"),
               XDG_CACHE_HOME=str(self.root / "cache"))
    for state in ("valid", "empty", "missing", "unreadable"):
      with self.subTest(state=state):
        if state == "missing":
          token.unlink()
        else:
          token.write_text("synthetic-key" if state != "empty" else "")
        if state == "unreadable":
          token.chmod(0)
          if os.access(token, os.R_OK):
            token.chmod(0o600)
            continue  # A privileged test runner cannot simulate unreadable files this way.
        content = json.loads(path.read_text())
        # Same config-loading seam, with a non-secret query name so debug output is observable.
        prefix = "http://127.0.0.1:1/mcp?fixture="
        content["mcp"]["servers"]["penpot"]["url"] = prefix + "{file:" + str(token) + "}"
        path.write_text(json.dumps(content))
        try:
          result = subprocess.run([shutil.which("opencode"), "debug", "config", "--standalone"],
                                  cwd=self.root, env=env, capture_output=True, text=True, timeout=45)
          self.assertEqual(result.returncode, 0, result.stderr)
          documents = [item for item in json.loads(result.stdout) if item["type"] == "document"]
          document = next(item for item in documents if item["path"] == str(path))
          server = document["info"]["mcp"]["servers"]["penpot"]
          self.assertEqual(server["url"], prefix + ("synthetic-key" if state == "valid" else ""))
          self.assertFalse(server["oauth"])
          self.assertIn("{file:", path.read_text())
        finally:
          if token.exists():
            token.chmod(0o600)


class ImageContracts(unittest.TestCase):
  def test_config_runs_as_container_after_setup_without_penpot_secret(self):
    content = (ROOT / "Dockerfile/base.Dockerfile").read_text()
    user = content.index("USER ${USER_NAME}")
    setup = content.index("scripts/setup.sh | bash")
    run = content.index("python3 /tmp/configure-penpot.py")
    self.assertLess(user, setup)
    self.assertLess(setup, run)
    self.assertIn("COPY --chown=1000:1000 scripts/configure-penpot.py", content)
    self.assertIn("test -x /home/${USER_NAME}/.opencode/bin/opencode", content)
    self.assertIn("rm /tmp/configure-penpot.py", content)
    self.assertNotIn("PENPOT_MCP_KEY", content)
    self.assertIn("id=token,target=/home/container/.config/token/git,uid=1000,required=true", content)
    self.assertNotIn(".config/git/token", content)

  def test_compose_mounts_only_one_readonly_token_directory(self):
    content = (ROOT / "compose/docker-compose.yml").read_text()
    self.assertEqual(content.count("source: ${HOME}/.config/token\n"), 1)
    self.assertIn("target: /home/container/.config/token\n        read_only: true\n        bind:\n          create_host_path: false", content)
    self.assertNotIn(".config/git/token", content)
    self.assertNotIn(".config/penpot/token", content)
    for original in ("${HOME}/.ssh", "${HOME}/.gitconfig", "/var/run/docker.sock"):
      self.assertIn(original, content)


if __name__ == "__main__":
  unittest.main()
