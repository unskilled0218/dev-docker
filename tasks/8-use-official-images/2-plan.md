# plan

- [plan](#plan)
  - [scope](#scope)
  - [Implementation Plan](#implementation-plan)
    - [Summary](#summary)
    - [1. Verify the upstream Playwright image](#1-verify-the-upstream-playwright-image)
    - [2. Build the development base from Playwright](#2-build-the-development-base-from-playwright)
    - [3. Remove duplicate installation from the npm image](#3-remove-duplicate-installation-from-the-npm-image)
    - [4. Update Compose and usage documentation](#4-update-compose-and-usage-documentation)
    - [5. Add regression checks and validate](#5-add-regression-checks-and-validate)
  - [Acceptance Criteria](#acceptance-criteria)
  - [Risks And Decisions](#risks-and-decisions)

## scope

Use the official Playwright image as the development base, remove redundant Playwright installation, and update `compose/docker-compose.yml`. The user's latest instruction removes OpenCode migration from this task, superseding that part of `1-goal.md`. Leave the current OpenCode installation, setup script, command, authentication, and port unchanged. Preserve the `base` then `npm` release graph, non-root development account, internal certificate trust, Docker access, skills, and project mounts. Do not change unrelated manual images, release publication logic, standalone network-test files, or `todo.md`.

## Implementation Plan

### Summary

Use the official Ubuntu Noble Playwright image as the final base. Inherit browsers and system libraries rather than downloading them again in the npm image. Keep the existing application service and all unrelated setup behavior.

### 1. Verify the upstream Playwright image

- Select an explicit published version of `mcr.microsoft.com/playwright` with the `noble` suffix; record the resolved tag and preferably its digest. The previously consulted official documentation shows `v1.64.1-noble`; verify availability and suitability rather than assuming that example is the desired release.
- Inspect the AMD64 image's users, groups, environment, browser paths, Node/npm versions, entrypoint, and command. Confirm Ubuntu 24.04 compatibility with the existing development setup and browser access for UID/GID 1000.

### 2. Build the development base from Playwright

- Change `Dockerfile/base.Dockerfile` to use the verified, version-pinned Playwright Noble image instead of `ubuntu:24.04`. Do not add an OpenCode source stage or service.
- Explicitly select root for image setup, then reuse or rename the appropriate upstream account to retain `container` with UID/GID 1000 and `/home/container`. Handle upstream account/group names and an existing Docker group without assuming the plain Ubuntu account layout.
- Preserve both certificate copies before `update-ca-certificates`, the existing development packages and Docker CLI setup, the required BuildKit `token` secret contract, and the final non-root user. Keep inherited browser paths available and readable by that user.
- Keep the existing external `scripts/setup.sh` invocation and final server command unchanged. Check inherited entrypoint behavior and clear an upstream entrypoint only if necessary to preserve the existing command's behavior.

### 3. Remove duplicate installation from the npm image

- Keep the exact initial `ARG BASE_IMAGE=base:latest` and `FROM ${BASE_IMAGE}` lines in `Dockerfile/npm.Dockerfile`; release validation requires that prefix.
- Remove `playwright install-deps` and `playwright install`, since browsers and system libraries now come from the base image.
- Retain Python, the npm user prefix, ownership, and user-facing Node/npm behavior. Reuse inherited Node/npm when it meets the existing supported requirement; avoid layering a second Node installation over the official image without a demonstrated need.
- Install only the Playwright JavaScript package needed for existing development usage, pinned to the exact browser-image version. The official Playwright image does not include that package. Preserve its usable location and permissions for the `container` account, and explain that downstream projects must match this version.

### 4. Update Compose and usage documentation

- Keep `app` using `git.lan/dev/base:latest`, now derived from the official Playwright image, rather than a bare upstream image that lacks certificates, skills, or development tooling. Document that the npm image provides the JavaScript package while base provides the browsers and libraries.
- Add `init: true` for browser subprocess reaping and a bounded `shm_size` for Chromium. Keep container execution non-root; do not add privileged mode, `SYS_ADMIN`, or disable browser sandboxing as a default workaround.
- Preserve port 4096, the project working directory, interactive settings, Docker socket access, and all existing credential bind mounts with their read-only and missing-source protections. Do not add OpenCode networking, command, or environment changes.
- Add `docs/development-images.md` with a table of contents covering the upstream Playwright version, inherited browsers, package/browser version matching, Compose startup, and smoke checks. Link it briefly from `README.md` and adjust `docs/image-releases.md` only where build prerequisites or inherited runtime behavior changed.

### 5. Add regression checks and validate

- Add focused offline tests for the official Playwright image input, absence of redundant browser download commands, package/browser version alignment, preserved child-image prefix, unchanged existing setup/server behavior, and Compose runtime settings and mounts. Follow the existing standard-library test style without adding a YAML dependency solely for assertions.
- Preserve the existing certificate-order regression and release safety tests. Run `python3 -B -m unittest discover -s tests -v`, `bash -n build-all.sh`, `bash build-all.sh --validate`, and `git diff --check`.
- Run `docker compose -f compose/docker-compose.yml config --quiet` with the required host mount inputs present. Do not start the normal Compose stack against the user's project or credentials for validation.
- When Docker and the existing build prerequisites are available, run `bash build-all.sh --build-only`; do not publish. Smoke-test both resulting images using disposable containers and a temporary workspace, without host credential or Docker socket mounts: verify UID/GID, `HOME`, Git, Docker CLI, skills, certificate files, existing server startup behavior, and Node/npm where applicable.
- In the npm image, launch Chromium, Firefox, and WebKit through the version-matched Playwright package as `container`, load local content, and exit cleanly. Remove only test-owned resources.
- Record unavailable prerequisites or skipped runtime checks explicitly. Offline text assertions and release fixtures are not evidence that browsers actually run.

## Acceptance Criteria

- The final development base inherits browsers and their libraries from a pinned official Playwright Noble image.
- Neither development Dockerfile downloads Playwright browsers or reinstalls their system dependencies. A version-matched Playwright JavaScript package remains available in the npm image.
- Both images retain a working non-root `container` account, certificate trust, skills, and the existing build/release interface. Existing OpenCode setup and behavior remain unchanged; no OpenCode image migration or network split is implemented.
- Compose includes the required initialization and browser shared-memory settings while preserving the existing project access, port, and protected credential mounts.
- Offline validation passes. Available runtime checks prove all three Playwright browsers work and existing development behavior remains intact; any unexecuted check is identified as a verification gap.

## Risks And Decisions

- This task now covers Playwright only. OpenCode migration, removal, separate containers, and cross-container tool execution are out of scope.
- Playwright installation currently lives in `Dockerfile/npm.Dockerfile`, not base. Updating that child is necessary to remove redundant downloads even though the goal names the base Dockerfile.
- Leave the external setup wrapper and agents repository untouched; this task does not redesign their installation behavior.
- Official Playwright images include browsers but not the JavaScript package. Browser/package versions must remain aligned, including downstream projects that bring their own package manifests.
- Preserve existing certificate and BuildKit secret requirements rather than redesigning credentials. Do not introduce host IPC sharing or broader browser privileges without a demonstrated need and explicit approval.
- Source: [official Playwright Docker guide](https://playwright.dev/docs/docker). Registry inspection and runtime verification are still required during implementation.
