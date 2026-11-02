#!/usr/bin/env python3
"""Stateful command ports for offline release tests; never contact services."""

import base64
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import time
from urllib.parse import parse_qs, unquote, urlsplit


path = Path(os.environ["TEST_STATE"])
state = json.loads(path.read_text())
args = sys.argv[1:]
tool = Path(sys.argv[0]).name
state["calls"].append([tool, *args])


def save():
  path.write_text(json.dumps(state))


def encoded(value):
  return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def digest(value):
  return "sha256:" + hashlib.sha256(value).hexdigest()


def die():
  save()
  sys.exit(9)


def effect(kind, value):
  state["effects"].append([kind, value])
  if kind == "link":
    state.update(state.get("after_link", {}))
  if state.get("lose_response") == kind:
    state.pop("lose_response")
    die()


def option(name):
  return args[args.index(name) + 1]


def publish_version(name, version):
  package = state["packages"].setdefault(name, {"versions": [], "repository": None})
  if version not in package["versions"]:
    package["versions"].append(version)


def package_versions(name):
  # Contract fixtures: upstream v1.24.7 and v28.2.0 ToPackage uses Version.ID,
  # filters repository visibility, and keeps the link shared by all versions.
  package = state["packages"].get(name)
  if package is None:
    return []
  repository = None if state.get("hide_links") else package["repository"]
  identities = state.setdefault("package_version_ids", {})
  for version in package["versions"]:
    key = json.dumps([name, version])
    if key not in identities:
      identities[key] = max(identities.values(), default=0) + 1
  return [{"id": identities[json.dumps([name, version])], "name": name, "type": "container", "version": version,
           "owner": state["namespace"], "repository": repository}
          for version in package["versions"]]


def verify_proxy_config():
  if "expected_proxy_hash" not in state:
    return
  directory = Path(os.environ["DOCKER_CONFIG"])
  config = json.loads((directory / "config.json").read_text())
  assert digest(encoded(config.get("proxies"))) == state["expected_proxy_hash"], "Private proxy configuration differs"
  assert "credsStore" not in config and "credHelpers" not in config, "Caller registry helper leaked"
  assert stat.S_IMODE(directory.stat().st_mode) == 0o700, "Private config directory permissions differ"
  assert stat.S_IMODE((directory / "config.json").stat().st_mode) == 0o600, "Private config permissions differ"
  state["proxy_checks"] = state.get("proxy_checks", 0) + 1


if tool == "git":
  actual = args[2:] if args[:1] == ["-C"] else args
  if actual[:2] == ["remote", "get-url"]:
    print(state.get("remote", "ssh://git@git.lan/dev/dev-docker.git"))
  elif actual[:1] == ["ls-remote"]:
    if "--tags" in actual:
      for tag, oid in state["tags"].items():
        print(oid + "\trefs/tags/" + tag)
        print(state["commit"] + "\trefs/tags/" + tag + "^{}")
    else:
      print(state.get("remote_commit", state["commit"]) + "\trefs/heads/main")
  elif actual[:1] == ["fetch"]:
    pass  # mktag created the immutable object in this temporary repository.
  elif actual[:1] == ["push"]:
    oid, ref = actual[-1].split(":", 1)
    state["tags"][ref.removeprefix("refs/tags/")] = oid
    effect("tag", ref)
  else:
    save()
    os.execv(os.environ["REAL_GIT"], [os.environ["REAL_GIT"], *args])
elif tool == "docker":
  if args[:2] == ["buildx", "version"]:
    print("github.com/docker/buildx v0.20.0 test")
  elif args[:3] == ["buildx", "inspect", "--bootstrap"]:
    print("Name: test\nDriver: " + state.get("driver", "docker") + "\nNodes:\nName: test0\nEndpoint: " +
          state.get("endpoint", os.environ.get("DOCKER_CONTEXT") or "default") +
          "\nPlatforms: " + state.get("platforms", "linux/amd64"))
  elif args[:2] == ["context", "show"]:
    config_path = Path(os.environ.get("DOCKER_CONFIG") or str(Path.home() / ".docker")) / "config.json"
    config = json.loads(config_path.read_text()) if config_path.exists() else {}
    print(os.environ.get("DOCKER_CONTEXT") or config.get("currentContext", "default"))
  elif args[:2] == ["context", "inspect"]:
    print(json.dumps([{"Endpoints": {"docker": {"Host": state.get("host", "unix:///var/run/docker.sock")}}}]))
  elif args[:1] == ["login"]:
    verify_proxy_config()
    if state.get("fail") == "login":
      die()
    assert sys.stdin.read() == state.get("token", "test-secret")
    directory = Path(os.environ["DOCKER_CONFIG"])
    config = json.loads((directory / "config.json").read_text())
    assert "credsStore" not in config and "credHelpers" not in config
    config["auths"] = {"git.lan": {"auth": base64.b64encode(b"dev:test-secret").decode()}}
    (directory / "config.json").write_text(json.dumps(config))
    state["private_config"] = str(directory)
    state["buildx_config"] = os.environ.get("BUILDX_CONFIG")
    effect("login", "git.lan")
  elif args[:2] == ["buildx", "build"]:
    verify_proxy_config()
    assert "--progress=plain" in args
    name = option("--tag")
    short = name.split("/")[-1].split(":")[0]
    print("#1 building " + short, flush=True)
    print("#2 running setup for " + short, file=sys.stderr, flush=True)
    for marker in state.get("build_log_markers", []):
      print("#3 diagnostic " + marker + " end", file=sys.stderr, flush=True)
    if state.get("fail") in ("build", "build:" + short):
      print("ERROR: synthetic setup instruction failed", file=sys.stderr, flush=True)
      die()
    if state.get("pause_build"):
      save()
      Path(os.environ["TEST_STATE"] + ".started").touch()
      time.sleep(60)
    labels = {args[index + 1].split("=", 1)[0]: args[index + 1].split("=", 1)[1]
              for index, value in enumerate(args) if value == "--label"}
    context = Path(args[-1])
    assert (context / "git.lanCA.crt").read_text() == "test-certificate\n"
    assert (context / "ntfy.lanCA.crt").read_text() == "test-ntfy-certificate\n"
    assert sorted(item.name for item in context.iterdir()) == ["Dockerfile", "git.lanCA.crt", "ntfy.lanCA.crt", "scripts"]
    assert sorted(item.name for item in (context / "scripts").iterdir()) == ["install-docker.sh"]
    assert (context / "scripts/install-docker.sh").read_bytes()
    assert "test-secret" not in " ".join(args)
    assert not (context / "token").exists()
    if short == "base":
      secret = option("--secret")
      assert secret.startswith("id=token,src=")
      assert Path(secret.split("src=", 1)[1]).read_text() == state.get("token", "test-secret")
    else:
      reference = option("--build-arg").split("=", 1)[1]
      if "--load" in args:
        assert reference in state["local_images"], "Child used an unverified parent"
        assert labels["dev.docker.release.parent"] == state["local_images"][reference]["Id"]
      else:
        assert "@sha256:" in reference, "Release child used a mutable parent"
        assert reference.replace("@", "/") in state["manifests"]
    content = {"os": "linux", "architecture": "amd64", "config": {"Labels": labels}, "fixture_image": short}
    config_digest = digest(encoded(content))
    manifest = {"schemaVersion": 2, "mediaType": "application/vnd.oci.image.manifest.v1+json",
                "config": {"digest": config_digest}, "layers": []}
    prepared = digest(encoded(manifest))
    if "--load" in args:
      local = {"Os": "linux", "Architecture": "amd64", "Id": config_digest, "Config": {"Labels": labels}}
      state["local_images"][name] = local
      state["local_images"][config_digest] = local
      if state.get("wrong_parent") and short == "base":
        state["local_images"][name]["Id"] = "sha256:" + "f" * 64
    else:
      image, tag = name.rsplit(":", 1)
      state["manifests"][image + "/" + tag] = manifest
      state["manifests"][image + "/" + prepared] = manifest
      state["blobs"][image + "/" + config_digest] = content
      publish_version(short, tag)
    Path(option("--metadata-file")).write_text(json.dumps({"containerimage.digest": prepared,
                                                          "containerimage.config.digest": config_digest}))
    effect("build", short)
    if short == "npm":
      state.update(state.get("after_staging", {}))
  elif args[:2] == ["image", "inspect"]:
    print(json.dumps([state["local_images"][args[-1]]]))
  elif args[:3] == ["buildx", "imagetools", "create"]:
    assert "--progress=plain" not in args
    target = option("--tag")
    image, alias = target.rsplit(":", 1)
    manifest = state["manifests"][args[-1].replace("@", "/")]
    if state.get("fail") == "promote":
      die()
    state["manifests"][image + "/" + alias] = manifest
    publish_version(image.rsplit("/", 1)[-1], alias)
    effect("promote", target)
    if state.get("revert_promoted") and alias == "latest":
      # Simulate another writer after a confirmed promotion: the next inventory
      # read triggers the change, so confirm-alias sees the accepted write first.
      state["revert_pending"] = [image + "/latest", 2]
  else:
    raise AssertionError("Unexpected Docker command: " + repr(args))
elif tool == "curl":
  assert args[0] == "-q" and "--location" not in args and "-L" not in args
  url = urlsplit(args[-1])
  method = option("--request")
  route = unquote(url.path)
  code, body = 200, []
  if route in state.get("responses", {}):
    response = state["responses"][route]
    code, body = response.get("code", 200), response.get("body")
    if "raw" in response:
      body = response["raw"].encode()
    if response.get("transport_failure"):
      die()
  elif route == "/api/v1/version":
    body = state["server_version"]
  elif route == "/api/v1/user":
    body = state["principal"]
  elif route == "/api/v1/users/dev":
    body = state["namespace"]
  elif route == "/api/v1/repos/dev/dev-docker":
    body = state["repository"]
  elif route == "/api/v1/packages/dev":
    assert method == "GET"
    query = parse_qs(url.query)
    assert query["type"] == ["container"] and query["limit"] == ["100"]
    name, page = query["q"][0], int(query["page"][0])
    records = [record for package in sorted(state["packages"]) if name.lower() in package.lower()
               for record in package_versions(package)]
    body = records[(page - 1) * 100:page * 100]
  elif route.startswith("/api/v1/packages/dev/container/"):
    parts = route.split("/")
    name = parts[6]
    if method == "POST":
      assert parts[7:] == ["-", "link", "dev-docker"], "Unlink/deletion is never authorized"
      package = state["packages"].get(name)
      if package is None:
        code = 404
      elif package["repository"] is not None:
        code = 400  # LinkToRepository refuses an existing association.
      elif state["namespace"]["id"] != state["repository"]["owner"]["id"]:
        code = 403
      elif state.get("fail") in ("link", "link:" + name):
        die()
      else:
        package["repository"] = state["repository"]
        code, body = 201, b""
        effect("link", name)
    else:
      assert method == "GET" and len(parts) == 7, "Only exact version listing is used"
      page = int(parse_qs(url.query)["page"][0])
      records = state.get("package_records", {}).get(name, package_versions(name))
      body = records[(page - 1) * 100:page * 100]
      # v28 middleware resolves the named package before listing its versions;
      # v1.24.7 only resolves descriptors for version-specific paths.
      if name not in state["packages"] and state["server_version"]["version"] == "28.2.0":
        code, body = 404, {"message": "package does not exist"}
      if state.get("repeat_package_page"):
        body = records[:100]
  elif route.startswith("/api/v1/repos/dev/dev-docker/releases"):
    if method == "POST":
      if state.get("fail") == "post":
        die()
      body = json.loads(Path(option("--data-binary")[1:]).read_text())
      state["release"] = body
      code = 201
      effect("post", "release")
    else:
      body = [state["release"]] if state.get("release") and parse_qs(url.query).get("page") == ["1"] else []
  elif route.startswith("/api/v1/repos/dev/dev-docker/tags"):
    body = [{"name": name} for name in state["tags"]] if parse_qs(url.query).get("page") == ["1"] else []
  elif route.startswith("/v2/"):
    repository, kind, reference = route[4:].rsplit("/", 2)
    key = "git.lan/" + repository + "/" + reference
    if state.get("revert_pending") and state["revert_pending"][0] == key:
      state["revert_pending"][1] -= 1
      if state["revert_pending"][1] == 0:
        state["manifests"].pop(key, None)
        state.pop("revert_pending")
        state.pop("revert_promoted", None)
    body = state["manifests" if kind == "manifests" else "blobs"].get(key)
    if body is None:
      code, body = 404, {"errors": [{"code": "MANIFEST_UNKNOWN"}]}
    if state.get("malformed_second") and key == "git.lan/dev/npm/" + state["release_tag"]:
      body = b"not json"
  else:
    raise AssertionError("Unexpected HTTP route")
  value = body if isinstance(body, bytes) else encoded(body)
  headers = "HTTP/1.1 " + str(code) + " OK\r\n"
  if code == 200 and route.startswith("/v2/"):
    headers += "Docker-Content-Digest: " + digest(value) + "\r\n"
  Path(option("--dump-header")).write_text(headers + "\r\n")
  Path(option("--output")).write_bytes(value)
  print(code, end="")
else:
  raise AssertionError("Unexpected command port")
save()
