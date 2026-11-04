# Penpot MCP

- [Penpot MCP](#penpot-mcp)
  - [Token files](#token-files)
  - [Compose](#compose)
  - [Image configuration](#image-configuration)
  - [Connect and verify](#connect-and-verify)
  - [Limits](#limits)

## Token files

Keep the host's `~/.config/token` directory mode `0700`, with files `git` and `penpot` mode `0600`. The container user (UID 1000) must be able to read them; Git build credentials must also be owned by the build-script caller. Account for UID mapping before using bind mounts. Never commit tokens or print their contents.

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

The supplied `compose/docker-compose.yml` uses one mount:

```yaml
- type: bind
  source: ${HOME}/.config/token
  target: /home/container/.config/token
  read_only: true
  bind:
    create_host_path: false
```

After selecting an image containing these changes, recreate the container:

```bash
docker compose -f compose/docker-compose.yml up -d --force-recreate app
```

Every file in this directory is visible to the container, including any additional tokens. Read-only prevents writes, not disclosure. A missing host directory refuses mounting; a present directory does not guarantee that either token file exists or is valid. No token environment variable is needed.

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

Only the literal file reference enters the image; OpenCode reads the key at runtime. Existing settings and other servers are retained; the Penpot entry is replaced with these defaults. A sole existing `opencode.jsonc` is updated in place, preserving settings but normalizing formatting and removing comments. Invalid or duplicate keys, symlinks, and simultaneous JSON/JSONC files are refused without overwrite. Output is written atomically with mode `0600`.

JSONC supports line/block comments and a single trailing comma after a value. Double commas, comma-only containers, and missing values are rejected before any write, preserving the original bytes and directory contents. Strings containing comment markers, escaped quotes, or comma/bracket text remain unchanged. CLI refusal returns a nonzero status and a sanitized message without printing config contents.

Project settings can override global defaults, including replacing a same-named server object. Mounting over the OpenCode config directory hides the baked file. OpenCode watches config changes; use `/reload` if needed. The build does not start an OpenCode service or contact MCP. The existing setup script installs OpenCode at `~/.opencode/bin/opencode`; the image verifies that executable before configuring it.

Git builds still use a separate BuildKit secret with ID `token` at `/home/container/.config/token/git`. The Compose mount supplies runtime files only. See [build credentials](image-releases.md#credentials-and-trust).

## Connect and verify

1. Open a Penpot design file at `https://penpot.lan` and select **File → MCP Server → Connect**. Keep that browser tab active.
2. In OpenCode, open `/mcps` and check Penpot's status. `opencode mcp list` also lists MCP connections; an empty list is not proof that the config file is absent. Inspect config discovery privately if needed.
3. Ask: “Use Penpot to list pages without changing anything.” Agents can edit designs, so start read-only.

The confirmed endpoint is `/mcp/stream`; `/mcp` serves the web application. Token-free initialization succeeded during planning, but it does not prove authenticated design access. `localhost` in a container refers to that container, not the host.

## Limits

OpenCode v2.2.5 config-loading checks resolved synthetic token files successfully. Empty, missing, and unreadable files resolved to empty strings without a config error. Do not treat config loading as authentication or an empty key as an authorized fallback; provide a valid readable key and verify actual MCP access. Keep keys newline-free and never share expanded URLs or private config/debug output. Token values in URLs can also reach proxy/server logs; restrict access and redact logs there.

Offline tests verify config creation, preservation, and runtime substitution using synthetic data, not real Penpot authorization. Real-image verification also requires readable CA inputs and Git build credentials. Do not bypass TLS or change host permissions to force a build. No image publication is part of setup verification.
