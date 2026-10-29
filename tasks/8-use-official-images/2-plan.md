# plan

- [plan](#plan)
  - [scope](#scope)
  - [Implementation Plan](#implementation-plan)
    - [Summary](#summary)
    - [1. Verify the upstream Playwright image](#1-verify-the-upstream-playwright-image)
    - [2. Add a standalone Playwright server](#2-add-a-standalone-playwright-server)
    - [3. Remove duplicate installation from the npm image](#3-remove-duplicate-installation-from-the-npm-image)
    - [4. Update Compose and usage documentation](#4-update-compose-and-usage-documentation)
    - [5. Add regression checks and validate](#5-add-regression-checks-and-validate)
  - [Acceptance Criteria](#acceptance-criteria)
  - [Risks And Decisions](#risks-and-decisions)

## scope

Run the official Playwright image as a separate browser-server container, accessible from development containers over a shared Docker network. Keep `Dockerfile/base.Dockerfile` based on Ubuntu and remove local browser installation from the npm image. This supersedes the original goal's image-inheritance interpretation and OpenCode migration. Leave the current OpenCode installation, setup script, command, authentication, and port unchanged. Preserve the `base` then `npm` release graph, non-root development account, internal certificate trust, Docker access, skills, and project mounts. Do not change unrelated manual images, release publication logic, standalone network-test files, or `todo.md`.

## Implementation Plan

### Summary

Create `compose/playwright-compose.yml` for a standalone Playwright server on an explicitly named `development` bridge network. The server project owns the network; `compose/docker-compose.yml` and independent client projects join it as an external network. Tests run in client containers while browsers run in the Playwright container. Do not derive the base image from Playwright or move OpenCode to another container.

### 1. Verify the upstream Playwright image

- Select an explicit published version of `mcr.microsoft.com/playwright` with the `noble` suffix; record the resolved tag and preferably its digest. The previously consulted official documentation shows `v1.64.1-noble`; verify availability and suitability rather than assuming that example is the desired release.
- Verify the selected image's non-root `pwuser`, writable working directory, browser paths, and Node/npm support. Verify the matching `playwright` package supports `run-server --host 0.0.0.0 --port 3000` and the client package supports remote WebSocket connections.
- Verify a lightweight WebSocket readiness probe against the chosen server version using the image's existing Node runtime. Confirm its handshake requirements and clean connection shutdown before choosing the healthcheck command; DNS resolution or an open TCP socket alone is insufficient. Select and verify a deliberately incompatible client/server version pair for the failure-path smoke test.

### 2. Add a standalone Playwright server

- Add `compose/playwright-compose.yml` with a distinct explicit Compose project name and a `playwright` service using the pinned official Noble image directly. Run as `pwuser` in `/home/pwuser`, with `init: true` and bounded Chromium shared memory such as `shm_size: "1gb"`.
- Start the matching package with `npx -y playwright@<version> run-server --host 0.0.0.0 --port 3000`. The image provides browsers and libraries, not the Playwright JavaScript package; this command installs only the server package and requires registry access on a cold start. Do not run browser installation commands.
- Add a Compose healthcheck that completes the verified WebSocket handshake against `ws://127.0.0.1:3000/`, closes the connection, and exits nonzero on timeout or handshake failure. Use the available Node runtime without downloading packages or launching browsers on each probe. Set `interval: 5s`, `timeout: 3s`, `start_period: 45s`, and `retries: 12`; bound the probe's own connection attempt below the Compose timeout and ensure connections do not accumulate.
- Define a bridge network with the explicit Docker name `development` and attach `playwright`. Do not publish port 3000 to the host, mount the Docker socket or credentials, or share the entire workspace with the browser server by default.
- Keep `Dockerfile/base.Dockerfile` unchanged, including Ubuntu ancestry, certificates, UID/GID, development tools, setup script, BuildKit secret, and server command.

### 3. Remove duplicate installation from the npm image

- Keep the exact initial `ARG BASE_IMAGE=base:latest` and `FROM ${BASE_IMAGE}` lines in `Dockerfile/npm.Dockerfile`; release validation requires that prefix.
- Remove `playwright install-deps` and `playwright install`; browser executables and system dependencies belong only in the separate server container.
- Retain the current Python and Node/npm installation, npm user prefix, ownership, working directory, and non-root account.
- Install only the Playwright JavaScript client package needed for existing development usage, pinned to the exact server/image version. Set `PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1` during package installation to explicitly prevent browser downloads. Preserve package accessibility for the `container` account and document that downstream projects must install the matching client package themselves.

### 4. Update Compose and usage documentation

- Keep `app` using `git.lan/dev/base:latest`. Attach it to an external network named `development`, and set `PW_TEST_CONNECT_WS_ENDPOINT=ws://playwright:3000/` for Playwright Test clients. Explain that base has no Node/client package; use the npm image or a project-specific client container when running JavaScript tests.
- Preserve port 4096, the project working directory, interactive settings, Docker socket access, and all existing credential bind mounts with their read-only and missing-source protections. Do not change OpenCode commands or authentication.
- Add `docs/playwright.md` with a table of contents, server startup before clients, shutdown of clients before the server, exact package/image version alignment, and the startup network/download requirement. Link it briefly from `README.md` and update release documentation only where npm runtime behavior changed.
- Document `docker compose -f compose/playwright-compose.yml up -d --wait --wait-timeout 120` as the server startup command. Explain that independent Compose projects cannot use cross-project `depends_on` to establish readiness. If startup fails or times out, stop the client startup sequence and inspect the server's health status and logs for package-download or server-start failures; do not remove unrelated containers or networks.
- Provide a matching-client connection example for independent containers with a 60-second overall deadline, individual `.connect()` attempts limited to 5 seconds, and a 2-second delay between retryable connection failures. Close the probe connection before running tests; configure a finite connection timeout for the actual test/library connection too. Stop immediately on known version incompatibility, and never fall back to local `.launch()`. On final failure, report the endpoint, elapsed time, and last connection error with guidance to inspect server health/logs and confirm version alignment. Redact any credentials embedded in endpoint URLs.
- Document both client approaches: Playwright Test through `PW_TEST_CONNECT_WS_ENDPOINT`, and library usage through `chromium.connect('ws://playwright:3000/')` with a version-matched `playwright` package. A network connection or endpoint environment variable alone does not redirect arbitrary `.launch()` calls or automatically configure every tool integration.
- Include an independent Compose example declaring `external: true` and `name: development`, plus `docker network connect development <container>` for an existing container. Do not require clients to share a Compose project or workspace mount with the server.
- Explain browser-side addressing: applications bind to `0.0.0.0` and are reached using their service names or unique network aliases, not client `localhost`. Avoid duplicate service aliases across projects. Document explicit shared mounts only for workflows that require server-local files.

### 5. Add regression checks and validate

- Add focused offline tests for the pinned official server image and matching server/client package versions, absence of browser installation in development Dockerfiles, preserved child-image prefix and unchanged base, external network linkage, WebSocket endpoint, non-root browser server, and absence of host port publication or credential mounts on that server. Follow the existing standard-library test style without adding a YAML dependency solely for assertions.
- Include offline configuration assertions for the healthcheck timing and failure exit behavior. Exercise client wait-example deadline/retry logic with controlled time and connection outcomes where practical, keeping real network tests separate from the offline suite.
- Preserve the existing certificate-order regression and release safety tests. Run `python3 -B -m unittest discover -s tests -v`, `bash -n build-all.sh`, `bash build-all.sh --validate`, and `git diff --check`.
- Run Compose configuration validation separately for `compose/playwright-compose.yml` and `compose/docker-compose.yml`, with the required host mount inputs present. Do not start the normal application stack against the user's project or credentials for validation.
- When Docker and the existing build prerequisites are available, run `bash build-all.sh --build-only`; do not publish. Smoke-test both resulting images using disposable containers and a temporary workspace, without host credential or Docker socket mounts: verify UID/GID, `HOME`, Git, Docker CLI, skills, certificate files, existing server startup behavior, and Node/npm where applicable.
- Test the server and two independent client Compose projects using a unique temporary network name through test-only overrides, without taking ownership of an existing `development` network. Verify both clients resolve `playwright` and connect over WebSocket; ensure an unattached client cannot resolve the service through that network.
- From the npm client image, connect to Chromium, Firefox, and WebKit through the server, load an HTTP page served by another container using its network alias, and exit cleanly. Test Playwright Test's environment-variable connection separately from direct library `.connect()`. Confirm no local browser installation is needed. Remove only test-owned containers, volumes, and networks.
- Add isolated delayed-start and failed-start smoke scenarios. Verify server startup waits for health, independent clients recover from a delay within their 60-second deadline, and an unavailable or failed server produces a bounded nonzero result with actionable diagnostics. Simulate a package-fetch/start failure without changing production credentials or registry settings. Confirm no local browser fallback and no accumulating readiness connections.
- Run one smoke check with the verified incompatible client/server pair. Require a bounded nonzero result and record the actual mismatch diagnostic plus the matching-version remedy; distinguish it from DNS/connection failures without asserting exact upstream error wording. Keep this network-dependent check outside the offline suite and do not accept a generic timeout as proof of version-mismatch detection.
- Record unavailable prerequisites or skipped runtime checks explicitly. Offline text assertions and release fixtures are not evidence that browsers actually run.

## Acceptance Criteria

- A standalone pinned official Playwright container serves browsers privately at `ws://playwright:3000/` on the explicitly named `development` network.
- The base Dockerfile remains unchanged. The npm image contains a matching JavaScript client package but no downloaded browsers or browser-specific system dependency installation.
- Independent Compose projects and existing containers can join the shared network and control remote browsers without sharing the server's Compose project.
- Both development images retain their non-root account, certificate trust, skills, and build/release interface. Existing OpenCode setup and behavior remain unchanged.
- Compose preserves existing application access and protected mounts; only the browser server receives browser-specific initialization and shared-memory settings. Port 3000 is not published to the host.
- The documented server startup waits for verified WebSocket readiness within 120 seconds. Independent client connection waits are bounded to 60 seconds and fail clearly when the server is unavailable, without installing or launching local browsers.
- Runtime validation covers delayed startup, failed startup, and a known incompatible client version. Failure diagnostics distinguish readiness/network errors from version mismatches; unexecuted scenarios are recorded as verification gaps.
- Offline validation passes. Available runtime checks prove all three Playwright browsers work and existing development behavior remains intact; any unexecuted check is identified as a verification gap.

## Risks And Decisions

- This task covers a separate Playwright browser service, not image inheritance. OpenCode migration, removal, and cross-container OpenCode tool execution are out of scope.
- Playwright installation currently lives in `Dockerfile/npm.Dockerfile`, not base. Updating that child is necessary to remove redundant downloads even though the goal names the base Dockerfile.
- Leave the external setup wrapper and agents repository untouched; this task does not redesign their installation behavior.
- Official Playwright images include browsers but not the JavaScript package. Image, server package, and client package versions must remain aligned, including downstream projects that bring their own package manifests.
- Health indicates readiness at probe time, not a guarantee of availability for every later request. Clients still need finite connection timeouts. Cold package downloads exceeding the 120-second startup budget fail visibly; users can inspect logs, restore registry access, and retry rather than wait indefinitely.
- The server project owns `development`; start it first and stop clients before removing it. If an unrelated network already uses that name, stop for an ownership decision rather than deleting or adopting it silently. Shared networks are trusted: any attached container can reach the browser server, so attach trusted clients only.
- Remote browsers do not automatically inherit client files, credentials, certificate trust, or localhost services. Internal HTTPS targets need explicit browser trust configuration; do not disable TLS verification globally. Confirm needed file-based test workflows separately.
- Preserve existing certificate and BuildKit secret requirements rather than redesigning credentials. Do not introduce host IPC sharing or broader browser privileges without a demonstrated need and explicit approval.
- Source: [official Playwright Docker guide](https://playwright.dev/docs/docker). Registry inspection and runtime verification are still required during implementation.
