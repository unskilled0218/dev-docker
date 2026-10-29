# Implementation

- [Implementation](#implementation)
  - [Changes](#changes)
  - [Version](#version)
  - [Verification](#verification)
  - [Build and deployment limits](#build-and-deployment-limits)
  - [Scope and cleanup](#scope-and-cleanup)

## Changes

Correction (2026-10-29): The results below were recorded before later commits `1950cef`, `25cec1a`, and `169aa6b` removed the Compose port mapping and changed the base Dockerfile. The final branch no longer sets the OpenCode server password or starts that server automatically. Claims below about unchanged base or port behavior describe the earlier state, not the final branch. Runtime checks used an existing base image and do not verify a fresh final base image. See task 9 for current verification.

- Added `compose/playwright-compose.yml` with a distinct server project, official Playwright `1.64.1` Noble image pinned to registry digest `sha256:47b510dd9230bf0b9bfc9b20102241e577ea7a99334ab4c3ca19f19770e9b8ea`, non-root `pwuser`, init, 1 GiB shared memory, and no host-published browser port or credential/workspace mounts.
- The browser project owns the explicitly named `development` bridge network. The existing application Compose project joins it as an external network and exposes `PW_TEST_CONNECT_WS_ENDPOINT=ws://playwright:3000/` to clients, preserving existing mounts and port 4096.
- Added a read-only, fail-fast bind of `scripts/playwright-healthcheck.cjs`. The healthcheck verifies the WebSocket upgrade and accept key within two seconds, disconnects without initializing a browser, and uses the plan's bounded Compose timing.
- Removed browser downloads and browser-specific dependency installation from `Dockerfile/npm.Dockerfile`. Retained Python, Node/npm setup, user configuration, and the release-required parent prefix. Installed only the exact `@playwright/test@1.64.1` client with downloads explicitly disabled.
- Added `scripts/playwright-connect.cjs` with a 60-second connection deadline, five-second attempts, two-second retry delays, immediate version-rejection handling, and URL-credential redaction. The library helper returns its successful browser for reuse; its CLI closes the readiness browser before tests, with a separate five-second close limit. There is no local launch fallback.
- Added Python offline configuration tests, dependency-free Node behavioral tests, and an opt-in isolated Docker smoke runner. Updated README and dedicated Playwright/release documentation with startup order, independent clients, browser-side addressing, failure handling, and trust limits.

## Version

Updated `VERSION` from `0.1.12` to `0.1.13`, added `docs/releases/0.1.13.md`, and pointed `scripts/release.json` to the matching release notes. The ordered base/npm publication graph and release tooling remain unchanged.

## Verification

- Full Python offline suite: the final uninterrupted rerun passed all 125 tests in 574.180 seconds. Earlier verification also passed across an interrupted run and its continuation, preserving 54 completed passes and running the remaining 71 tests in 325.132 seconds.
- Focused final Python configuration suite: all five tests passed. The initial full run executed 125 tests in 594.741 seconds; its only failure was an assertion loaded before the healthcheck bind changed from short syntax to fail-fast long syntax. The updated assertions pass; the clean rerun avoids relying on that mixed-source run.
- Final Node behavioral suite: all ten tests passed using Node from a disposable existing npm-image container with networking disabled. Coverage includes valid/invalid/stalled/refused WebSocket handshakes, connection closure, delayed connection recovery, bounded deadlines, version rejection, exhausted-deadline behavior, and credential redaction. No Playwright package downloads are required by these unit tests.
- `bash -n build-all.sh`, `bash build-all.sh --validate`, both Compose configuration validations, and `git diff --check` passed. `git diff --exit-code -- Dockerfile/base.Dockerfile` confirms base is unchanged.
- Verified official-image publication and AMD64 runtime. The image reports Node `v24.22.1`, npm `11.19.1`, user `pwuser` UID/GID 1001, a writable `/home/pwuser`, and browser assets under `/ms-playwright`. No assumption that this account has UID 1000 is required.
- Built the actual updated npm Dockerfile successfully as test-owned `task8-npm-client:verification`, using the already available `git.lan/dev/base:latest` rather than rebuilding base. Verified client version `1.64.1`, Node `v24.22.2`, npm `11.19.1`, UID/GID 1000, HOME, Git, Docker CLI, skills, certificate files, and the absence of a local browser cache.
- The existing base and newly built npm image both started their inherited server command in isolated containers without host mounts or network access; local port 4096 returned HTTP 401, confirming the unchanged authenticated server startup. OpenCode reports `v2.1.4` in these images; no OpenCode installation or invocation was changed.
- Final opt-in Docker smoke runner passed again during continuation: a delayed server became healthy; two independent client projects connected; no readiness sockets remained established; Chromium, Firefox, and WebKit loaded a page served by another container through its unique network alias; Playwright Test used its endpoint environment variable; and an unattached client could not resolve the browser service.
- Incompatible client `1.63.0` against server `1.64.1` failed in 17 milliseconds with HTTP 428 and `Playwright version mismatch`, not a DNS timeout. Matching-client unavailability failed after 60001 milliseconds with actionable endpoint/health/version diagnostics and no fallback. A synthetic package/start failure made the wait-for-health startup command fail within its 120-second budget.

- The additional CLI-only smoke run was interrupted by the harness/server restart before recording a result. Preserved the completed browser/network/failure-path checks. Resumed the CLI check against the interrupted test server; its container-local npm cache reported `EINTEGRITY` from an incomplete download. Recreating only that disposable server restored health without disabling integrity checks, and the actual `playwright-connect.cjs` CLI printed `Playwright ready at ws://playwright:3000/`. Removed the interrupted clients and server/network afterward.

## Build and deployment limits

- `bash build-all.sh --build-only` was attempted but stopped during local preflight because the configured Git CA file is unreadable. Both configured CA files exist but have mode 0600 and are unreadable by the current user. No permissions, ownership, certificate sources, or build preflight checks were changed to bypass this restriction. Provide readable CA files through `BUILD_CERT_FILE` and `BUILD_NTFY_CERT_FILE` to run the complete two-image build later.
- The successful child-image build uses an existing base image, so it does not prove a fresh execution of the mutable external base setup script. That full-build verification remains blocked, not passed.
- The Docker daemon cannot access this checkout's absolute bind paths. Browser smoke tests therefore used test-only Compose configurations with the identical healthcheck source inlined, while client helper files were copied into disposable containers. This verifies the real server, client package, readiness logic, network topology, and browser execution, but not the default healthcheck file bind on this host.
- Production Compose deployments must make the readiness script visible on the daemon host or explicitly override its source path. The bind refuses missing paths rather than creating a host directory. Normal application credential/workspace mounts were validated as configuration only; the production stack was not started.
- Client wait examples rely on Playwright honoring its finite `.connect()` timeout; unit tests inject controlled clocks and connection results. Registry access is still required for a cold server package installation. Browser-side internal CA trust, file-based workflows, arbitrary third-party integrations, and hardened browsing of untrusted sites were not certified.

## Scope and cleanup

Branch: `8-use-official-images`. Base Dockerfile, external agents setup, OpenCode configuration, manual images, release scripts, `todo.md`, and the standalone `~/workdir/test.yml`, `test2.yml`, and `opencode.yml` files were not changed. No images were published and no existing development network was adopted or modified. Test Compose projects used randomized names and networks; all test containers and networks were removed. The pulled official image and test-built client image remain cached for reproducibility and diagnostics.
