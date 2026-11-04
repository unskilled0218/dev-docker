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
# Each transformation protects quoted strings and runs only once.
JSON_STRING = r'"(?:[^"\\]|\\.)*"'
JSONC_COMMENT = re.compile(JSON_STRING + r'|//[^\r\n]*|/\*[\s\S]*?\*/')
JSONC_COMMA = re.compile(JSON_STRING + r'|,\s*(?=[}\]])')


def jsonc_text(text):
  text = JSONC_COMMENT.sub(lambda match: match[0] if match[0].startswith('"') else " ", text)

  def trailing_comma(match):
    if match[0].startswith('"'):
      return match[0]
    previous = text[:match.start()].rstrip()
    # Strings, containers, numbers, true/false, and null can end a value.
    # Final JSON parsing still validates its complete syntax.
    if previous and previous[-1] in '"}]0123456789el':
      return " "
    return match[0]

  return JSONC_COMMA.sub(trailing_comma, text)


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
      text = jsonc_text(text)
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
