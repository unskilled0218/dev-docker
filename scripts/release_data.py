#!/usr/bin/env python3
"""Strict release data and state checks. Bash owns the mutation sequence.

Based on container-release-template 0.4.0 at
1d051b36888fd64d9bfcd49e8e09f504943b6a1a; adapted for one five-image release.
"""

import base64
import fcntl
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import signal
import stat
import subprocess
import sys
import time
from urllib.parse import urlencode, urlsplit

import release_io
from release_io import (API_LIMIT, CONFIG_LIMIT, REF_LIMIT, SMALL_LIMIT, CommandFailed,
                        Refusal, canonical, command, decode, document, git, http,
                        locked, read, registry, require, sha, write)


MARKER = b"dev-docker-release/1\n"
GRAPH = [
  ("my-base", "base", None), ("npm-non-root", "npm", "my-base"),
  ("android-dev", "android", "npm-non-root"), ("tauri-dev", "tauri", "android-dev"),
  ("switchboard", "switchboard", "android-dev"),
]


def digest(value):
  return isinstance(value, str) and re.fullmatch(r"sha256:[0-9a-f]{64}", value) is not None


def text(value):
  return isinstance(value, str) and value and not re.search(r"[\x00-\x1f\x7f]", value)


def regular(root, name):
  require(text(name) and not PurePosixPath(name).is_absolute() and
          ".." not in PurePosixPath(name).parts, "Unsafe source path")
  root, path = Path(root).resolve(), Path(root) / name
  require(path.resolve().is_relative_to(root), "Source path escapes project")
  relative = path.relative_to(root)
  require(all(not (root / Path(*relative.parts[:index])).is_symlink()
              for index in range(1, len(relative.parts) + 1)), "Symlink source refused")
  require(path.is_file(), "Required source file is missing")
  return path


def semver(value):
  require(isinstance(value, str) and len(value) <= 16 and
          re.fullmatch(r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)", value),
          "Version must be MAJOR.MINOR.PATCH, at most 16 characters")
  return tuple(map(int, value.split(".")))


def normalized_notes(value, tag):
  result = value.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n").rstrip("\n") + "\n"
  require(result.startswith("# Release " + tag + "\n") and len(result.splitlines()) > 2 and
          "\x00" not in result, "Release notes heading/content differs")
  return result


def settings(root):
  config = document(regular(root, "scripts/release.json"), SMALL_LIMIT)
  fields = {"schema", "gitea", "repository", "username", "token_file", "certificate_file", "notes", "platforms", "images"}
  require(isinstance(config, dict) and set(config) == fields and type(config["schema"]) is int and
          config["schema"] == 1, "Invalid release configuration fields")
  require(all(text(config[key]) for key in fields - {"schema", "platforms", "images"}), "Invalid setting string")
  require(re.fullmatch(r"https://[a-z0-9.-]+(?::[0-9]+)?", config["gitea"]), "Expected credential-free HTTPS origin")
  origin = urlsplit(config["gitea"])
  require(origin.hostname and origin.port != 0, "Invalid HTTPS origin")
  name = r"[a-z0-9][a-z0-9._-]*"
  require(re.fullmatch(name + "/" + name, config["repository"]), "Invalid repository")
  require(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", config["username"]), "Invalid login")
  require(config["platforms"] == ["linux/amd64"], "Only linux/amd64 is supported")
  expected = [{"name": name, "dockerfile": "Dockerfile/" + file + ".Dockerfile", "parent": parent}
              for name, file, parent in GRAPH]
  require(config["images"] == expected, "Expected the ordered five-image dependency graph")
  for item in expected:
    content = read(regular(root, item["dockerfile"])).decode()
    if item["parent"]:
      require(content.startswith("ARG BASE_IMAGE=" + item["parent"] + ":latest\nFROM ${BASE_IMAGE}\n"),
              "Dockerfile parent differs from configured graph")
  version = read(regular(root, "VERSION"), 128).decode().strip()
  semver(version)
  tag = "v" + version
  normalized_notes(read(regular(root, config["notes"]), SMALL_LIMIT), tag)
  scripts = ("build-all.sh", "scripts/release_data.py", "scripts/release_io.py")
  script_hash = sha(b"".join(name.encode() + b"\x00" + read(regular(root, name)) for name in scripts))
  owner = config["repository"].split("/")[0]
  return config | {"version": version, "tag": tag, "script_hash": script_hash,
                   "config_hash": sha(read(root / "scripts/release.json", SMALL_LIMIT)),
                   "prefix": origin.netloc + "/" + owner}


def remote_key(value):
  require(text(value), "Invalid Git destination")
  if re.fullmatch(r"[^/@:]+@[^/:]+:[^\s]+", value):
    host, repository = value.split("@", 1)[1].split(":", 1)
    return host.lower(), repository.removesuffix(".git")
  parts = urlsplit(value)
  require(parts.scheme in ("ssh", "https") and parts.hostname and not parts.password and
          not parts.query and not parts.fragment and (parts.scheme != "https" or not parts.username),
          "Invalid Git destination")
  host = parts.hostname.lower()
  if parts.scheme == "https" and parts.port not in (None, 443):
    host += ":" + str(parts.port)
  return host, parts.path.lstrip("/").removesuffix(".git")


def source(root, config, expected=None):
  require(git(root, "branch", "--show-current").strip() == b"main", "Publication requires main")
  require(not git(root, "status", "--porcelain", "--untracked-files=all"), "Publication requires a clean checkout")
  git(root, "check-ignore", "--quiet", ".release-operation.lock")
  origin = urlsplit(config["gitea"])
  for arguments in (("remote", "get-url", "--all", "origin"), ("remote", "get-url", "--push", "--all", "origin")):
    destinations = git(root, *arguments).decode().splitlines()
    require(len(destinations) == 1, "Require exactly one fetch and push destination")
    destination = destinations[0]
    ssh = destination.startswith("ssh://") or re.fullmatch(r"[^/@:]+@[^/:]+:[^\s]+", destination)
    host = origin.hostname
    if not ssh and origin.port not in (None, 443):
      host += ":" + str(origin.port)
    require(remote_key(destination) == (host, config["repository"]), "Git destination differs from configured target")
  commit = git(root, "rev-parse", "HEAD").decode().strip()
  require(re.fullmatch(r"[0-9a-f]{40}", commit) and (expected is None or commit == expected), "Captured source changed")
  require(git(root, "ls-remote", "origin", "refs/heads/main").decode().split() == [commit, "refs/heads/main"],
          "Remote main differs; push source separately")
  return commit


def blob(root, commit, name, limit=API_LIMIT):
  regular(root, name)
  tree = git(root, "--literal-pathspecs", "ls-tree", "-z", commit, "--", name, limit=SMALL_LIMIT)
  entries = tree.rstrip(b"\0").split(b"\0")
  require(len(entries) == 1 and b"\t" in entries[0], "Expected regular committed source blob")
  fields, filename = entries[0].split(b"\t", 1)
  mode, kind, oid = fields.decode().split()
  require(mode in ("100644", "100755") and kind == "blob" and filename.decode() == name,
          "Expected regular committed source blob")
  require(int(git(root, "cat-file", "-s", oid)) <= limit, "Committed blob exceeds bound")
  return git(root, "cat-file", "blob", oid, limit=limit)


def init(root, work, mode):
  config = settings(root)
  cert = Path(os.environ.get("BUILD_CERT_FILE") or config["certificate_file"]).expanduser()
  require(cert.is_file(), "Existing build certificate required; set BUILD_CERT_FILE")
  value = read(cert, CONFIG_LIMIT)
  require(value, "Build certificate is empty")
  (work / "certificate").write_bytes(value)
  config["certificate_hash"] = sha(value)
  if mode == "publish":
    config["commit"] = source(root, config)
    config["body"] = normalized_notes(blob(root, config["commit"], config["notes"], SMALL_LIMIT), config["tag"])
  write(work / "settings.json", config)
  write(work / "state.json", {"digests": {}, "predecessors": {}, "versions": {}, "latest": {}, "oid": None})


def credentials(root, work, config):
  username = os.environ.get("GIT_USERNAME") or os.environ.get("FORGEJO_USERNAME") or config["username"]
  require(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", username), "Invalid login override")
  token_path = Path(os.environ.get("GIT_TOKEN") or os.environ.get("FORGEJO_TOKEN_FILE") or config["token_file"]).expanduser()
  if not token_path.is_absolute():
    token_path = root / token_path
  require(not token_path.resolve().is_relative_to(root.resolve()), "Keep credentials outside project")
  require(all(not parent.is_symlink() for parent in (token_path, *token_path.parents)), "Token symlink refused")
  descriptor = os.open(token_path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
  with os.fdopen(descriptor, "rb") as source_file:
    metadata = os.fstat(source_file.fileno())
    require(stat.S_ISREG(metadata.st_mode) and metadata.st_uid == os.getuid() and
            stat.S_IMODE(metadata.st_mode) in (0o400, 0o600), "Token must be user-owned mode 0400 or 0600")
    raw = source_file.read(4097)
    require(len(raw) <= 4096, "Token file exceeds size bound")
    token = raw.decode().strip()
  require(len(token) <= 4096 and re.fullmatch(r"[A-Za-z0-9._~-]+", token), "Invalid private token file")
  (work / "token").write_text(token)
  (work / "login").write_text(username)
  (work / "api.curl").write_text('header = "Authorization: token ' + token + '"\n')
  basic = base64.b64encode((username + ":" + token).encode()).decode()
  (work / "registry.curl").write_text('header = "Authorization: Basic ' + basic + '"\n')


def docker_proxies(value):
  """Validate proxy data without interpreting Docker's endpoint selection policy."""
  if value is None:
    return None
  message = "Invalid Docker proxy configuration"
  require(isinstance(value, dict), message)
  fields = {"httpProxy", "httpsProxy", "ftpProxy", "noProxy", "allProxy"}
  def safe_string(item):
    return isinstance(item, str) and not re.search(r"[\x00-\x1f\x7f-\x9f]", item)
  for endpoint, proxies in value.items():
    require(safe_string(endpoint) and endpoint, message)
    require(isinstance(proxies, dict) and set(proxies) <= fields, message)
    require(all(safe_string(item) for item in proxies.values()), message)
  return {endpoint: dict(proxies) for endpoint, proxies in value.items()}


def docker_auth(work):
  """Keep validated build/connection settings, never caller registry auth/helpers."""
  original = Path(os.environ.get("DOCKER_CONFIG") or str(Path.home() / ".docker")).resolve()
  previous = document(original / "config.json", CONFIG_LIMIT) if (original / "config.json").is_file() else {}
  require(isinstance(previous, dict), "Invalid original Docker configuration")
  proxies = docker_proxies(previous.get("proxies"))
  extra = previous.get("cliPluginsExtraDirs", [])
  require(isinstance(extra, list) and all(text(path) for path in extra), "Invalid plugin search directories")
  context = command(["docker", "context", "show"], SMALL_LIMIT).decode().strip()
  require(text(context), "Invalid Docker context selection")
  private = work / "docker"
  private.mkdir(mode=0o700)
  config = {"auths": {}}
  if proxies is not None:
    config["proxies"] = proxies
  if context != "default" or os.environ.get("DOCKER_CONTEXT"):
    config["currentContext"] = context
  if (original / "contexts").is_dir():
    shutil.copytree(original / "contexts", private / "contexts")
  # Docker discovers config-local plugins here. Keep the same executable search path.
  if (original / "cli-plugins").is_dir():
    (private / "cli-plugins").symlink_to(original / "cli-plugins", target_is_directory=True)
  if (original / "config.json").is_file():
    config["cliPluginsExtraDirs"] = [str(Path(path).absolute()) for path in extra]
  write(private / "config.json", config)
  (private / "config.json").chmod(0o600)


def builder(work, local):
  output = command(["docker", "buildx", "inspect", "--bootstrap"], CONFIG_LIMIT).decode()
  platforms = {item.strip().rstrip("*") for line in re.findall(r"^\s*Platforms:\s*(.+)$", output, re.M)
               for item in line.split(",")}
  require("linux/amd64" in platforms, "Builder must advertise linux/amd64")
  if local:
    drivers = re.findall(r"^Driver:\s*(\S+)\s*$", output, re.M)
    require(drivers == ["docker"], "Build-only requires a selected Docker-driver builder; select one explicitly")
    endpoints = re.findall(r"^\s*Endpoint:\s*(\S+)\s*$", output, re.M)
    context = command(["docker", "context", "show"], SMALL_LIMIT).decode().strip()
    connection = decode(command(["docker", "context", "inspect", context], CONFIG_LIMIT))
    require(isinstance(connection, list) and len(connection) == 1, "Cannot verify Docker endpoint")
    endpoint = connection[0]["Endpoints"]["docker"]["Host"]
    if not os.environ.get("DOCKER_CONTEXT") and context == "default" and os.environ.get("DOCKER_HOST"):
      endpoint = os.environ["DOCKER_HOST"]
    require(len(endpoints) == 1 and endpoints[0] in (context, endpoint), "Builder and local image store differ")
  (work / "builder").write_text(output)
  (work / "buildx-version").write_bytes(command(["docker", "buildx", "version"], SMALL_LIMIT))


def verify_builder(work):
  require(command(["docker", "buildx", "version"], SMALL_LIMIT) == read(work / "buildx-version", SMALL_LIMIT),
          "Buildx plugin changed during auth isolation")
  output = command(["docker", "buildx", "inspect", "--bootstrap"], CONFIG_LIMIT).decode()
  def selection(value):
    return re.findall(r"^\s*(Name|Driver|Endpoint|Platforms):\s*(.+)$", value, re.M)
  require(selection(output) == selection(read(work / "builder").decode()), "Selected builder changed during auth isolation")


def full_image(config, name):
  require(name in [item[0] for item in GRAPH], "Unknown release image")
  return config["prefix"] + "/" + name


def resolve(work, config, name, reference):
  result = registry(work, config["gitea"], full_image(config, name), "manifests", reference, True)
  return result[0] if result else None


def image(work, config, name, reference):
  result = registry(work, config["gitea"], full_image(config, name), "manifests", reference)
  root_digest, manifest = result
  require(isinstance(manifest, dict) and manifest.get("schemaVersion") == 2, "Invalid image manifest")
  media = manifest.get("mediaType")
  if media in ("application/vnd.oci.image.index.v1+json", "application/vnd.docker.distribution.manifest.list.v2+json"):
    members = manifest.get("manifests")
    require(isinstance(members, list) and len(members) == 1, "Expected one AMD64 image without attestations")
    member = members[0]
    require(isinstance(member, dict) and member.get("platform") == {"architecture": "amd64", "os": "linux"} and
            digest(member.get("digest")), "Unexpected index platform")
    _, manifest = registry(work, config["gitea"], full_image(config, name), "manifests", member["digest"])
  require(isinstance(manifest, dict) and manifest.get("schemaVersion") == 2 and
          manifest.get("mediaType") in ("application/vnd.oci.image.manifest.v1+json", "application/vnd.docker.distribution.manifest.v2+json") and
          isinstance(manifest.get("config"), dict) and digest(manifest["config"].get("digest")), "Invalid platform manifest")
  _, content = registry(work, config["gitea"], full_image(config, name), "blobs", manifest["config"]["digest"])
  require(isinstance(content, dict) and content.get("os") == "linux" and content.get("architecture") == "amd64",
          "Image configuration platform differs")
  labels = content.get("config", {}).get("Labels", {})
  require(isinstance(labels, dict) and all(labels.get(key) == value for key, value in labels_for(config).items()),
          "Image labels differ from captured identity")
  parent = next(item[2] for item in GRAPH if item[0] == name)
  if parent:
    state = document(work / "state.json")
    require(labels.get("dev.docker.release.parent") == full_image(config, parent) + "@" + state["digests"][parent],
            "Image parent identity differs")
  return root_digest


def labels_for(config):
  return {"org.opencontainers.image.source": config["gitea"] + "/" + config["repository"],
          "org.opencontainers.image.version": config["version"],
          "org.opencontainers.image.revision": config["commit"],
          "dev.docker.release.config": config["config_hash"],
          "dev.docker.release.scripts": config["script_hash"],
          "dev.docker.release.certificate": config["certificate_hash"]}


def inventory(root, work, config):
  release_io.INVENTORY_BUDGET = {"deadline": time.monotonic() + 600, "bytes": 0}
  try:
    return inventory_scan(root, work, config)
  finally:
    release_io.INVENTORY_BUDGET = None


def inventory_scan(root, work, config):
  started, size, items, pages = time.monotonic(), 0, 0, 0
  release = None
  api_tag = None
  for resource in ("releases", "tags"):
    fingerprints, identities = set(), set()
    for page in range(1, 1003):
      pages += 1
      remaining = 600 - (time.monotonic() - started)
      require(pages <= 1002 and remaining > 0, "Inventory time/page budget exceeded")
      url = config["gitea"] + "/api/v1/repos/" + config["repository"] + "/" + resource + "?" + urlencode({"page": page, "limit": 100})
      status, _, payload = http(work, "GET", url, seconds=min(60, remaining))
      require(status == 200, "Inventory unavailable")
      size += len(payload)
      values = decode(payload)
      require(isinstance(values, list) and len(values) <= 100, "Invalid inventory array")
      items += len(values)
      require(size <= 64 * 1024 * 1024 and items <= 100000, "Inventory byte/item budget exceeded")
      if not values:
        break
      fingerprint = sha(canonical(values))
      require(fingerprint not in fingerprints, "Inventory pagination repeated")
      fingerprints.add(fingerprint)
      for value in values:
        require(isinstance(value, dict), "Invalid inventory record")
        name = value.get("tag_name" if resource == "releases" else "name")
        require(text(name) and name not in identities, "Invalid or duplicate inventory identity")
        identities.add(name)
        if name == config["tag"]:
          if resource == "releases":
            release = value
          else:
            api_tag = value
        if resource == "releases":
          require(type(value.get("draft")) is bool and type(value.get("prerelease")) is bool, "Invalid release flags")
          if not value["draft"] and not value["prerelease"]:
            require(name.startswith("v") and semver(name[1:]) <= semver(config["version"]), "Newer or unrecognized release exists")
    else:
      raise Refusal("Inventory has no terminal empty page")
  remaining = 600 - (time.monotonic() - started)
  require(remaining > 0, "Inventory time budget exceeded")
  raw = command(["git", "-C", str(root), "ls-remote", "--tags", "origin"], REF_LIMIT, min(60, remaining))
  release_io.INVENTORY_BUDGET["bytes"] += len(raw)
  require(size + len(raw) <= 64 * 1024 * 1024 and time.monotonic() - started < 600, "Inventory budget exceeded")
  refs = {}
  for line in raw.decode().splitlines():
    parts = line.split()
    require(len(parts) == 2 and re.fullmatch(r"[0-9a-f]{40}", parts[0]) and parts[1].startswith("refs/tags/") and
            parts[1] not in refs, "Malformed tag advertisement")
    refs[parts[1]] = parts[0]
  require(items + len(refs) <= 100000, "Tag inventory item budget exceeded")
  tag = "refs/tags/" + config["tag"]
  require((api_tag is not None) == (tag in refs), "API/Git tag inventories disagree")
  require(tag in refs or tag + "^{}" not in refs, "Missing direct tag advertisement")
  versions, latest = {}, {}
  for name, _, _ in GRAPH:
    versions[name] = resolve(work, config, name, config["tag"])
    latest[name] = resolve(work, config, name, "latest")
  return {"release": release, "oid": refs.get(tag), "commit": refs.get(tag + "^{}"),
          "versions": versions, "latest": latest}


def base_identity(config):
  return {"format": "dev-docker-release/1", "repository": config["repository"], "version": config["version"],
          "tag": config["tag"], "commit": config["commit"], "config": config["config_hash"],
          "scripts": config["script_hash"], "certificate": config["certificate_hash"], "platforms": config["platforms"],
          "prefix": config["prefix"], "notes": {"path": config["notes"], "digest": sha(config["body"].encode())}}


def tag_bytes(identity):
  header = ("object " + identity["commit"] + "\ntype commit\ntag " + identity["tag"] +
            "\ntagger Dev Docker Release <release@localhost> 0 +0000\n\n").encode()
  return header + MARKER + canonical(identity) + b"\n"


def tag_object(root, identity):
  oid = git(root, "mktag", input_data=tag_bytes(identity)).decode().strip()
  require(re.fullmatch(r"[0-9a-f]{40}", oid), "Invalid tag object ID")
  local = git(root, "tag", "--list", identity["tag"]).strip()
  if local:
    require(git(root, "rev-parse", "refs/tags/" + identity["tag"]).decode().strip() == oid, "Local tag conflicts")
  return oid


def inspect_tag(root, config, oid):
  require(re.fullmatch(r"[0-9a-f]{40}", oid), "Invalid tag object")
  git(root, "fetch", "--no-tags", "--no-write-fetch-head", "origin", oid)
  require(git(root, "cat-file", "-t", oid).strip() == b"tag" and
          int(git(root, "cat-file", "-s", oid)) <= SMALL_LIMIT, "Expected bounded annotated tag")
  raw = git(root, "cat-file", "tag", oid, limit=SMALL_LIMIT)
  message = raw.split(b"\n\n", 1)[1]
  require(message.startswith(MARKER), "Unknown tag identity format")
  identity = decode(message[len(MARKER):])
  base = base_identity(config)
  require(isinstance(identity, dict) and set(identity) == set(base) | {"digests", "predecessors"} and
          all(identity[key] == value for key, value in base.items()), "Release identity differs")
  names = {item[0] for item in GRAPH}
  require(isinstance(identity["digests"], dict) and set(identity["digests"]) == names and
          all(digest(value) for value in identity["digests"].values()), "Invalid bound digest set")
  require(isinstance(identity["predecessors"], dict) and set(identity["predecessors"]) == names and
          all(value is None or digest(value) for value in identity["predecessors"].values()), "Invalid predecessor set")
  require(raw == tag_bytes(identity) and tag_object(root, identity) == oid, "Canonical tag bytes differ")
  return identity


def release_check(record, config):
  require(isinstance(record, dict) and record.get("tag_name") == config["tag"] and
          record.get("name") == config["tag"] and record.get("draft") is False and record.get("prerelease") is False and
          isinstance(record.get("body"), str) and
          record["body"].replace("\r\n", "\n").replace("\r", "\n").rstrip("\n") + "\n" == config["body"],
          "Release body/state differs")


def unchanged(root, work, config):
  current = settings(root)
  require(all(config[key] == value for key, value in current.items()), "Captured settings/scripts changed")
  source(root, config, config["commit"])
  cert = Path(os.environ.get("BUILD_CERT_FILE") or config["certificate_file"]).expanduser()
  require(sha(read(cert, CONFIG_LIMIT)) == config["certificate_hash"], "Build certificate changed")


def startup(root, work, config):
  observed = inventory(root, work, config)
  state = document(work / "state.json")
  if observed["oid"] or observed["release"]:
    require(observed["oid"] and observed["release"] and observed["commit"] == config["commit"],
            "Ambiguous or conflicting tag/release startup; inspect without repair")
    identity = inspect_tag(root, config, observed["oid"])
    release_check(observed["release"], config)
    require(observed["versions"] == identity["digests"] and observed["latest"] == identity["digests"],
            "Completed aliases missing or foreign; no repair authority")
    state |= {key: identity[key] for key in ("digests", "predecessors")}
    state |= {"oid": observed["oid"], "versions": identity["digests"].copy(), "latest": identity["digests"].copy()}
    write(work / "state.json", state)
    for name, _, _ in GRAPH:
      require(image(work, config, name, state["digests"][name]) == state["digests"][name], "Immutable image differs")
    guard(root, work, config, completed=True)
    print("completed")
    return
  require(all(value is None for value in observed["versions"].values()), "Orphan version alias; inspect without adoption")
  require(not git(root, "tag", "--list", config["tag"]).strip(), "Local tag exists without completed publication")
  state |= {"predecessors": observed["latest"], "versions": observed["versions"], "latest": observed["latest"].copy()}
  write(work / "state.json", state)
  print("fresh")


def guard(root, work, config, completed=False, expected_oid=None, allow_release=False):
  unchanged(root, work, config)
  state = document(work / "state.json")
  observed = inventory(root, work, config)
  oid = expected_oid or state["oid"]
  require(observed["oid"] == oid and (not oid or observed["commit"] == config["commit"]), "Confirmed tag disappeared or changed")
  if completed or allow_release:
    require(observed["release"], "Release creation not confirmed")
    release_check(observed["release"], config)
  else:
    require(observed["release"] is None, "Requested release appeared unexpectedly")
  require(observed["versions"] == state["versions"], "Version aliases changed")
  for name, _, _ in GRAPH:
    actual, expected = observed["latest"][name], state["latest"][name]
    allowed = {expected}
    # Only not-yet-promoted latest may already equal the prepared digest.
    if expected == state["predecessors"][name] and name in state["digests"]:
      allowed.add(state["digests"][name])
    require(actual in allowed, "Latest changed; no rollback authority")
    if completed:
      require(actual == state["digests"][name], "Completed latest differs")
  return observed


def snapshot(root, work, config, local):
  context = work / "context"
  (context / "Dockerfile").mkdir(parents=True)
  for _, file, _ in GRAPH:
    name = "Dockerfile/" + file + ".Dockerfile"
    value = read(regular(root, name)) if local else blob(root, config["commit"], name)
    (context / name).write_bytes(value)
  shutil.copyfile(work / "certificate", context / "git.lanCA.crt")


def build_args(work, config, name, local):
  state = document(work / "state.json")
  item = next(item for item in config["images"] if item["name"] == name)
  arguments = ["docker", "buildx", "build", "--platform", "linux/amd64", "--provenance=false", "--sbom=false",
               "--metadata-file", str(work / "build.json"), "--file", str(work / "context" / item["dockerfile"])]
  if local:
    arguments += ["--load", "--pull=false", "--tag", name + ":latest"]
  else:
    arguments += ["--push", "--tag", full_image(config, name) + ":" + staging(config)]
    for key, value in labels_for(config).items():
      arguments += ["--label", key + "=" + value]
  parent = item["parent"]
  if parent:
    reference = parent + ":latest" if local else full_image(config, parent) + "@" + state["digests"][parent]
    if local:
      require(local_image(reference) == state["digests"][parent], "Local parent changed before child build")
    arguments += ["--build-arg", "BASE_IMAGE=" + reference]
    # Local image IDs are config digests, not registry manifest references. BuildKit
    # resolves the checked tag from the Docker-driver store with --pull=false.
    arguments += ["--label", "dev.docker.release.parent=" + (state["digests"][parent] if local else reference)]
  else:
    # Preserve the token secret requested by the current base Dockerfile (user commit d15c1af).
    arguments += ["--secret", "id=token,src=" + str(work / "token")]
  return arguments + [str(work / "context")]


def staging(config):
  identity = base_identity(config)
  return "stage-" + config["version"] + "-" + sha(canonical(identity))[7:]


def local_image(reference):
  values = decode(command(["docker", "image", "inspect", reference], CONFIG_LIMIT))
  require(isinstance(values, list) and len(values) == 1, "Expected one local image")
  value = values[0]
  require(value.get("Os") == "linux" and value.get("Architecture") == "amd64" and digest(value.get("Id")),
          "Local image platform/identity differs")
  return value["Id"]


def prepare_image(root, work, config, name, local):
  if not local:
    guard(root, work, config)
    existing = resolve(work, config, name, staging(config))
    captured = document(work / "state.json")["digests"].get(name)
    if existing:
      require(captured is None or captured == existing, "Captured staging alias changed")
      require(image(work, config, name, existing) == existing, "Staging image differs")
      state = document(work / "state.json")
      state["digests"][name] = existing
      write(work / "state.json", state)
      print("reuse")
      return
    require(captured is None, "Captured staging alias disappeared; no automatic rebuild")
  write(work / "arguments.json", build_args(work, config, name, local))
  print("build")


def staging_inventory(work, config):
  """Classify every staging object before the first build; no writes to services."""
  for name, _, parent in GRAPH:
    existing = resolve(work, config, name, staging(config))
    if existing:
      state = document(work / "state.json")
      require(parent is None or parent in state["digests"], "Orphan staging child; inspect parent evidence")
      require(image(work, config, name, existing) == existing, "Staging evidence differs")
      state["digests"][name] = existing
      write(work / "state.json", state)


def accept_image(work, config, name, local):
  metadata = document(work / "build.json", CONFIG_LIMIT)
  if local:
    prepared = local_image(name + ":latest")
    require(metadata.get("containerimage.config.digest") == prepared, "Loaded image differs from build metadata")
    item = decode(command(["docker", "image", "inspect", prepared], CONFIG_LIMIT))[0]
    parent = next(item[2] for item in GRAPH if item[0] == name)
    if parent:
      expected_parent = document(work / "state.json")["digests"][parent]
      require(local_image(parent + ":latest") == expected_parent, "Local parent changed during child build")
      require(item.get("Config", {}).get("Labels", {}).get("dev.docker.release.parent") == expected_parent,
              "Local parent label differs")
  else:
    prepared = image(work, config, name, staging(config))
    require(metadata.get("containerimage.digest") == prepared, "Pushed image differs from build metadata")
  state = document(work / "state.json")
  state["digests"][name] = prepared
  write(work / "state.json", state)


def make_tag(root, work, config):
  guard(root, work, config)
  state = document(work / "state.json")
  require(set(state["digests"]) == {item[0] for item in GRAPH}, "Incomplete image set")
  for name, _, _ in GRAPH:
    require(image(work, config, name, state["digests"][name]) == state["digests"][name], "Prepared image disappeared")
  identity = base_identity(config) | {key: state[key] for key in ("digests", "predecessors")}
  write(work / "identity.json", identity)
  print(tag_object(root, identity))


def confirm_tag(root, work, config, oid):
  guard(root, work, config, expected_oid=oid)
  state = document(work / "state.json")
  state["oid"] = oid
  write(work / "state.json", state)


def promote_args(root, work, config, name, alias):
  observed = guard(root, work, config)
  state = document(work / "state.json")
  require(state["oid"], "Cannot promote without confirmed tag")
  require(alias in (config["tag"], "latest"), "Unknown alias")
  key = "latest" if alias == "latest" else "versions"
  prepared = state["digests"][name]
  if observed[key][name] == prepared:
    state[key][name] = prepared
    write(work / "state.json", state)
    print("skip")
    return
  write(work / "arguments.json", ["docker", "buildx", "imagetools", "create", "--prefer-index=false", "--tag",
                                full_image(config, name) + ":" + alias, full_image(config, name) + "@" + prepared])
  print("promote")


def confirm_alias(root, work, config, name, alias):
  state = document(work / "state.json")
  prepared = state["digests"][name]
  require(resolve(work, config, name, alias) == prepared, "Alias write not confirmed")
  state["latest" if alias == "latest" else "versions"][name] = prepared
  write(work / "state.json", state)
  guard(root, work, config)


def payload(root, work, config):
  guard(root, work, config)
  state = document(work / "state.json")
  require(state["oid"] and state["versions"] == state["digests"] and state["latest"] == state["digests"],
          "Release requires every prepared alias")
  write(work / "payload.json", {"tag_name": config["tag"], "target_commitish": config["commit"],
                                "name": config["tag"], "body": config["body"], "draft": False, "prerelease": False})


def prewrite(check, *arguments):
  """A failed prerequisite read is not evidence that a mutation was attempted."""
  try:
    return check(*arguments)
  except CommandFailed as exc:
    raise Refusal("Pre-write evidence unavailable; no mutation attempted") from exc


def dispatch(arguments):
  action, root, *args = arguments
  root = Path(root).resolve()
  if action == "settings":
    config = settings(root)
    if args:
      require(args[0] == config["tag"], "Positional tag must equal configured v<VERSION>")
    print("Configuration valid; no credentials or external operations used")
    return 0
  if action == "locked":
    return locked(root, args)
  if action == "lock-check":
    descriptor = int(os.environ["RELEASE_LOCK_FD"])
    path = root / ".release-operation.lock"
    require(not path.is_symlink() and os.fstat(descriptor).st_ino == path.stat().st_ino and
            os.fstat(descriptor).st_dev == path.stat().st_dev, "Invalid inherited release lock")
    fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
    return 0
  work, *args = args
  work = Path(work)
  if action == "init":
    init(root, work, args[0])
    return 0
  config = document(work / "settings.json")
  if action == "credentials":
    credentials(root, work, config)
  elif action == "docker-auth":
    docker_auth(work)
  elif action == "builder":
    builder(work, args[0] == "local")
  elif action == "verify-builder":
    verify_builder(work)
  elif action == "startup":
    unchanged(root, work, config)
    startup(root, work, config)
  elif action == "staging-inventory":
    staging_inventory(work, config)
  elif action == "snapshot":
    snapshot(root, work, config, args[0] == "local")
  elif action == "prepare-image":
    prepare_image(root, work, config, args[0], args[1] == "local")
  elif action == "accept-image":
    accept_image(work, config, args[0], args[1] == "local")
  elif action == "build":
    if "commit" in config:
      prewrite(guard, root, work, config)
    arguments = document(work / "arguments.json")
    seconds = 7200 if arguments[1:3] == ["buildx", "build"] else 60
    command(arguments, REF_LIMIT, seconds)
  elif action == "login":
    command(["docker", "login", urlsplit(config["gitea"]).netloc, "--username", read(work / "login", 256).decode(),
             "--password-stdin"], CONFIG_LIMIT, input_data=read(work / "token", 4096))
  elif action == "make-tag":
    make_tag(root, work, config)
  elif action == "push-tag":
    prewrite(guard, root, work, config)
    require(args[0] == prewrite(tag_object, root, document(work / "identity.json")), "Unexpected tag push")
    git(root, "push", "--no-follow-tags", "origin", args[0] + ":refs/tags/" + config["tag"])
  elif action == "confirm-tag":
    confirm_tag(root, work, config, args[0])
  elif action == "promote-args":
    promote_args(root, work, config, *args)
  elif action == "confirm-alias":
    confirm_alias(root, work, config, *args)
  elif action == "payload":
    payload(root, work, config)
  elif action == "post-release":
    prewrite(payload, root, work, config)
    status, _, _ = http(work, "POST", config["gitea"] + "/api/v1/repos/" + config["repository"] + "/releases",
                        payload=work / "payload.json")
    require(status in (200, 201), "Release request not accepted")
  elif action == "finish":
    guard(root, work, config, completed=True)
    state = document(work / "state.json")
    for name, _, _ in GRAPH:
      require(image(work, config, name, state["digests"][name]) == state["digests"][name], "Final image differs")
    guard(root, work, config, completed=True)
  elif action == "summary":
    state = document(work / "state.json")
    print("Verified " + config["tag"])
    for name, _, _ in GRAPH:
      print(full_image(config, name) + "@" + state["digests"][name] + " (" + config["tag"] + ", latest)")
    print(config["gitea"] + "/" + config["repository"] + "/releases/tag/" + config["tag"])
  elif action == "status":
    state = document(work / "state.json")
    print("Known tag: " + str(state["oid"]), file=sys.stderr)
    for name, _, _ in GRAPH:
      print(name + ": " + canonical({key: state[key].get(name) for key in ("digests", "versions", "latest")}).decode(),
            file=sys.stderr)
  elif action == "docker-origin":
    print(Path(os.environ.get("DOCKER_CONFIG") or str(Path.home() / ".docker")).absolute())
  elif action == "field":
    print(config[args[0]])
  else:
    raise Refusal("Unknown release helper action")
  return 0


if __name__ == "__main__":
  def interrupted(_number, _frame):
    raise Refusal("Operation interrupted; inspect remaining remote objects")
  signal.signal(signal.SIGINT, interrupted)
  signal.signal(signal.SIGTERM, interrupted)
  try:
    require(sys.version_info >= (3, 11), "Install Python 3.11 or later")
    sys.exit(dispatch(sys.argv[1:]))
  except (Refusal, OSError, ValueError, KeyError, TypeError, IndexError, AttributeError,
          RecursionError, subprocess.SubprocessError) as exc:
    # Never relay remote payloads, command stderr, or credential paths.
    print("Release stopped: " + (str(exc) if isinstance(exc, Refusal) else "Invalid or unavailable input"), file=sys.stderr)
    sys.exit(2 if isinstance(exc, CommandFailed) else 1)
