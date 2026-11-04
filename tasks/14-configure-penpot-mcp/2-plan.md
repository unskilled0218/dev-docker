- [Scope](#scope)
- [Implementation plan](#implementation-plan)
  - [1. Confirm the endpoint and authentication](#1-confirm-the-endpoint-and-authentication)
  - [2. Add the image configuration](#2-add-the-image-configuration)
  - [3. Add offline regression tests](#3-add-offline-regression-tests)
  - [4. Document and verify](#4-document-and-verify)
- [Acceptance criteria](#acceptance-criteria)
- [Risks and decisions](#risks-and-decisions)

## Scope

Configure a global Penpot MCP connection for the container user during the base image build, preserving existing OpenCode settings. Use the confirmed self-hosted endpoint and keep credentials out of image layers. Do not alter the running container's OpenCode configuration, Penpot server settings, host trust, or unrelated image behavior.

## Implementation plan

### 1. Confirm the endpoint and authentication

- Use `https://penpot.lan/mcp/stream`, not `/mcp`. Planning-time trusted HTTPS probes showed `/mcp` returning the Penpot HTML application and `/mcp/stream` returning MCP JSON-RPC errors for requests without a valid handshake.
- A planning-time token-free `initialize` request to `/mcp/stream` succeeded and identified server `penpot`, version `1.0.0`, with tool capabilities. This confirms the transport endpoint, not authorization for design tools or a connected plugin. No design tools were called.
- Start with the fixed credential-free URL. Do not assume that local-only access removes authentication requirements. If actual tool discovery or use requires a key, stop and confirm the supported runtime credential mechanism; do not invent a header or embed a token.

### 2. Add the image configuration

- After the existing `scripts/setup.sh` installation step in `Dockerfile/base.Dockerfile`, run `opencode mcp add penpot --global --url https://penpot.lan/mcp/stream` as the existing `container` user. The installed CLI documents this noninteractive command and OpenCode recommends it to preserve unrelated settings.
- Ensure the installer-provided OpenCode executable is on PATH in that build layer; use its verified installed path if shell-profile changes from setup are not inherited by Docker RUN instructions.
- Verify with the installed CLI in an isolated temporary HOME/config directory that the command creates `/home/container/.config/opencode/opencode.json` in the image when no config exists, writes native V2 `mcp.servers.penpot` with `type: remote`, and preserves unrelated fields and other MCP servers when a config exists. Include the published `$schema` in a newly created JSON config if the CLI does not add it.
- Do not overwrite a pre-existing JSONC config or create a second conflicting global config. If setup begins supplying JSONC or a conflicting Penpot entry, inspect its behavior and preserve unrelated settings; stop rather than silently discard unsupported content. Replace only the intended Penpot connection when that is necessary to establish the requested endpoint.
- Keep the global config and its directory owned and writable by `container`. Do not run the configuration command as root, start an OpenCode server, authenticate during the build, or call Penpot tools during the build.
- Prefer this inline Dockerfile command over adding a separate copied config or helper script. Existing local/publication snapshot contexts then need no new files or broader inclusion rules. The npm image inherits the base configuration.

### 3. Add offline regression tests

- Add `tests/test_penpot_mcp.py` to verify the configuration step follows setup and `USER ${USER_NAME}`, uses `--global`, and contains the confirmed credential-free endpoint rather than the web application URL.
- Test CLI configuration behavior using the installed OpenCode binary with isolated HOME, XDG configuration, data, state, cache, and working directories. Cover absent config, existing unrelated settings, another MCP server, and repeat application. Verify semantic preservation, the native V2 server shape, and no embedded credentials. Do not read or modify the user's real configuration or contact MCP services. If the binary is unavailable, mark these CLI-dependent tests explicitly skipped while keeping Dockerfile contract tests runnable.
- Do not assert whitespace, JSON key order, or unrelated CLI defaults. Keep assertions focused on the endpoint, preservation, idempotence, and supported config path. Any necessary schema insertion must have equivalent preservation and failure-path tests.
- Preserve existing Dockerfile, certificate, snapshot, build-isolation, and publication tests. Do not expand the fake context inventory unless implementation actually adds a source file, in which case update validation and both snapshot modes together.

### 4. Document and verify

- Add `docs/penpot-mcp.md` with the endpoint, global config location, base/npm inheritance, config precedence, and runtime override guidance. Keep the README change to a short link and summary. Update the existing context description only if its contents change.
- Explain that Penpot needs an active design file and connected MCP plugin, that agents can edit designs, and that the first manual check should be read-only. Document `opencode mcp list` and `/mcps`; never expose credential-bearing URLs in examples or logs.
- Document that `localhost` inside Docker is the container, and that mounting over the OpenCode config directory hides the baked configuration. Runtime secrets must reach the OpenCode service environment or a privately mounted configuration; do not add secret build arguments or image ENV values.
- Run `python3 -B -m unittest discover -s tests`, `bash build-all.sh --validate`, and `git diff --check`. Separately identify the known baseline failure concerning absent manual-image Dockerfiles; do not claim the whole suite passes if it remains.
- Attempt a real `bash build-all.sh --build-only` only with readable valid certificate inputs and available credentials. In a successfully built image, verify config contents and ownership, npm inheritance, and MCP connection status without changing designs. Report unreadable Git/ntfy CA files or other prerequisites without changing host permissions or bypassing TLS. Do not publish images.
- Through the implementation workflow, increment the patch version from the then-current version, add release notes, update `scripts/release.json`'s notes path, and record results in `4-implemented.md`.

## Acceptance criteria

- Base and derived npm images provide the container user's global OpenCode configuration with the confirmed fixed Penpot MCP URL and native V2 structure.
- Existing unrelated configuration survives, configuration is container-user-owned, and repeated configuration does not duplicate the server.
- No actual key, token, credential-bearing URL, TLS bypass, new server process, or host configuration change is introduced into the image build.
- Automated verification covers configuration creation and preservation without depending on live Penpot. Runtime authorization and plugin availability are reported separately from successful configuration.
- Relevant README, dedicated documentation, release metadata, and implementation results are updated; limitations and baseline test failures remain explicit.

## Risks and decisions

- Successful initialization without a token does not prove design operations work without one. Runtime authentication, if needed, remains a verification gate rather than a reason to bake secrets into the image.
- The external setup script installs a moving OpenCode V2 version. Verify actual CLI output and executable availability rather than assuming a JSON filename or PATH. A filename or JSONC conflict must be resolved without data loss before declaring the requested path complete.
- OpenCode configuration reloads on save; use `/reload` when needed rather than prescribing a restart. Do not alter the existing service environment merely to test the baked defaults.
- Image-level verification may remain blocked by unreadable Git/ntfy CA inputs. Planning changed only this document and did not modify implementation code or live configuration.
