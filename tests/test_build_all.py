import fcntl
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest


PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "scripts"))
import release_data as data
import release_io as ports


class ReleaseFixture(unittest.TestCase):
  def setUp(self):
    self.temp = tempfile.TemporaryDirectory()
    self.addCleanup(self.temp.cleanup)
    self.root = Path(self.temp.name)
    self.project = self.root / "project with spaces"
    self.project.mkdir()
    for name in ("build-all.sh", "VERSION", ".gitignore"):
      shutil.copy(PROJECT / name, self.project / name)
    for name in ("scripts", "Dockerfile", "docs"):
      shutil.copytree(PROJECT / name, self.project / name)
    self.real_git = shutil.which("git")
    self.git("init", "--initial-branch=main")
    self.git("config", "user.email", "test@localhost")
    self.git("config", "user.name", "Test")
    self.git("add", ".")
    self.git("commit", "-m", "Fixture")
    commit = self.git("rev-parse", "HEAD").strip()
    self.bin = self.root / "bin"
    self.bin.mkdir()
    for name in ("git", "docker", "curl"):
      path = self.bin / name
      path.write_bytes((PROJECT / "tests/fake_release_ports.py").read_bytes())
      path.chmod(0o755)
    self.token = self.root / "token"
    self.token.write_text("test-secret\n")
    self.token.chmod(0o600)
    self.cert = self.root / "certificate"
    self.cert.write_text("test-certificate\n")
    self.docker_config = self.root / "original docker"
    self.docker_config.mkdir()
    self.state_path = self.root / "state.json"
    self.store({"commit": commit, "tags": {}, "release": None, "manifests": {}, "blobs": {},
                "local_images": {}, "calls": [], "effects": []})
    self.env = dict(os.environ, PATH=str(self.bin) + ":" + os.environ["PATH"],
                    TEST_STATE=str(self.state_path), REAL_GIT=self.real_git,
                    FORGEJO_TOKEN_FILE=str(self.token), BUILD_CERT_FILE=str(self.cert),
                    DOCKER_CONFIG=str(self.docker_config), TMPDIR=str(self.root))
    for name in ("GIT_TOKEN", "GIT_USERNAME", "FORGEJO_USERNAME", "DOCKER_CONTEXT", "DOCKER_HOST",
                 "BUILDX_CONFIG", "RELEASE_LOCK_FD"):
      self.env.pop(name, None)

  def git(self, *args):
    return subprocess.check_output([self.real_git, "-C", str(self.project), *args], stderr=subprocess.DEVNULL, text=True)

  def state(self):
    return json.loads(self.state_path.read_text())

  def store(self, value):
    self.state_path.write_text(json.dumps(value))

  def change(self, **values):
    self.store(self.state() | values)

  def run_script(self, *args):
    return subprocess.run(["bash", str(self.project / "build-all.sh"), *args], env=self.env,
                          cwd=self.root, capture_output=True, text=True, timeout=120)

  def assert_success(self, result):
    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

  def assert_refused_without_writes(self, result):
    self.assertNotEqual(result.returncode, 0, result.stdout)
    self.assertEqual(self.state()["effects"], [], result.stderr)


class LocalContractTests(ReleaseFixture):
  def test_validation_has_no_external_or_filesystem_effects(self):
    self.token.unlink()
    self.cert.unlink()
    before = sorted(str(path.relative_to(self.project)) for path in self.project.rglob("*"))
    self.assert_success(self.run_script("--validate"))
    self.assertEqual(self.state()["calls"], [])
    self.assertEqual(before, sorted(str(path.relative_to(self.project)) for path in self.project.rglob("*")))

  def test_help_and_rejected_cli_never_call_external_ports(self):
    for args in [("--help",), ("-h",)]:
      self.assert_success(self.run_script(*args))
    for args in [("latest",), ("v9.0.0",), ("one", "two"), ("--unknown",), ("--help", "v0.1.0"),
                 ("--validate", "v0.1.0"), ("--validate", "--build-only"), ("--build-only", "--build-only")]:
      with self.subTest(args=args):
        self.assert_refused_without_writes(self.run_script(*args))
    self.assertEqual(self.state()["calls"], [])

  def test_build_only_loads_five_images_with_exact_local_parents(self):
    self.assert_success(self.run_script("--build-only", "v0.1.0"))
    state = self.state()
    self.assertEqual([effect[1] for effect in state["effects"]], [item[0] for item in data.GRAPH])
    self.assertFalse(any(call[0] == "curl" for call in state["calls"]))
    self.assertFalse(any(call[0] == "git" and "ls-remote" in call for call in state["calls"]))
    for name, _, _ in data.GRAPH:
      self.assertIn(name + ":latest", state["local_images"])
    self.assertFalse(list(self.root.glob("dev-docker-release.*")))

  def test_build_only_accepts_reversed_assertion_order(self):
    self.assert_success(self.run_script("v0.1.0", "--build-only"))

  def test_unsupported_builders_missing_platform_and_wrong_endpoint_refuse_before_build(self):
    for setting in ({"driver": "docker-container"}, {"driver": "remote"}, {"platforms": "linux/arm64"},
                    {"endpoint": "different"}):
      with self.subTest(setting=setting):
        self.change(driver="docker", platforms="linux/amd64", endpoint="default", **{})
        self.change(**setting)
        self.assert_refused_without_writes(self.run_script("--build-only"))

  def test_wrong_loaded_parent_stops_before_child(self):
    self.change(wrong_parent=True)
    result = self.run_script("--build-only")
    self.assertNotEqual(result.returncode, 0)
    self.assertEqual(self.state()["effects"], [["build", "my-base"]])
    self.assertIn("metadata", result.stderr)

  def test_token_permissions_and_location_refuse(self):
    self.token.chmod(0o644)
    self.assert_refused_without_writes(self.run_script("--build-only"))
    self.token.chmod(0o600)
    link = self.root / "token-link"
    link.symlink_to(self.token)
    self.env["GIT_TOKEN"] = str(link)
    self.assert_refused_without_writes(self.run_script("--build-only"))
    self.env["GIT_TOKEN"] = str(self.project / "VERSION")
    self.assert_refused_without_writes(self.run_script("--build-only"))

  def test_source_and_target_preflight_refuse_before_credentials_or_writes(self):
    self.token.unlink()
    self.change(remote="ssh://git@git.lan/dev/wrong.git")
    self.assert_refused_without_writes(self.run_script())
    self.change(remote="ssh://git@git.lan/dev/dev-docker.git", remote_commit="0" * 40)
    self.assert_refused_without_writes(self.run_script())
    self.change(remote_commit=self.state()["commit"])
    (self.project / "dirty").write_text("not committed")
    self.assert_refused_without_writes(self.run_script())

  def test_build_failure_cleans_private_files(self):
    self.change(fail="build:android-dev")
    result = self.run_script("--build-only")
    self.assertNotEqual(result.returncode, 0)
    self.assertEqual([value for kind, value in self.state()["effects"] if kind == "build"], ["my-base", "npm-non-root"])
    self.assertFalse(list(self.root.glob("dev-docker-release.*")))
    self.assertNotIn("test-secret", result.stdout + result.stderr)

  def test_checkout_lock_contention_refuses_before_build(self):
    with (self.project / ".release-operation.lock").open("w") as lock:
      fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
      self.assert_refused_without_writes(self.run_script("--build-only"))

  def test_missing_token_and_certificate_fail_without_builds(self):
    self.token.unlink()
    self.assert_refused_without_writes(self.run_script("--build-only"))
    self.cert.unlink()
    self.assert_refused_without_writes(self.run_script("--build-only"))

  def test_host_only_docker_connection_and_relative_paths(self):
    self.env["DOCKER_HOST"] = "tcp://test-host:2376"
    self.env["DOCKER_CONFIG"] = os.path.relpath(self.docker_config, self.root)
    self.change(endpoint="tcp://test-host:2376")
    self.assert_success(self.run_script("--build-only"))

  def test_signal_stops_owned_build_and_removes_private_files(self):
    self.change(pause_build=True)
    process = subprocess.Popen(["bash", str(self.project / "build-all.sh"), "--build-only"],
                               env=self.env, cwd=self.root, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
      marker = Path(str(self.state_path) + ".started")
      deadline = time.monotonic() + 15
      while not marker.exists() and process.poll() is None and time.monotonic() < deadline:
        time.sleep(0.02)
      self.assertTrue(marker.exists(), "Fake build never started")
      process.terminate()
      output, error = process.communicate(timeout=15)
      self.assertNotEqual(process.returncode, 0, output + error)
      self.assertFalse(list(self.root.glob("dev-docker-release.*")))
      self.assertNotIn("test-secret", output + error)
    finally:
      if process.poll() is None:
        process.kill()
        process.communicate()


class PublicationTests(ReleaseFixture):
  def test_five_image_release_and_completed_read_only_retry(self):
    first = self.run_script("v0.1.0")
    self.assert_success(first)
    state = self.state()
    kinds = [effect[0] for effect in state["effects"]]
    self.assertEqual(kinds.count("build"), 5)
    self.assertEqual(kinds.count("promote"), 10)
    self.assertLess(max(index for index, kind in enumerate(kinds) if kind == "build"), kinds.index("tag"))
    self.assertEqual(kinds[-1], "post")
    self.assertFalse(Path(state["private_config"]).exists())
    self.assertEqual(state["buildx_config"], str(self.docker_config / "buildx"))
    self.assertNotIn("test-secret", first.stdout + first.stderr)
    # Completed publications do not rely on staging aliases.
    state["manifests"] = {key: value for key, value in state["manifests"].items() if "/stage-" not in key}
    state["effects"], state["calls"] = [], []
    self.store(state)
    self.assert_success(self.run_script())
    self.assertEqual(self.state()["effects"], [])
    self.assertFalse(any(call[0] == "curl" and "stage-" in call[-1] for call in self.state()["calls"]))

  def test_fifth_image_orphan_alias_and_malformed_inventory_block_all_writes(self):
    manifest = {"schemaVersion": 2, "foreign": True}
    self.change(manifests={"git.lan/dev/switchboard/v0.1.0": manifest})
    self.assert_refused_without_writes(self.run_script())
    self.change(manifests={}, malformed_fifth=True)
    self.assert_refused_without_writes(self.run_script())

  def test_tag_only_and_release_only_refuse_without_login(self):
    self.change(tags={"v0.1.0": "a" * 40})
    self.assert_refused_without_writes(self.run_script())
    self.change(tags={}, release={"tag_name": "v0.1.0", "draft": False, "prerelease": False})
    self.assert_refused_without_writes(self.run_script())

  def test_staging_retry_reuses_verified_parents(self):
    self.change(fail="build:android-dev")
    self.assertNotEqual(self.run_script().returncode, 0)
    state = self.state()
    self.assertEqual([value for kind, value in state["effects"] if kind == "build"], ["my-base", "npm-non-root"])
    state.pop("fail")
    state["effects"] = []
    self.store(state)
    self.assert_success(self.run_script())
    self.assertEqual([value for kind, value in self.state()["effects"] if kind == "build"],
                     ["android-dev", "tauri-dev", "switchboard"])

  def test_matching_orphan_version_alias_is_not_adopted(self):
    self.change(fail="build:npm-non-root")
    self.assertNotEqual(self.run_script().returncode, 0)
    state = self.state()
    staged = next(value for key, value in state["manifests"].items() if "/my-base/stage-" in key)
    state["manifests"]["git.lan/dev/my-base/v0.1.0"] = staged
    state["effects"] = []
    state.pop("fail")
    self.store(state)
    self.assert_refused_without_writes(self.run_script())

  def test_lost_tag_response_reconciles_once(self):
    self.change(lose_response="tag")
    self.assert_success(self.run_script())
    self.assertEqual(sum(kind == "tag" for kind, _ in self.state()["effects"]), 1)

  def test_lost_promotion_response_reconciles_once(self):
    self.change(lose_response="promote")
    self.assert_success(self.run_script())
    self.assertEqual(sum(kind == "promote" for kind, _ in self.state()["effects"]), 10)

  def test_lost_release_response_reconciles_once(self):
    self.change(lose_response="post")
    self.assert_success(self.run_script())
    self.assertEqual(sum(kind == "post" for kind, _ in self.state()["effects"]), 1)

  def test_promoted_alias_reversion_stops_before_release(self):
    self.change(revert_promoted=True)
    result = self.run_script()
    self.assertNotEqual(result.returncode, 0)
    self.assertFalse(any(kind == "post" for kind, _ in self.state()["effects"]))
    self.assertEqual(sum(kind == "promote" for kind, _ in self.state()["effects"]), 2)
    self.assertFalse(list(self.root.glob("dev-docker-release.*")))

  def test_partial_promotion_retry_refuses_without_repair(self):
    self.change(fail="promote")
    self.assertNotEqual(self.run_script().returncode, 0)
    state = self.state()
    self.assertTrue(state["tags"])
    state.pop("fail")
    state["effects"] = []
    self.store(state)
    self.assert_refused_without_writes(self.run_script())


class DataBoundaryTests(ReleaseFixture):
  def test_settings_reject_unknown_duplicate_traversal_and_changed_graph(self):
    path = self.project / "scripts/release.json"
    original = path.read_text()
    mutations = [original.replace('"schema": 1', '"schema": 1, "unknown": 1'),
                 original.replace('"schema": 1', '"schema": 1, "schema": 1'),
                 original.replace('docs/releases/0.1.0.md', '../outside.md'),
                 original.replace('"parent": "my-base"', '"parent": "android-dev"')]
    for content in mutations:
      with self.subTest(content=content[:40]):
        path.write_text(content)
        self.assertRaises((ports.Refusal, ValueError), data.settings, self.project)
    path.write_text(original)
    version = self.project / "VERSION"
    for value in ("01.0.0", "1.2", "v1.2.3", "1.2.3-alpha"):
      version.write_text(value)
      self.assertRaises(ports.Refusal, data.settings, self.project)

  def test_credential_override_precedence_and_empty_values(self):
    from unittest.mock import patch
    work = self.root / "private"
    work.mkdir(mode=0o700)
    config = data.settings(self.project)
    config["token_file"] = str(self.token)
    other = self.root / "other-token"
    other.write_text("new-secret")
    other.chmod(0o400)
    cases = [({}, "test-secret", "dev"),
             ({"GIT_TOKEN": "", "FORGEJO_TOKEN_FILE": str(self.token)}, "test-secret", "dev"),
             ({"GIT_TOKEN": str(other), "FORGEJO_TOKEN_FILE": str(self.token),
               "GIT_USERNAME": "new", "FORGEJO_USERNAME": "old"}, "new-secret", "new"),
             ({"FORGEJO_USERNAME": "old", "GIT_USERNAME": ""}, "test-secret", "old"),
             ({"GIT_TOKEN": str(other)}, "new-secret", "dev")]
    for environment, token, login in cases:
      with self.subTest(environment=environment), patch.dict(os.environ, environment, clear=True):
        data.credentials(self.project, work, config)
        self.assertEqual((work / "token").read_text(), token)
        self.assertEqual((work / "login").read_text(), login)

  def test_auth_isolation_preserves_plugins_context_but_not_registry_helpers(self):
    from unittest.mock import patch
    plugins = self.docker_config / "cli-plugins"
    plugins.mkdir()
    (plugins / "docker-buildx").write_text("test plugin")
    (self.docker_config / "config.json").write_text(json.dumps({"auths": {"foreign": {"auth": "secret"}},
      "credsStore": "helper", "credHelpers": {"git.lan": "helper"}, "cliPluginsExtraDirs": [str(plugins)]}))
    work = self.root / "private"
    work.mkdir(mode=0o700)
    with patch.dict(os.environ, self.env | {"DOCKER_CONTEXT": "selected"}):
      data.docker_auth(work)
    config = json.loads((work / "docker/config.json").read_text())
    self.assertEqual(config["auths"], {})
    self.assertEqual(config["currentContext"], "selected")
    self.assertNotIn("credsStore", config)
    self.assertNotIn("credHelpers", config)
    self.assertEqual((work / "docker/cli-plugins").resolve(), plugins)
    self.assertEqual(config["cliPluginsExtraDirs"], [str(plugins)])

  def test_bounded_capture_refuses_overflow_and_drains_both_pipes(self):
    self.assertRaises(ports.Refusal, ports.command, [sys.executable, "-c", "print('x'*101)"], 100)
    value = ports.command([sys.executable, "-c", "import sys; sys.stderr.write('e'*65536); print('ok')"], 100)
    self.assertEqual(value, b"ok\n")

  def test_registry_foreign_token_realm_refused(self):
    from unittest.mock import patch
    with patch.object(ports, "http", return_value=(401, {"www-authenticate": 'Bearer realm="https://foreign/token"'}, b"")) as http:
      self.assertRaises(ports.Refusal, ports.registry, self.root, "https://git.lan", "git.lan/dev/my-base", "manifests", "latest")
      self.assertEqual(http.call_count, 1)

  def test_guard_rejects_changed_confirmed_tag_before_any_write(self):
    from unittest.mock import patch
    work = self.root / "private"
    work.mkdir()
    config = data.settings(self.project) | {"commit": self.state()["commit"]}
    names = [item[0] for item in data.GRAPH]
    aliases = {name: None for name in names}
    state = {"oid": "a" * 40, "digests": {}, "predecessors": aliases,
             "versions": aliases, "latest": aliases}
    ports.write(work / "state.json", state)
    observed = {"oid": "b" * 40, "commit": config["commit"], "release": None,
                "versions": aliases, "latest": aliases}
    with patch.object(data, "unchanged"), patch.object(data, "inventory", return_value=observed):
      self.assertRaisesRegex(ports.Refusal, "tag disappeared or changed", data.guard, self.project, work, config)

  def test_readers_reject_oversized_and_duplicate_json(self):
    path = self.root / "oversized"
    path.write_bytes(b"x" * 101)
    self.assertRaises(ports.Refusal, ports.read, path, 100)
    self.assertRaises(ports.Refusal, ports.decode, b'{"a":1,"a":2}')
    self.assertRaises(ports.Refusal, ports.decode, b'{"a":NaN}')

  def test_inventory_refuses_nonterminal_repeated_pages(self):
    from unittest.mock import patch
    work = self.root / "private"
    work.mkdir()
    config = data.settings(self.project)
    record = {"tag_name": "v0.0.1", "draft": False, "prerelease": False}
    with patch.object(data, "http", return_value=(200, {}, ports.canonical([record]))):
      self.assertRaisesRegex(ports.Refusal, "pagination repeated", data.inventory, self.project, work, config)
    self.assertIsNone(ports.INVENTORY_BUDGET)

  def test_failed_prewrite_read_never_becomes_lost_write_authority(self):
    from unittest.mock import Mock
    check = Mock(side_effect=ports.CommandFailed("Read transport failed"))
    with self.assertRaises(ports.Refusal) as refused:
      data.prewrite(check)
    self.assertNotIsInstance(refused.exception, ports.CommandFailed)
    self.assertIn("no mutation attempted", str(refused.exception))


if __name__ == "__main__":
  unittest.main()
