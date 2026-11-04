- [Scope](#scope)
- [Implementation](#implementation)
- [Verification](#verification)
- [Acceptance criteria](#acceptance-criteria)
- [Risks](#risks)

## Scope

Configure Penpot MCP in the base image and use one read-only token directory for Git and Penpot. Preserve unrelated settings. Do not modify real tokens, host permissions, or live services.

## Implementation

The plan review approved this scope without findings. Before choosing the config-writing method, verify the installed OpenCode version preserves literal file references and loads them correctly at runtime using isolated synthetic inputs.

1. Use host files `~/.config/token/git` and `~/.config/token/penpot`.
2. Replace Compose's Git token mount with `${HOME}/.config/token` → `/home/container/.config/token`. Set `read_only: true` and `bind.create_host_path: false`. Preserve unrelated mounts.
3. Set Git's default `token_file` in `scripts/release.json` to `~/.config/token/git`. Preserve validation and override precedence: nonempty `GIT_TOKEN`, then nonempty `FORGEJO_TOKEN_FILE`, then configured path. Support the old path through explicit configuration or overrides, not automatic fallback.
4. Change the base Dockerfile's BuildKit secret target to `/home/container/.config/token/git`. Keep secret ID `token`, UID 1000, and `required=true`. Adjust directory creation without copying secrets. Check active consumers of the old path; do not modify external repositories.
5. After OpenCode setup, configure `/home/container/.config/opencode/opencode.json` as `container`. Add `mcp.servers.penpot` with `type: remote`, `oauth: false`, and URL `https://penpot.lan/mcp/stream?userToken={file:/home/container/.config/token/penpot}`. Store the literal reference, never the key. Use the CLI or a targeted merge that preserves unrelated settings, other servers, and existing JSONC without conflicting config files. Include the published schema for a new config. Verify executable availability and container-user ownership. npm inherits the config.
6. Add `docs/penpot-mcp.md`, a short README link, and updated Git paths in `docs/image-releases.md`. Document safe user-run migration, directory mode `0700`, file mode `0600`, compatible ownership, and a newline-free Penpot key. Never overwrite existing tokens or delete originals. Explain the connected Penpot plugin, `/mcps`, runtime mounting, and recreating the Compose container.
7. During implementation, bump the patch version, add release notes, update the configured notes path, and write `4-implemented.md`. Leave historical records unchanged.

## Verification

- Add offline tests for config creation, preservation, repeat application, V2 fields, and literal file references without a Penpot key present. Isolate HOME and XDG directories; never use real credentials or live Penpot.
- Test runtime substitution using synthetic credentials and a local test seam. Cover missing, empty, and unreadable key files; report actual failure behavior rather than assuming OpenCode rejects empty substitutions.
- Check the single Compose mount, Git default and legacy overrides, BuildKit secret target, Dockerfile ordering, and unchanged credential safeguards. Keep tokens out of build contexts and image layers. Update both snapshot modes and tests if new source files are needed.
- Run `python3 -B -m unittest discover -s tests`, `bash build-all.sh --validate`, and `git diff --check`. Report the known baseline failure concerning missing manual-image Dockerfiles separately.
- When prerequisites allow, run `bash build-all.sh --build-only`. Verify config ownership, base/npm inheritance, and authenticated MCP connectivity with a read-only action. Do not publish images, bypass TLS, or print credential-bearing URLs.

## Acceptance criteria

- One read-only directory mount supplies Git and Penpot tokens at the new paths.
- Base and npm images contain the Penpot file reference, not an actual token; unrelated OpenCode settings survive.
- Git overrides and secret isolation remain intact. Config generation needs no Penpot key; builds still require the Git BuildKit secret.
- Tests, relevant docs, release metadata, and implementation results describe the change and verification limits.
- Report config generation, authenticated MCP access, and real-image verification separately. A passing config test does not prove plugin connectivity; baseline failures or blocked builds must remain explicit.

## Risks

- `/mcp/stream` passed token-free initialization; `/mcp` serves HTML. Authenticated design access still requires separate verification and a connected plugin.
- The directory mount exposes every token inside it. Missing host directories fail mounting, but missing or empty files need separate checks. Keep the Penpot key newline-free and redact expanded URLs.
- Git's new default requires user migration. Runtime mounting does not replace build-time secret provisioning. Do not migrate host files automatically.
- OpenCode setup installs a moving version. Verify CLI persistence, JSONC preservation, PATH, and config loading. Never resolve the token reference during builds or start an OpenCode server as part of image configuration.
- Unreadable Git/ntfy CA inputs may block real builds; report this without changing host permissions. Mounting over the OpenCode config directory hides baked settings.
