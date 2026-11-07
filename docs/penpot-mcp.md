# Penpot MCP

- [Penpot MCP](#penpot-mcp)
  - [Token files](#token-files)
  - [Compose](#compose)
  - [Image configuration](#image-configuration)
  - [Connect and verify](#connect-and-verify)
  - [Limits](#limits)

## Token files

Keep the host's `~/.config/token` directory mode `0700`, with files `git` and `penpot` mode `0600`. Git publication credentials must be owned by the build-script caller. Both build modes copy the whole token directory into the image for UID 1000, including any extra files. Never commit tokens or print their contents. See [personal build inputs](image-releases.md#personal-files) for overrides and limits.

Run these Bash commands on the host to copy an existing Git token without deleting the original. An existing destination causes refusal rather than overwrite:

```bash
(
  set -e
  umask 077
  set -o noclobber
  mkdir -p "$HOME/.config/token"
  chmod 700 "$HOME/.config/token"
  cat "$HOME/.config/git/token" > "$HOME/.config/token/git"
)
```

In Penpot, enable **Your account → Integrations → MCP Server** and generate a key. Save only that key, not the copied server URL, using Bash:

```bash
(
  set -e
  umask 077
  set -o noclobber
  mkdir -p "$HOME/.config/token"
  chmod 700 "$HOME/.config/token"
  IFS= read -rsp "Penpot MCP key: " key
  printf '\n'
  test -n "$key"
  printf '%s' "$key" > "$HOME/.config/token/penpot"
)
```

This creates a newline-free file and refuses to overwrite an existing token. The application never migrates host tokens or changes their permissions automatically. Git's old path remains usable through explicit `token_file`, `GIT_TOKEN`, or `FORGEJO_TOKEN_FILE` settings; there is no automatic fallback. Update any personal credential helpers or external scripts that still reference the old path yourself.

## Compose

The supplied `compose/docker-compose.yml` uses the image's baked SSH, Git config, and token files. It no longer mounts these host paths. You can add your own runtime mount to override baked files.

After rebuilding and selecting the new image, recreate the container:

```bash
docker compose -f compose/docker-compose.yml up -d --force-recreate app
```

Every copied token is extractable by anyone with image access, including from caches and backups. Private Gitea hosting does not prevent extraction. Rotation requires a new image version and recreated containers; revoke obsolete keys because old images retain them. No token environment variable is needed. The build does not require a `penpot` file or prove that its key is valid.

## Image configuration

After setup, the base image merges this server into `/home/container/.config/opencode/opencode.json` as `container`; npm inherits it:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "servers": {
      "penpot": {
        "type": "remote",
        "url": "https://penpot.lan/mcp/stream?userToken={file:/home/container/.config/token/penpot}",
        "oauth": false
      }
    }
  }
}
```

The configuration keeps the literal file reference; OpenCode reads the baked key at runtime. Personal files are copied after setup and this configuration step. Existing settings and other servers are retained; the Penpot entry is replaced with these defaults. A sole existing `opencode.jsonc` is updated in place, preserving settings but normalizing formatting and removing comments. Invalid or duplicate keys, symlinks, and simultaneous JSON/JSONC files are refused without overwrite. Output is written atomically with mode `0600`.

JSONC supports line/block comments and a single trailing comma after a value. Double commas, comma-only containers, and missing values are rejected before any write, preserving the original bytes and directory contents. Strings containing comment markers, escaped quotes, or comma/bracket text remain unchanged. CLI refusal returns a nonzero status and a sanitized message without printing config contents.

Project settings can override global defaults, including replacing a same-named server object. Mounting over the OpenCode config directory hides the baked file. OpenCode watches config changes; use `/reload` if needed. The build does not start an OpenCode service or contact MCP. The existing setup script installs OpenCode at `~/.opencode/bin/opencode`; the image verifies that executable before configuring it.

The unused Git BuildKit secret mount has been removed. Host publication authentication remains separate from the copied token directory; its overrides do not replace baked files. See [build credentials](image-releases.md#credentials-and-trust).

## Connect and verify

1. Open a Penpot design file at `https://penpot.lan` and select **File → MCP Server → Connect**. Keep that browser tab active.
2. In OpenCode, open `/mcps` and check Penpot's status. `opencode mcp list` also lists MCP connections; an empty list is not proof that the config file is absent. Inspect config discovery privately if needed.
3. Ask: “Use Penpot to list pages without changing anything.” Agents can edit designs, so start read-only.

The confirmed endpoint is `/mcp/stream`; `/mcp` serves the web application. Token-free initialization succeeded during planning, but it does not prove authenticated design access. `localhost` in a container refers to that container, not the host.

## Limits

OpenCode v2.2.5 config-loading checks resolved synthetic token files successfully. Empty, missing, and unreadable files resolved to empty strings without a config error. Do not treat config loading as authentication or an empty key as an authorized fallback; provide a valid readable key and verify actual MCP access. Keep keys newline-free and never share expanded URLs or private config/debug output. Token values in URLs can also reach proxy/server logs; restrict access and redact logs there.

Offline tests verify config creation, preservation, and runtime substitution using synthetic data, not real Penpot authorization. Real-image verification also requires readable CA inputs and Git build credentials. Do not bypass TLS or change host permissions to force a build. No image publication is part of setup verification.
