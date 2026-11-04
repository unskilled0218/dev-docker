- [Changes](#changes)
- [Verification](#verification)
- [Limits and decisions](#limits-and-decisions)

## Changes

- Created branch `14-configure-penpot-mcp` and updated version `0.1.21` → `0.1.22`, release notes, and the configured notes path.
- Replaced Compose's individual Git token mount with one read-only `~/.config/token` directory at `/home/container/.config/token`, with automatic host-path creation disabled.
- Moved Git's default input to `~/.config/token/git` and BuildKit secret target to `/home/container/.config/token/git`. Preserved ID `token`, UID 1000, required-secret behavior, credential validation, override precedence, and explicit legacy-path support without fallback.
- Added `scripts/configure-penpot.py` and Python 3 in the base image. After OpenCode setup, it atomically merges native V2 Penpot defaults as the container user with `oauth: false` and literal URL `https://penpot.lan/mcp/stream?userToken={file:/home/container/.config/token/penpot}`. No token file is opened by the helper.
- Preserved unrelated config settings and other MCP servers. JSONC settings are supported in place with formatting/comments normalized; conflicting config files, duplicate keys, malformed structures, and symlinks are refused without overwrite. Output mode is `0600`; the image creates the runtime token directory as the container user with mode `0700`.
- Added the helper to validation and both build snapshot modes. Extended fake-context assertions, source-refusal tests, snapshots, Git default/legacy-path tests, and offline config/runtime-substitution tests.
- Updated README, release documentation, and dedicated `docs/penpot-mcp.md` with safe user-run migration, Compose usage, permissions, plugin connection, and security limits.

## Verification

- Isolated OpenCode v2.2.5 CLI probe: `mcp add --global --url` preserved a literal file reference without a token present. Isolated config-loading checks resolved a synthetic file at runtime. The targeted helper was chosen to set `oauth: false`, avoid loading credentials during builds, and explicitly handle JSONC and conflicts without relying on CLI write formatting.
- `python3 -B -m unittest discover -s tests -p test_penpot_mcp.py -v`: all 9 tests passed, including synthetic runtime substitution through `opencode debug config --standalone` in isolated HOME/XDG directories.
- Focused build-boundary/configurator run: all 24 tests passed. Supplemental Git/default/credential/configurator checks: all 5 passed. Installer tests: all 3 passed.
- `python3 -B -m unittest discover -s tests`: 145 tests ran in 543.257 seconds; 144 passed and one failed. The only failure was the pre-existing missing-manual-Dockerfile assertion described below. Supplemental Git-default checks passed after strengthening that test while the full suite was running.
- `bash build-all.sh --validate`, `docker compose -f compose/docker-compose.yml config --quiet`, and `git diff --check`: passed.
- Reproduced `test_excluded_images_remain_manual_and_do_not_block_either_mode` failing in an isolated `git archive main` checkout. It expects manual-image Dockerfiles absent from the baseline; no unrelated files or tests were changed to hide it.
- `bash build-all.sh --build-only`: stopped at local certificate preflight with `git.lanCA.crt is missing, unreadable, empty, or exceeds byte limit; set BUILD_CERT_FILE`. Docker image building did not begin.
- Inspected the current external setup script and its `install-brooks.sh`/`update-skills.sh` token references read-only; these scripts contained no old Git-token path consumers. External repositories were not changed.

## Limits and decisions

- OpenCode v2.2.5 resolves missing, empty, and unreadable token files to an empty string without a configuration error. The docs require a valid readable key and separate authenticated plugin verification; the implementation does not claim config loading validates authorization.
- Isolated MCP listing attempts returned no registered servers despite config discovery; this is not treated as proof of either absent config or successful MCP connectivity. The runtime substitution test uses the actual config-loading seam without contacting live Penpot or changing the active OpenCode service.
- No real image was built because certificate preflight failed. Base/npm ownership and inheritance are checked statically and through isolated helper tests, not certified in a resulting image. Authenticated Penpot access and real plugin interaction remain unverified.
- Adding a copied helper required corresponding validation and private-context updates, as allowed by the plan. Its JSONC support preserves settings rather than comments; documentation makes this explicit.
- No real tokens were read, migrated, created, or printed. No host permissions, live configurations, TLS settings, remote records, or external repositories were changed. No images were published.
