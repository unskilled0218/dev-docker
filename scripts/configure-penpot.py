#!/usr/bin/env python3
"""Merge token-free Penpot defaults without loading OpenCode or runtime secrets."""

import json
from pathlib import Path
import re
import sys
import tempfile


SERVER = {
  "type": "remote",
  "url": "https://penpot.lan/mcp/stream?userToken={file:/home/container/.config/token/penpot}",
  "oauth": False,
}
# Keep strings intact while removing JSONC comments and trailing commas.
JSONC_TOKEN = re.compile(r'"(?:[^"\\]|\\.)*"|//[^\r\n]*|/\*[\s\S]*?\*/|,\s*(?=[}\]])')


def unique(pairs):
  result = {}
  for key, value in pairs:
    if key in result:
      raise ValueError("Duplicate configuration key")
    result[key] = value
  return result


def object_field(parent, key):
  if key not in parent:
    parent[key] = {}
  if not isinstance(parent[key], dict):
    raise ValueError("Expected configuration object")
  return parent[key]


def configure(directory):
  directory = Path(directory)
  if any(path.is_symlink() for path in (directory, *directory.parents)):
    raise ValueError("Symlink configuration directory refused")
  paths = [directory / name for name in ("opencode.json", "opencode.jsonc")]
  if any(path.is_symlink() for path in paths):
    raise ValueError("Symlink configuration file refused")
  existing = [path for path in paths if path.exists()]
  if len(existing) > 1:
    raise ValueError("Conflicting JSON and JSONC configurations")
  path = existing[0] if existing else paths[0]
  config = {}
  if existing:
    text = path.read_text()
    if path.suffix == ".jsonc":
      text = JSONC_TOKEN.sub(lambda match: match[0] if match[0].startswith('"') else " ", text)
      # A comment between a comma and closing bracket becomes whitespace above.
      text = JSONC_TOKEN.sub(lambda match: match[0] if match[0].startswith('"') else " ", text)
    config = json.loads(text, object_pairs_hook=unique)
  if not isinstance(config, dict):
    raise ValueError("Expected configuration object")
  config.setdefault("$schema", "https://opencode.ai/config.json")
  servers = object_field(object_field(config, "mcp"), "servers")
  servers["penpot"] = dict(SERVER)
  directory.mkdir(parents=True, exist_ok=True, mode=0o700)
  temporary = None
  try:
    with tempfile.NamedTemporaryFile(mode="w", dir=directory, delete=False) as target:
      temporary = Path(target.name)
      json.dump(config, target, indent=2, allow_nan=False)
      target.write("\n")
    temporary.replace(path)
  finally:
    if temporary is not None:
      temporary.unlink(missing_ok=True)


if __name__ == "__main__":
  try:
    configure(Path.home() / ".config/opencode")
  except (OSError, ValueError):
    # Existing config may contain private settings; never print parser input.
    sys.exit("Penpot configuration refused; check config permissions, format, and conflicting files")
