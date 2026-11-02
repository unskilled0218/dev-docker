import fcntl
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch


PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "scripts"))
import release_data as data
import release_io as ports


class ReleaseFixture(unittest.TestCase):
  def setUp(self):
    self.make_fixture("1.2.3")

  def make_fixture(self, version, source=PROJECT):
    self.temp = tempfile.TemporaryDirectory()
    self.addCleanup(self.temp.cleanup)
    self.root = Path(self.temp.name)
    self.project = self.root / "project with spaces"
    self.project.mkdir()
    for name in ("build-all.sh", ".gitignore"):
      shutil.copy(source / name, self.project / name)
    for name in ("scripts", "Dockerfile"):
      shutil.copytree(source / name, self.project / name)
    self.version = version
    self.tag = "v" + self.version
    self.notes_path = "docs/releases/fixture.md"
    (self.project / "VERSION").write_text(self.version + "\n")
    notes = self.project / self.notes_path
    notes.parent.mkdir(parents=True)
    notes.write_text("# Release " + self.tag + "\n\n- Test-owned release notes.\n")
    settings = self.project / "scripts/release.json"
    config = json.loads(settings.read_text())
    config["notes"] = self.notes_path
    settings.write_text(json.dumps(config))
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
    self.ntfy_cert = self.root / "ntfy certificate"
    self.ntfy_cert.write_text("test-ntfy-certificate\n")
    self.docker_config = self.root / "original docker"
    self.docker_config.mkdir()
    self.state_path = self.root / "state.json"
    # Minimal real response fields from upstream Gitea v1.24.7/v28.2.0 schemas.
    owner = {"id": 7, "login": "dev", "active": True, "restricted": False,
             "prohibit_login": False, "type": "User"}
    repository = {"id": 19, "full_name": "dev/dev-docker", "owner": owner,
                  "has_packages": True, "permissions": {"admin": True}}
    self.store({"commit": commit, "release_tag": self.tag, "tags": {}, "release": None, "manifests": {}, "blobs": {},
                "local_images": {}, "calls": [], "effects": [], "packages": {}, "principal": owner,
                "namespace": owner, "repository": repository, "server_version": {"version": "28.2.0"}})
    self.env = dict(os.environ, PATH=str(self.bin) + ":" + os.environ["PATH"],
                    TEST_STATE=str(self.state_path), REAL_GIT=self.real_git,
                    FORGEJO_TOKEN_FILE=str(self.token), BUILD_CERT_FILE=str(self.cert),
                    BUILD_NTFY_CERT_FILE=str(self.ntfy_cert),
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

  def proxy_config(self):
    return {
      "default": {
        "httpProxy": "http://proxy-user:synthetic-proxy-password@proxy.invalid:3128",
        "httpsProxy": "http://proxy.invalid:3129",
        "ftpProxy": "ftp://proxy.invalid:2121",
        "noProxy": "localhost,*.internal.invalid,10.0.0.0/8,[::1]",
        "allProxy": "socks5h://proxy.invalid:1080",
      },
      "tcp://test-host:2376": {"httpsProxy": "", "noProxy": "api.internal.invalid"},
    }


class LocalContractTests(ReleaseFixture):
  def test_validation_has_no_external_or_filesystem_effects(self):
    self.token.unlink()
    self.cert.unlink()
    self.ntfy_cert.unlink()
    before = sorted(str(path.relative_to(self.project)) for path in self.project.rglob("*"))
    self.assert_success(self.run_script("--validate"))
    self.assertEqual(self.state()["calls"], [])
    self.assertEqual(before, sorted(str(path.relative_to(self.project)) for path in self.project.rglob("*")))

  def test_missing_installer_refuses_all_modes_before_external_operations(self):
    (self.project / "scripts/install-docker.sh").unlink()
    self.assert_installer_refused_before_external_operations("Required source file is missing")

  def test_symlinked_installer_refuses_all_modes_before_external_operations(self):
    installer = self.project / "scripts/install-docker.sh"
    target = installer.with_name("installer-target.sh")
    installer.rename(target)
    installer.symlink_to(target.name)
    self.assert_installer_refused_before_external_operations("Symlink source refused")

  def assert_installer_refused_before_external_operations(self, message):
    self.token.unlink()
    self.cert.unlink()
    self.ntfy_cert.unlink()
    before = sorted(str(path.relative_to(self.root)) for path in self.root.rglob("*"))
    for args in (("--validate",), ("--build-only",), ()):
      with self.subTest(args=args):
        result = self.run_script(*args)
        self.assert_refused_without_writes(result)
        self.assertIn(message, result.stderr)
        self.assertEqual(self.state()["calls"], [])
        self.assertFalse(list(self.root.glob("dev-docker-release.*")))
        self.assertFalse((self.project / ".release-operation.lock").exists())
        self.assertEqual(before, sorted(str(path.relative_to(self.root)) for path in self.root.rglob("*")))

  def test_help_and_rejected_cli_never_call_external_ports(self):
    for args in [("--help",), ("-h",)]:
      self.assert_success(self.run_script(*args))
    mismatch = "v0.0.0" if self.tag != "v0.0.0" else "v0.0.1"
    for args in [("latest",), (mismatch,), ("one", "two"), ("--unknown",), ("--help", self.tag),
                 ("--validate", self.tag), ("--validate", "--build-only"), ("--build-only", "--build-only")]:
      with self.subTest(args=args):
        self.assert_refused_without_writes(self.run_script(*args))
    self.assertEqual(self.state()["calls"], [])

  def test_build_only_loads_two_images_with_exact_local_parents(self):
    self.assert_local_build()
    with self.subTest(version="2.4.6"):
      self.make_fixture("2.4.6")
      self.assert_local_build()

  def assert_local_build(self):
    self.assert_success(self.run_script("--build-only", self.tag))
    state = self.state()
    self.assertEqual([effect[1] for effect in state["effects"]], ["base", "npm"])
    self.assertFalse(any(call[0] == "curl" for call in state["calls"]))
    self.assertFalse(any(call[0] == "git" and "ls-remote" in call for call in state["calls"]))
    for name, _, _ in data.GRAPH:
      self.assertIn(name + ":latest", state["local_images"])
    self.assertFalse(list(self.root.glob("dev-docker-release.*")))

  def test_build_only_accepts_reversed_assertion_order(self):
    self.assert_success(self.run_script(self.tag, "--build-only"))

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
    self.assertEqual(self.state()["effects"], [["build", "base"]])
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
    self.change(fail="build:npm")
    result = self.run_script("--build-only")
    self.assertNotEqual(result.returncode, 0)
    self.assertEqual([value for kind, value in self.state()["effects"] if kind == "build"], ["base"])
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

  def test_invalid_certificates_refuse_before_external_calls_and_clean_up(self):
    for path, override in ((self.cert, "BUILD_CERT_FILE"), (self.ntfy_cert, "BUILD_NTFY_CERT_FILE")):
      original = path.read_bytes()
      for content in (None, b"", b"x" * (ports.CONFIG_LIMIT + 1)):
        for args in (("--build-only",), ()):
          with self.subTest(certificate=override, content_size=None if content is None else len(content), args=args):
            if content is None:
              path.unlink(missing_ok=True)
            else:
              path.write_bytes(content)
            result = self.run_script(*args)
            self.assert_refused_without_writes(result)
            self.assertIn(override, result.stderr)
            self.assertEqual(self.state()["calls"], [])
            self.assertFalse(list(self.root.glob("dev-docker-release.*")))
            self.assertNotIn(str(path), result.stdout + result.stderr)
      path.write_bytes(original)

  def test_host_only_docker_connection_and_relative_paths(self):
    self.env["DOCKER_HOST"] = "tcp://test-host:2376"
    self.env["DOCKER_CONFIG"] = os.path.relpath(self.docker_config, self.root)
    self.env["BUILD_CERT_FILE"] = os.path.relpath(self.cert, self.root)
    self.env["BUILD_NTFY_CERT_FILE"] = os.path.relpath(self.ntfy_cert, self.root)
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

  def test_build_only_keeps_original_proxy_configuration(self):
    config = self.docker_config / "config.json"
    original = json.dumps({"proxies": self.proxy_config()}).encode()
    config.write_bytes(original)
    self.assert_success(self.run_script("--build-only"))
    self.assertEqual(config.read_bytes(), original)
    self.assertFalse(any(kind == "login" for kind, _ in self.state()["effects"]))
    self.assertFalse(list(self.root.glob("dev-docker-release.*")))

  def test_fixture_ignores_changed_project_release_metadata(self):
    source = self.root / "changed project source"
    source.mkdir()
    for name in ("build-all.sh", ".gitignore"):
      shutil.copy(PROJECT / name, source / name)
    for name in ("scripts", "Dockerfile"):
      shutil.copytree(PROJECT / name, source / name)
    (source / "VERSION").write_text("9.8.7\n")
    settings = source / "scripts/release.json"
    config = json.loads(settings.read_text())
    config["notes"] = "docs/releases/9.8.7.md"
    settings.write_text(json.dumps(config))
    notes = source / config["notes"]
    notes.parent.mkdir(parents=True)
    notes.write_text("# Release v9.8.7\n\n- Changed project release.\n")
    self.make_fixture("2.4.6", source)
    self.assertEqual((self.project / "VERSION").read_text(), "2.4.6\n")
    self.assertEqual(json.loads((self.project / "scripts/release.json").read_text())["notes"], self.notes_path)
    self.assertFalse((self.project / config["notes"]).exists())
    self.assert_success(self.run_script("--validate"))
    self.assert_local_build()


class PublicationTests(ReleaseFixture):
  def test_publication_preserves_private_proxies_through_login_and_all_builds(self):
    proxies = self.proxy_config()
    config = self.docker_config / "config.json"
    original = json.dumps({"proxies": proxies, "auths": {"foreign": {"auth": "foreign-auth"}},
                           "credsStore": "foreign-helper", "credHelpers": {"git.lan": "foreign-helper"}}).encode()
    config.write_bytes(original)
    self.change(expected_proxy_hash=ports.sha(ports.canonical(proxies)))
    result = self.run_script()
    self.assert_success(result)
    state = self.state()
    self.assertEqual(state["proxy_checks"], 3)
    self.assertEqual(config.read_bytes(), original)
    self.assertFalse(Path(state["private_config"]).exists())
    self.assertFalse(list(self.root.glob("dev-docker-release.*")))
    self.assertNotIn("synthetic-proxy-password", result.stdout + result.stderr + json.dumps(state))
    for key, value in proxies["default"].items():
      self.assertNotIn(value, result.stdout + result.stderr)

  def test_proxy_build_failure_cleans_private_copy_without_leaking_values(self):
    proxies = self.proxy_config()
    config = self.docker_config / "config.json"
    original = json.dumps({"proxies": proxies}).encode()
    config.write_bytes(original)
    self.change(expected_proxy_hash=ports.sha(ports.canonical(proxies)), fail="build")
    result = self.run_script()
    self.assertNotEqual(result.returncode, 0)
    state = self.state()
    self.assertEqual(state["effects"], [["login", "git.lan"]])
    self.assertEqual(state["proxy_checks"], 2)
    self.assertFalse(Path(state["private_config"]).exists())
    self.assertFalse(list(self.root.glob("dev-docker-release.*")))
    self.assertEqual(config.read_bytes(), original)
    self.assertNotIn("synthetic-proxy-password", result.stdout + result.stderr + json.dumps(state))

  def test_invalid_proxy_config_refuses_before_publication_and_cleans_up(self):
    invalid = [[], "synthetic-proxy-password", {"": {}}, {"default": None}, {"default": []},
               {"default": {"unsupported": "synthetic-proxy-password"}}, {"default": {"httpsProxy": 1}},
               {"default": {"httpsProxy": False}}, {"default": {"httpsProxy": None}},
               {"default": {"httpsProxy": "synthetic-proxy-password\n"}}, {"bad\x7fendpoint": {}},
               {"default": {"noProxy": "internal\x85invalid"}}]
    documents = [json.dumps({"proxies": value}) for value in invalid]
    documents += ['{"proxies":{"default":{"httpProxy":"synthetic-proxy-password","httpProxy":"duplicate"}}}',
                  json.dumps({"proxies": {"default": {"httpsProxy": "x" * ports.CONFIG_LIMIT}}})]
    config = self.docker_config / "config.json"
    for index, content in enumerate(documents):
      with self.subTest(case=index):
        config.write_text(content)
        result = self.run_script()
        self.assert_refused_without_writes(result)
        self.assertEqual(config.read_text(), content)
        self.assertFalse(list(self.root.glob("dev-docker-release.*")))
        self.assertNotIn("synthetic-proxy-password", result.stdout + result.stderr)
        self.assertFalse(any(call[0] == "curl" for call in self.state()["calls"]))

  def test_two_image_release_and_completed_read_only_retry(self):
    self.assert_release_and_retry()
    with self.subTest(version="2.4.6"):
      self.make_fixture("2.4.6")
      self.assert_release_and_retry()

  def assert_release_and_retry(self):
    first = self.run_script(self.tag)
    self.assert_success(first)
    state = self.state()
    kinds = [effect[0] for effect in state["effects"]]
    self.assertEqual(kinds.count("build"), 2)
    self.assertEqual(kinds.count("promote"), 4)
    self.assertEqual([value for kind, value in state["effects"] if kind == "link"], ["base", "npm"])
    self.assertLess(max(index for index, kind in enumerate(kinds) if kind == "link"), kinds.index("tag"))
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

  def test_second_image_orphan_alias_and_malformed_inventory_block_all_writes(self):
    self.assert_second_image_refusals()
    with self.subTest(version="2.4.6"):
      self.make_fixture("2.4.6")
      self.assert_second_image_refusals()

  def assert_second_image_refusals(self):
    manifest = {"schemaVersion": 2, "foreign": True}
    self.change(manifests={"git.lan/dev/npm/" + self.tag: manifest})
    result = self.run_script()
    self.assert_refused_without_writes(result)
    self.assertIn("Orphan version alias", result.stderr)
    self.change(manifests={}, malformed_second=True)
    self.assert_refused_without_writes(self.run_script())

  def test_tag_only_and_release_only_refuse_without_login(self):
    self.change(tags={self.tag: "a" * 40})
    self.assert_refused_without_writes(self.run_script())
    self.change(tags={}, release={"tag_name": self.tag, "draft": False, "prerelease": False})
    self.assert_refused_without_writes(self.run_script())

  def test_staging_retry_reuses_verified_parents(self):
    self.change(fail="build:npm")
    self.assertNotEqual(self.run_script().returncode, 0)
    state = self.state()
    self.assertEqual([value for kind, value in state["effects"] if kind == "build"], ["base"])
    state.pop("fail")
    state["effects"] = []
    self.store(state)
    self.assert_success(self.run_script())
    self.assertEqual([value for kind, value in self.state()["effects"] if kind == "build"],
                     ["npm"])

  def test_matching_orphan_version_alias_is_not_adopted(self):
    self.change(fail="build:npm")
    self.assertNotEqual(self.run_script().returncode, 0)
    state = self.state()
    staged = next(value for key, value in state["manifests"].items() if "/base/stage-" in key)
    state["manifests"]["git.lan/dev/base/" + self.tag] = staged
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
    self.assertEqual(sum(kind == "promote" for kind, _ in self.state()["effects"]), 4)

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
  def test_certificate_defaults_overrides_and_empty_overrides(self):
    config = data.settings(self.project)
    self.assertEqual(config["certificate_file"], "/usr/local/share/ca-certificates/git.lanCA.crt")
    self.assertEqual(config["ntfy_certificate_file"], "/usr/local/share/ca-certificates/ntfy.lanCA.crt")
    config |= {"certificate_file": str(self.cert), "ntfy_certificate_file": str(self.ntfy_cert)}
    other_git, other_ntfy = self.root / "other git", self.root / "other ntfy"
    other_git.write_bytes(b"other-git")
    other_ntfy.write_bytes(b"other-ntfy")
    cases = [({}, self.cert.read_bytes(), self.ntfy_cert.read_bytes()),
             ({"BUILD_CERT_FILE": "", "BUILD_NTFY_CERT_FILE": ""}, self.cert.read_bytes(), self.ntfy_cert.read_bytes()),
             ({"BUILD_CERT_FILE": str(other_git)}, b"other-git", self.ntfy_cert.read_bytes()),
             ({"BUILD_NTFY_CERT_FILE": str(other_ntfy)}, self.cert.read_bytes(), b"other-ntfy"),
             ({"BUILD_CERT_FILE": str(other_git), "BUILD_NTFY_CERT_FILE": str(other_ntfy)}, b"other-git", b"other-ntfy")]
    for environment, git_value, ntfy_value in cases:
      with self.subTest(environment=environment), patch.dict(os.environ, environment, clear=True):
        self.assertEqual(data.certificates(config), {"git.lanCA.crt": git_value, "ntfy.lanCA.crt": ntfy_value})

  def test_certificate_home_expansion(self):
    config = data.settings(self.project)
    with patch.dict(os.environ, {"HOME": str(self.root), "BUILD_CERT_FILE": "~/certificate",
                                 "BUILD_NTFY_CERT_FILE": "~/ntfy certificate"}, clear=True):
      self.assertEqual(data.certificates(config), {"git.lanCA.crt": self.cert.read_bytes(),
                                                  "ntfy.lanCA.crt": self.ntfy_cert.read_bytes()})

  def test_certificate_read_errors_are_sanitized(self):
    config = data.settings(self.project)
    for override, path in (("BUILD_CERT_FILE", self.cert), ("BUILD_NTFY_CERT_FILE", self.ntfy_cert)):
      def denied(candidate, limit):
        if candidate == path:
          raise PermissionError("private-certificate-path-and-content")
        return ports.read(candidate, limit)
      with self.subTest(override=override), patch.dict(os.environ, self.env, clear=True), patch.object(data, "read", side_effect=denied):
        with self.assertRaises(ports.Refusal) as caught:
          data.certificates(config)
        self.assertIn(override, str(caught.exception))
        self.assertNotIn("private-certificate", str(caught.exception))
        self.assertNotIn(str(path), str(caught.exception))

  def test_certificate_fingerprint_binds_names_and_both_contents(self):
    values = {"git.lanCA.crt": self.cert.read_bytes(), "ntfy.lanCA.crt": self.ntfy_cert.read_bytes()}
    expected = ports.sha(ports.canonical({name: ports.sha(value) for name, value in values.items()}))
    self.assertEqual(data.certificate_fingerprint(values), expected)
    self.assertEqual(data.certificate_fingerprint(dict(reversed(list(values.items())))), expected)
    for name in values:
      with self.subTest(certificate=name):
        self.assertNotEqual(data.certificate_fingerprint(values | {name: b"changed"}), expected)
    swapped = {"git.lanCA.crt": values["ntfy.lanCA.crt"], "ntfy.lanCA.crt": values["git.lanCA.crt"]}
    self.assertNotEqual(data.certificate_fingerprint(swapped), expected)

  def test_guard_rejects_either_changed_certificate_before_inventory(self):
    work = self.root / "private"
    work.mkdir(mode=0o700)
    with patch.dict(os.environ, self.env, clear=True), patch.object(data, "source"), patch.object(data, "inventory") as inventory:
      data.init(self.project, work, "local")
      config = ports.document(work / "settings.json") | {"commit": self.state()["commit"]}
      data.unchanged(self.project, work, config)
      for path in (self.cert, self.ntfy_cert):
        original = path.read_bytes()
        with self.subTest(certificate=path.name):
          path.write_bytes(b"changed")
          self.assertRaisesRegex(ports.Refusal, "Build certificate changed", data.guard, self.project, work, config)
          inventory.assert_not_called()
          path.write_bytes(original)
      data.unchanged(self.project, work, config)

  def test_snapshots_use_captured_bytes_for_local_and_publication(self):
    originals = {"git.lanCA.crt": self.cert.read_bytes(), "ntfy.lanCA.crt": self.ntfy_cert.read_bytes()}
    for local in (True, False):
      with self.subTest(local=local):
        self.cert.write_bytes(originals["git.lanCA.crt"])
        self.ntfy_cert.write_bytes(originals["ntfy.lanCA.crt"])
        work = self.root / ("local-snapshot" if local else "publish-snapshot")
        work.mkdir(mode=0o700)
        with patch.dict(os.environ, self.env, clear=True):
          data.init(self.project, work, "local")
        config = ports.document(work / "settings.json") | {"commit": self.state()["commit"]}
        self.cert.write_bytes(b"changed-git")
        self.ntfy_cert.write_bytes(b"changed-ntfy")
        data.snapshot(self.project, work, config, local)
        context = work / "context"
        self.assertEqual(sorted(path.name for path in context.iterdir()), ["Dockerfile", *sorted(originals), "scripts"])
        self.assertEqual([path.name for path in (context / "scripts").iterdir()], ["install-docker.sh"])
        for name, value in originals.items():
          self.assertEqual((context / name).read_bytes(), value)
        self.assertEqual(config["certificate_hash"], data.certificate_fingerprint(originals))
        self.assertEqual(data.labels_for(config)["dev.docker.release.certificate"], config["certificate_hash"])

  def test_installer_snapshot_uses_worktree_locally_and_selected_commit_for_publication(self):
    installer = self.project / "scripts/install-docker.sh"
    committed = installer.read_bytes()
    installer.write_bytes(committed + b"\n# Working-tree change\n")
    for local in (True, False):
      with self.subTest(local=local):
        work = self.root / ("local-installer" if local else "published-installer")
        work.mkdir(mode=0o700)
        with patch.dict(os.environ, self.env, clear=True):
          data.init(self.project, work, "local")
        config = ports.document(work / "settings.json") | {"commit": self.state()["commit"]}
        data.snapshot(self.project, work, config, local)
        captured = work / "context/scripts/install-docker.sh"
        self.assertEqual(captured.read_bytes(), installer.read_bytes() if local else committed)
        self.assertEqual([path.name for path in captured.parent.iterdir()], ["install-docker.sh"])

  def test_base_dockerfile_copies_both_certificates_before_trust_update(self):
    content = (self.project / "Dockerfile/base.Dockerfile").read_text()
    for name in ("git.lanCA.crt", "ntfy.lanCA.crt"):
      with self.subTest(certificate=name):
        copy = "COPY " + name + " /usr/local/share/ca-certificates/" + name + "\n"
        self.assertIn(copy, content)
        self.assertLess(content.index(copy), content.index("update-ca-certificates"))

  def test_proxy_maps_preserve_literal_values_without_merging(self):
    complete = self.proxy_config()
    for proxies in ({}, {"default": {}}, {"default": complete["default"]},
                    {"tcp://test-host:2376": complete["tcp://test-host:2376"]}, complete):
      with self.subTest(endpoints=list(proxies)):
        self.assertEqual(data.docker_proxies(proxies), proxies)
    self.assertIsNone(data.docker_proxies(None))

  def test_private_proxy_config_handles_missing_null_empty_and_default_config_paths(self):
    home = self.root / "test home"
    home.mkdir()
    original = home / ".docker"
    original.mkdir()
    cases = [("missing", None), ("no proxies", {}), ("null", {"proxies": None}),
             ("empty", {"proxies": {}}), ("configured", {"proxies": self.proxy_config()})]
    for index, (name, content) in enumerate(cases):
      with self.subTest(case=name):
        source = original / "config.json"
        if content is not None:
          source.write_text(json.dumps(content))
        before = source.read_bytes() if source.exists() else None
        work = self.root / ("private-" + str(index))
        work.mkdir(mode=0o700)
        environment = {"HOME": str(home)}
        if index % 2:
          environment["DOCKER_CONFIG"] = ""
        with patch.dict(os.environ, environment, clear=True), patch.object(data, "command", return_value=b"default\n"):
          data.docker_auth(work)
        actual = json.loads((work / "docker/config.json").read_text())
        if content is not None and content.get("proxies") is not None:
          self.assertEqual(actual["proxies"], content["proxies"])
        else:
          self.assertNotIn("proxies", actual)
        self.assertEqual(source.read_bytes() if source.exists() else None, before)
        self.assertEqual(stat.S_IMODE((work / "docker").stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE((work / "docker/config.json").stat().st_mode), 0o600)

  def test_settings_reject_unknown_duplicate_traversal_and_changed_graph(self):
    path = self.project / "scripts/release.json"
    original = path.read_text()
    mutations = [original.replace('"schema": 1', '"schema": 1, "unknown": 1'),
                 original.replace('"schema": 1', '"schema": 1, "schema": 1'),
                 original.replace(self.notes_path, '../outside.md'),
                 original.replace('"parent": "base"', '"parent": "android"')]
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
      "credsStore": "helper", "credHelpers": {"git.lan": "helper"}, "cliPluginsExtraDirs": [str(plugins)],
      "proxies": self.proxy_config()}))
    original = (self.docker_config / "config.json").read_bytes()
    work = self.root / "private"
    work.mkdir(mode=0o700)
    relative = os.path.relpath(self.docker_config)
    with patch.dict(os.environ, self.env | {"DOCKER_CONTEXT": "selected", "DOCKER_CONFIG": relative}):
      data.docker_auth(work)
    config = json.loads((work / "docker/config.json").read_text())
    self.assertEqual(config["auths"], {})
    self.assertEqual(config["currentContext"], "selected")
    self.assertNotIn("credsStore", config)
    self.assertNotIn("credHelpers", config)
    self.assertEqual((work / "docker/cli-plugins").resolve(), plugins)
    self.assertEqual(config["cliPluginsExtraDirs"], [str(plugins)])
    self.assertEqual(config["proxies"], self.proxy_config())
    self.assertEqual((self.docker_config / "config.json").read_bytes(), original)
    self.assertEqual(stat.S_IMODE((work / "docker").stat().st_mode), 0o700)
    self.assertEqual(stat.S_IMODE((work / "docker/config.json").stat().st_mode), 0o600)

  def test_bounded_capture_refuses_overflow_and_drains_both_pipes(self):
    self.assertRaises(ports.Refusal, ports.command, [sys.executable, "-c", "print('x'*101)"], 100)
    value = ports.command([sys.executable, "-c", "import sys; sys.stderr.write('e'*65536); print('ok')"], 100)
    self.assertEqual(value, b"ok\n")

  def test_registry_foreign_token_realm_refused(self):
    from unittest.mock import patch
    with patch.object(ports, "http", return_value=(401, {"www-authenticate": 'Bearer realm="https://foreign/token"'}, b"")) as http:
      self.assertRaises(ports.Refusal, ports.registry, self.root, "https://git.lan", "git.lan/dev/base", "manifests", "latest")
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
