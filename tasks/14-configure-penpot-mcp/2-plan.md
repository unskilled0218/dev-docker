- [Scope](#scope)
- [Implementation plan](#implementation-plan)
  - [1. Confirm the endpoint and authentication](#1-confirm-the-endpoint-and-authentication)
  - [2. Add the image configuration](#2-add-the-image-configuration)
  - [3. Add offline regression tests](#3-add-offline-regression-tests)
  - [4. Document and verify](#4-document-and-verify)
- [Acceptance criteria](#acceptance-criteria)
- [Risks and decisions](#risks-and-decisions)

## Scope

Configure a global Penpot MCP connection for the container user during the base image build, preserving existing OpenCode settings. Use the confirmed self-hosted endpoint and read its MCP key at runtime from `/home/container/.config/penpot/token`, mounted read-only from the host's `~/.config/penpot/token`. Keep credentials out of image layers. Do not alter the running container's OpenCode configuration, Penpot server settings, host trust, or unrelated image behavior.

## Implementation plan

### 1. Confirm the endpoint and authentication

- Use `https://penpot.lan/mcp/stream`, not `/mcp`. Planning-time trusted HTTPS probes showed `/mcp` returning the Penpot HTML application and `/mcp/stream` returning MCP JSON-RPC errors for requests without a valid handshake.
- A planning-time token-free `initialize` request to `/mcp/stream` succeeded and identified server `penpot`, version `1.0.0`, with tool capabilities. This confirms the transport endpoint, not authorization for design tools or a connected plugin. No design tools were called.
- Use Penpot's documented `userToken` query parameter with OpenCode file substitution: `https://penpot.lan/mcp/stream?userToken={file:/home/container/.config/penpot/token}`. Store this literal placeholder in the image configuration, never the actual key. Set `oauth: false` because this connection uses the MCP key rather than OAuth.

### 2. Add the image configuration

- After the existing `scripts/setup.sh` installation step in `Dockerfile/base.Dockerfile`, configure Penpot as the existing `container` user. Prefer `opencode mcp add penpot --global --url 'https://penpot.lan/mcp/stream?userToken={file:/home/container/.config/penpot/token}'` to preserve unrelated settings. Verify that the CLI persists the literal file reference without resolving it during the build; if it does not, use a targeted configuration merge instead. Preserve the V2 structure and set only this server's `oauth` field to `false` using a safe merge if the CLI cannot set it.
- Ensure the installer-provided OpenCode executable is on PATH in that build layer; use its verified installed path if shell-profile changes from setup are not inherited by Docker RUN instructions.
- Verify with the installed CLI in an isolated temporary HOME/config directory that the command creates `/home/container/.config/opencode/opencode.json` in the image when no config exists, writes native V2 `mcp.servers.penpot` with `type: remote`, and preserves unrelated fields and other MCP servers when a config exists. Include the published `$schema` in a newly created JSON config if the CLI does not add it.
- Do not overwrite a pre-existing JSONC config or create a second conflicting global config. If setup begins supplying JSONC or a conflicting Penpot entry, inspect its behavior and preserve unrelated settings; stop rather than silently discard unsupported content. Replace only the intended Penpot connection when that is necessary to establish the requested endpoint.
- Keep the global config and its directory owned and writable by `container`. Do not run the configuration command as root, start an OpenCode server, authenticate during the build, or call Penpot tools during the build.
- Prefer this inline Dockerfile command over adding a separate copied config or helper script. Existing local/publication snapshot contexts then need no new files or broader inclusion rules. The npm image inherits the base configuration.
- Add a long-form read-only bind mount to `compose/docker-compose.yml`: source `${HOME}/.config/penpot/token`, target `/home/container/.config/penpot/token`, and `bind.create_host_path: false`, matching the existing Git token mount style. Preserve all existing mounts and environment settings. Do not create the host token file, copy it into the build context, or add a token environment variable. Create only the container-side parent directory if necessary, owned by `container`.

### 3. Add offline regression tests

- Add `tests/test_penpot_mcp.py` to verify the configuration step follows setup and `USER ${USER_NAME}`, targets the global config, and stores the confirmed endpoint with the literal token-file reference and `oauth: false` rather than a real key or the web application URL.
- Test CLI configuration behavior using the installed OpenCode binary with isolated HOME, XDG configuration, data, state, cache, and working directories. Cover absent config, existing unrelated settings, another MCP server, and repeat application. Verify semantic preservation, the native V2 server shape, and no embedded credentials. Do not read or modify the user's real configuration or contact MCP services. If the binary is unavailable, mark these CLI-dependent tests explicitly skipped while keeping Dockerfile contract tests runnable.
- Do not assert whitespace, JSON key order, or unrelated CLI defaults. Keep assertions focused on the endpoint, preservation, idempotence, and supported config path. Any necessary schema insertion must have equivalent preservation and failure-path tests.
- Cover configuration generation with no token file present, proving that builds do not require or resolve the runtime key. Test runtime file substitution using only a synthetic token and an isolated local MCP test endpoint or equivalent configuration-loading seam; never send a real token or synthetic credentials to Penpot. Cover missing, empty, and unreadable token inputs and document the observed failure behavior without falling back to unauthenticated access. Do not assume OpenCode rejects empty substitutions itself.
- Assert the Compose token mount source, target, read-only setting, and disabled host-path creation. Verify that existing Git token and other mounts remain unchanged.
- Preserve existing Dockerfile, certificate, snapshot, build-isolation, and publication tests. Do not expand the fake context inventory unless implementation actually adds a source file, in which case update validation and both snapshot modes together.

### 4. Document and verify

- Add `docs/penpot-mcp.md` with the endpoint, global config location, base/npm inheritance, config precedence, and runtime override guidance. Keep the README change to a short link and summary. Update the existing context description only if its contents change.
- Explain that Penpot needs an active design file and connected MCP plugin, that agents can edit designs, and that the first manual check should be read-only. Document `opencode mcp list` and `/mcps`; never expose credential-bearing URLs in examples or logs.
- Document creating the host's `~/.config/penpot/token` from a hidden prompt with `umask 077` and `printf '%s'`, so it contains only the MCP key without a trailing newline. Require mode `0600` and ownership/UID permissions that let the container user read the bind-mounted file. Never print the key, commit it, or change host permissions automatically.
- Document the read-only Compose mount and `docker compose -f compose/docker-compose.yml up -d --force-recreate app`. No `PENPOT_MCP_KEY` environment variable is needed. Explain that `localhost` inside Docker is the container and that mounting over the OpenCode config directory hides the baked configuration. Do not add secret build arguments or image ENV values.
- Run `python3 -B -m unittest discover -s tests`, `bash build-all.sh --validate`, and `git diff --check`. Separately identify the known baseline failure concerning absent manual-image Dockerfiles; do not claim the whole suite passes if it remains.
- Attempt a real `bash build-all.sh --build-only` only with readable valid certificate inputs and available credentials. In a successfully built image, verify config contents and ownership, npm inheritance, and MCP connection status without changing designs. Report unreadable Git/ntfy CA files or other prerequisites without changing host permissions or bypassing TLS. Do not publish images.
- Through the implementation workflow, increment the patch version from the then-current version, add release notes, update `scripts/release.json`'s notes path, and record results in `4-implemented.md`.

## Acceptance criteria

- Base and derived npm images provide the container user's global OpenCode configuration with the confirmed fixed Penpot MCP URL and native V2 structure.
- The persisted URL contains `{file:/home/container/.config/penpot/token}` and the server has `oauth: false`. Compose mounts `${HOME}/.config/penpot/token` read-only without creating a missing host path. Builds work without the runtime token file.
- Existing unrelated configuration survives, configuration is container-user-owned, and repeated configuration does not duplicate the server.
- No actual key, token, credential-bearing URL, TLS bypass, new server process, or host configuration change is introduced into the image build.
- Automated verification covers configuration creation and preservation without depending on live Penpot. Runtime authorization and plugin availability are reported separately from successful configuration.
- Relevant README, dedicated documentation, release metadata, and implementation results are updated; limitations and baseline test failures remain explicit.

## Risks and decisions

- Successful initialization without a token does not prove design operations work without one. The requested connection explicitly uses a runtime-mounted MCP key; validate authorization and plugin connectivity separately without baking secrets into the image.
- OpenCode substitutes a missing file with an empty string, so absence of a key must not be mistaken for authenticated success. Compose refuses a missing host mount source; direct container runs still need the documented mount and a valid nonempty key. Verify whitespace handling, keep the key file newline-free, and redact expanded URLs from diagnostics.
- The external setup script installs a moving OpenCode V2 version. Verify actual CLI output and executable availability rather than assuming a JSON filename or PATH. A filename or JSONC conflict must be resolved without data loss before declaring the requested path complete.
- OpenCode configuration reloads on save; use `/reload` when needed rather than prescribing a restart. Do not alter the existing service environment merely to test the baked defaults.
- Image-level verification may remain blocked by unreadable Git/ntfy CA inputs. Planning changed only this document and did not modify implementation code or live configuration.
