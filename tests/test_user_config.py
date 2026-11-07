"""Private image inputs, tested only with disposable home files and fake ports."""

import json
import os
import shutil
import socket
import stat
from unittest.mock import patch

from test_build_all import ReleaseFixture
import release_data as data
import release_io as ports


class UserConfigTests(ReleaseFixture):
  def capture(self):
    with patch.dict(os.environ, self.env, clear=True):
      return data.user_config(self.project)

  def initialize(self, name="private"):
    work = self.root / name
    work.mkdir(mode=0o700)
    with patch.dict(os.environ, self.env, clear=True):
      data.init(self.project, work, "local")
    return work, ports.document(work / "settings.json") | {"commit": self.state()["commit"]}

  def test_capture_includes_nested_hidden_and_empty_files_with_private_modes(self):
    nested = self.ssh / ".hidden directory"
    nested.mkdir()
    helper = nested / "helper"
    helper.write_bytes(b"#!/bin/sh\nexit 0\n")
    helper.chmod(0o755)
    (nested / "empty").mkdir()
    self.gitconfig.write_bytes(b"")
    original = helper.stat().st_mode
    records = self.capture()
    self.assertEqual(records["ssh/.hidden directory/helper"], (0o700, helper.read_bytes()))
    self.assertEqual(records["ssh/.hidden directory/empty"], (0o700, None))
    self.assertEqual(records["gitconfig"], (0o600, b""))
    self.assertEqual(records["token/git"], (0o600, b"baked-git-secret\n"))
    work, _ = self.initialize()
    for name, (mode, value) in records.items():
      copied = work / "user-config" / name
      self.assertEqual(stat.S_IMODE(copied.stat().st_mode), mode)
      if value is not None:
        self.assertEqual(copied.read_bytes(), value)
    self.assertEqual(helper.stat().st_mode, original)

  def test_home_defaults_empty_overrides_tilde_and_relative_overrides(self):
    expected = self.capture()
    variants = [{}, {override: "" for _, _, override, _ in data.USER_INPUTS},
                {"BUILD_SSH_DIR": "~/.ssh", "BUILD_GITCONFIG_FILE": "~/.gitconfig",
                 "BUILD_TOKEN_DIR": "~/.config/token"},
                {override: os.path.relpath(path) for override, path in
                 (("BUILD_SSH_DIR", self.ssh), ("BUILD_GITCONFIG_FILE", self.gitconfig),
                  ("BUILD_TOKEN_DIR", self.tokens))}]
    for overrides in variants:
      with self.subTest(overrides=overrides), patch.dict(os.environ, {"HOME": str(self.home)} | overrides, clear=True):
        self.assertEqual(data.user_config(self.project), expected)

  def test_empty_directories_are_captured(self):
    shutil.rmtree(self.ssh)
    shutil.rmtree(self.tokens)
    self.ssh.mkdir()
    self.tokens.mkdir()
    self.assertEqual(set(self.capture()), {"ssh", "gitconfig", "token"})

  def test_missing_inputs_stop_before_builder_calls_and_remove_private_copies(self):
    for override in ("BUILD_SSH_DIR", "BUILD_GITCONFIG_FILE", "BUILD_TOKEN_DIR"):
      original = self.env[override]
      self.env[override] = str(self.root / "missing-private-input")
      for args in ((), ("--build-only",)):
        with self.subTest(override=override, args=args):
          result = self.run_script(*args)
          self.assert_refused_without_writes(result)
          self.assertEqual(self.state()["calls"], [])
          self.assertIn(override, result.stderr)
          self.assertNotIn(self.env[override], result.stdout + result.stderr)
          self.assertFalse(list(self.root.glob("dev-docker-release.*")))
      self.env[override] = original

  def test_unreadable_inputs_refuse_without_disclosing_source_errors(self):
    with patch.dict(os.environ, self.env, clear=True), \
         patch.object(data.os, "open", side_effect=PermissionError("private-path-and-secret")):
      with self.assertRaises(ports.Refusal) as caught:
        data.user_config(self.project)
    self.assertIn("BUILD_SSH_DIR", str(caught.exception))
    self.assertNotIn("private-path", str(caught.exception))

  def test_repository_contained_inputs_are_refused(self):
    for override, path in (("BUILD_SSH_DIR", self.project),
                           ("BUILD_GITCONFIG_FILE", self.project / "VERSION"),
                           ("BUILD_TOKEN_DIR", self.project / "scripts")):
      with self.subTest(override=override), patch.dict(os.environ, self.env | {override: str(path)}, clear=True):
        self.assertRaises(ports.Refusal, data.user_config, self.project)

  def test_symlinked_roots_parents_and_descendants_are_refused(self):
    link = self.root / "private-link"
    for override, target in (("BUILD_SSH_DIR", self.ssh), ("BUILD_GITCONFIG_FILE", self.gitconfig),
                             ("BUILD_TOKEN_DIR", self.tokens)):
      link.symlink_to(target)
      with self.subTest(override=override), patch.dict(os.environ, self.env | {override: str(link)}, clear=True):
        self.assertRaises(ports.Refusal, data.user_config, self.project)
      link.unlink()
    link.symlink_to(self.home, target_is_directory=True)
    with patch.dict(os.environ, self.env | {"BUILD_SSH_DIR": str(link / ".ssh")}, clear=True):
      self.assertRaises(ports.Refusal, data.user_config, self.project)
    child = self.ssh / "linked-secret"
    child.symlink_to(self.token)
    self.assertRaises(ports.Refusal, self.capture)
    child.unlink()
    child.symlink_to(self.tokens, target_is_directory=True)
    self.assertRaises(ports.Refusal, self.capture)

  def test_sockets_and_fifos_are_refused_without_blocking(self):
    child = self.ssh / "agent"
    with socket.socket(socket.AF_UNIX) as agent:
      agent.bind(str(child))
      self.assertRaises(ports.Refusal, self.capture)
    child.unlink()
    os.mkfifo(child)
    self.assertRaises(ports.Refusal, self.capture)

  def test_file_total_entry_and_depth_limits(self):
    records = self.capture()
    total = sum(len(value) for _, value in records.values() if value is not None)
    cases = [("USER_FILE_LIMIT", 1), ("USER_TOTAL_LIMIT", total - 1),
             ("USER_ENTRY_LIMIT", len(records) - 1), ("USER_DEPTH_LIMIT", 0)]
    for limit, value in cases:
      with self.subTest(limit=limit), patch.object(data, limit, value):
        self.assertRaises(ports.Refusal, self.capture)
    with patch.object(data, "USER_TOTAL_LIMIT", total), patch.object(data, "USER_ENTRY_LIMIT", len(records)):
      self.assertEqual(self.capture(), records)
    large = self.ssh / "large"
    with large.open("wb") as output:
      output.truncate(data.USER_FILE_LIMIT + 1)
    self.assertRaises(ports.Refusal, self.capture)

  def test_reads_detect_file_changes_during_capture(self):
    original = os.read
    changed = False

    def changing(descriptor, count):
      nonlocal changed
      value = original(descriptor, count)
      if value and not changed:
        changed = True
        (self.ssh / "id_ed25519").write_bytes(b"changed-during-read")
      return value

    with patch.object(data.os, "read", side_effect=changing):
      self.assertRaises(ports.Refusal, self.capture)

  def test_fingerprint_binds_names_contents_empty_directories_and_normalized_modes(self):
    records = self.capture()
    fingerprint = data.user_config_fingerprint(records)
    self.assertEqual(data.user_config_fingerprint(dict(reversed(list(records.items())))), fingerprint)
    variants = [records | {"token/new": (0o600, b"extra")},
                {name: value for name, value in records.items() if name != "token/git"},
                records | {"token/git": (0o600, b"changed")},
                records | {"ssh/empty": (0o700, None)},
                records | {"token/git": (0o700, records["token/git"][1])}]
    renamed = dict(records)
    renamed["token/renamed"] = renamed.pop("token/git")
    variants.append(renamed)
    for index, variant in enumerate(variants):
      with self.subTest(variant=index):
        self.assertNotEqual(data.user_config_fingerprint(variant), fingerprint)
    (self.tokens / "git").chmod(0o644)
    self.assertEqual(data.user_config_fingerprint(self.capture()), fingerprint)
    (self.tokens / "git").chmod(0o700)
    self.assertNotEqual(data.user_config_fingerprint(self.capture()), fingerprint)

  def test_local_and_publication_snapshots_use_captured_bytes_and_modes(self):
    original = self.gitconfig.read_bytes()
    for local in (True, False):
      self.gitconfig.write_bytes(original)
      work, config = self.initialize("snapshot-" + str(local))
      self.gitconfig.write_bytes(b"changed after capture")
      data.snapshot(self.project, work, config, local)
      copied = work / "context/user-config/gitconfig"
      self.assertEqual(copied.read_bytes(), original)
      self.assertEqual(stat.S_IMODE(copied.stat().st_mode), 0o600)
      self.assertEqual(stat.S_IMODE(copied.parent.stat().st_mode), 0o700)

  def test_changed_inputs_refuse_guard_before_inventory(self):
    work, config = self.initialize()
    with patch.dict(os.environ, self.env, clear=True), patch.object(data, "source"), \
         patch.object(data, "inventory") as inventory:
      data.unchanged(self.project, work, config)
      (self.tokens / "new").write_bytes(b"new-synthetic-token")
      self.assertRaisesRegex(ports.Refusal, "Build user configuration changed", data.guard, self.project, work, config)
      inventory.assert_not_called()

  def test_baked_tokens_do_not_replace_publication_credentials(self):
    result = self.run_script("--build-only")
    self.assert_success(result)
    self.assertNotEqual(self.token.read_text(), (self.tokens / "git").read_text())
    expected = data.user_config_fingerprint(self.capture())
    for name in ("base", "npm"):
      labels = self.state()["local_images"][name + ":latest"]["Config"]["Labels"]
      self.assertEqual(labels["dev.docker.release.user-config"], expected)
    for call in self.state()["calls"]:
      self.assertNotIn("--secret", call)
    for secret in ("baked-git-secret", "baked-penpot-secret", "synthetic-ssh-payload"):
      self.assertNotIn(secret, result.stdout + result.stderr)

  def test_changed_inputs_do_not_reuse_previous_staging_images(self):
    self.change(fail="build:npm")
    self.assertNotEqual(self.run_script().returncode, 0)
    before = self.state()
    previous = {key for key in before["manifests"] if "/base/stage-" in key}
    self.assertTrue(previous)
    (self.tokens / "new").write_text("new-synthetic-token")
    before.pop("fail")
    before["effects"] = []
    self.store(before)
    self.assert_success(self.run_script())
    after = self.state()
    self.assertEqual([name for kind, name in after["effects"] if kind == "build"], ["base", "npm"])
    self.assertTrue({key for key in after["manifests"] if "/base/stage-" in key} - previous)

  def test_completed_retry_refuses_changed_inputs_without_writes(self):
    self.assert_success(self.run_script())
    state = self.state()
    identity = json.loads(self.git("cat-file", "tag", state["tags"][self.tag]).split(data.MARKER.decode(), 1)[1])
    self.assertTrue(data.digest(identity["user_config"]))
    self.assertNotIn("baked-penpot-secret", json.dumps(identity))
    (self.tokens / "new").write_text("new-synthetic-token")
    self.change(effects=[], calls=[])
    self.assert_refused_without_writes(self.run_script())

  def test_logs_hide_captured_multiline_keys_tokens_and_source_paths(self):
    self.change(build_log_markers=["synthetic-ssh-payload", "baked-git-secret", "baked-penpot-secret", str(self.ssh)])
    result = self.run_script("--build-only")
    self.assert_success(result)
    for marker in self.state()["build_log_markers"]:
      self.assertNotIn(marker, result.stdout + result.stderr)
    self.assertIn("[redacted]", result.stderr)
