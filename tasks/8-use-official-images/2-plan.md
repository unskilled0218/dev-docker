# plan

- [plan](#plan)
  - [scope](#scope)
  - [Implementation Plan](#implementation-plan)
    - [Summary](#summary)
    - [1. Verify upstream image contracts](#1-verify-upstream-image-contracts)
    - [2. Build the development base from official images](#2-build-the-development-base-from-official-images)
    - [3. Remove duplicate installation from the npm image](#3-remove-duplicate-installation-from-the-npm-image)
    - [4. Update Compose and usage documentation](#4-update-compose-and-usage-documentation)
    - [5. Add regression checks and validate](#5-add-regression-checks-and-validate)
  - [Acceptance Criteria](#acceptance-criteria)
  - [Risks And Decisions](#risks-and-decisions)

## scope

Use official Playwright and OpenCode images as build inputs for the existing development image, remove redundant tool installation, and update `compose/docker-compose.yml`. Preserve the `base` then `npm` release graph, the non-root development account, internal certificate trust, Docker access, skills, project mounts, and OpenCode access on port 4096. Do not change unrelated manual images, release publication logic, or `todo.md`.

## Implementation Plan

### Summary

Use the official Ubuntu Noble Playwright image as the final base and the official OpenCode image as a named source stage. Import the verified OpenCode runtime rather than running its installer. Keep one Compose development service so OpenCode tools, project files, and browsers share the same environment.

### 1. Verify upstream image contracts

- Select explicit published versions for `mcr.microsoft.com/playwright` with the `noble` suffix and `ghcr.io/anomalyco/opencode`; record the resolved tags and preferably digests. The official documentation currently shows Playwright `v1.64.1-noble` and OpenCode `2.0.0` as examples; verify availability rather than assuming either example is the desired release.
- Inspect the AMD64 images' users, groups, environment, executable locations, entrypoints, and runtime dependencies. Verify the OpenCode binary and its required assets can run on Ubuntu 24.04; do not copy a musl-linked executable into Ubuntu without its required runtime.
- Check the chosen OpenCode version's help and official V2 documentation for a supported foreground server command, network binding, authentication, and port configuration. Preserve the existing access contract where supported, and document any required client change rather than guessing V1 compatibility.
- Stop for a design decision if the official OpenCode runtime cannot be imported safely; do not silently restore an installer or split services with different tool environments.

### 2. Build the development base from official images

- Change `Dockerfile/base.Dockerfile` to declare the version-pinned OpenCode source stage and use the verified Playwright Noble image for the final stage. Copy only the verified OpenCode executable and required runtime assets into stable paths, and expose `opencode` through `PATH`.
- Explicitly select root for image setup, then reuse or rename the appropriate upstream account to retain `container` with UID/GID 1000 and `/home/container`. Handle upstream account/group names and an existing Docker group without assuming the plain Ubuntu account layout.
- Preserve both certificate copies before `update-ca-certificates`, the existing development packages and Docker CLI setup, the required BuildKit `token` secret contract, and the final non-root user. Keep inherited browser paths available and readable by that user.
- Remove the indirect OpenCode installation: the current external `scripts/setup.sh` unconditionally runs the OpenCode installer. Replace that wrapper with the existing dedicated Brooks and custom-skill setup operations, retaining creation of the work directory and `command.md`. Do not edit the external agents repository or filter downloaded shell scripts to remove installer lines.
- Set the final command explicitly so neither upstream entrypoint accidentally overrides the development server. Use an exec-form command and the server invocation verified in step 1; retain the intended authentication behavior without adding new secrets to source files.

### 3. Remove duplicate installation from the npm image

- Keep the exact initial `ARG BASE_IMAGE=base:latest` and `FROM ${BASE_IMAGE}` lines in `Dockerfile/npm.Dockerfile`; release validation requires that prefix.
- Remove `playwright install-deps` and `playwright install`, since browsers and system libraries now come from the base image.
- Retain Python, the npm user prefix, ownership, and user-facing Node/npm behavior. Reuse inherited Node/npm when it meets the existing supported requirement; avoid layering a second Node installation over the official image without a demonstrated need.
- Install only the Playwright JavaScript package needed for existing development usage, pinned to the exact browser-image version. The official Playwright image does not include that package. Preserve its usable location and permissions for the `container` account, and explain that downstream projects must match this version.

### 4. Update Compose and usage documentation

- Keep `app` using the locally published development image derived from the official inputs, rather than pointing it at a bare upstream image that lacks certificates, skills, or development tooling. Retain `git.lan/dev/base:latest` if all required runtime capabilities are in base; verify this choice against the package placement in step 3.
- Add `init: true` for browser subprocess reaping and a bounded `shm_size` for Chromium. Keep container execution non-root; do not add privileged mode, `SYS_ADMIN`, or disable browser sandboxing as a default workaround.
- Preserve port 4096, the project working directory, interactive settings, Docker socket access, and all existing credential bind mounts with their read-only and missing-source protections. Add only command/environment overrides required by the verified runtime contract.
- Add `docs/development-images.md` with a table of contents covering upstream versions, the multistage arrangement, package/browser version matching, Compose startup, and smoke checks. Link it briefly from `README.md` and adjust `docs/image-releases.md` only where build prerequisites or inherited runtime behavior changed.

### 5. Add regression checks and validate

- Add focused offline tests for the two official image inputs, absence of the OpenCode installer wrapper and browser download commands, package/browser version alignment, preserved child-image prefix, and Compose runtime settings and mounts. Follow the existing standard-library test style without adding a YAML dependency solely for assertions.
- Preserve the existing certificate-order regression and release safety tests. Run `python3 -B -m unittest discover -s tests -v`, `bash -n build-all.sh`, `bash build-all.sh --validate`, and `git diff --check`.
- Run `docker compose -f compose/docker-compose.yml config --quiet` with the required host mount inputs present. Do not start the normal Compose stack against the user's project or credentials for validation.
- When Docker and the existing build prerequisites are available, run `bash build-all.sh --build-only`; do not publish. Smoke-test both resulting images using disposable containers and a temporary workspace, without host credential or Docker socket mounts: verify UID/GID, `HOME`, Git, Docker CLI, skills, certificate files, `opencode --version`, and Node/npm where applicable.
- In the npm image, launch Chromium, Firefox, and WebKit through the version-matched Playwright package as `container`, load local content, and exit cleanly. Verify the foreground OpenCode server becomes reachable on port 4096 using the documented endpoint and authentication for the chosen version, then remove only test-owned resources.
- Record unavailable prerequisites or skipped runtime checks explicitly. Offline text assertions and release fixtures are not evidence that an imported binary or browser actually runs.

## Acceptance Criteria

- The final development base inherits browsers and their libraries from a pinned official Playwright Noble image and obtains OpenCode from a pinned official OpenCode image.
- Neither development Dockerfile nor its invoked setup path reinstalls OpenCode or downloads Playwright browsers/system dependencies. A version-matched Playwright JavaScript package remains available in the npm image.
- Both images retain a working non-root `container` account, certificate trust, skills, and the existing build/release interface; OpenCode can execute tools in the same workspace as the browsers.
- Compose includes the required initialization and browser shared-memory settings while preserving the existing project access, port, and protected credential mounts.
- Offline validation passes. Available runtime checks prove the imported OpenCode runtime and all three Playwright browsers work; any unexecuted check is identified as a verification gap.

## Risks And Decisions

- Multistage composition is the planned interpretation of “use official images”; separate OpenCode and Playwright services would require a new remote-browser contract and are outside this plan.
- Playwright installation currently lives in `Dockerfile/npm.Dockerfile`, not base. Updating that child is necessary to remove redundant downloads even though the goal names the base Dockerfile.
- OpenCode installation currently lives inside a mutable external setup script. Bypassing that wrapper must preserve its skill setup without depending on an undocumented skip flag or changing another repository.
- The OpenCode image's executable path, libc compatibility, runtime assets, and V2 server behavior remain implementation gates. No unverified `COPY` path or inherited V1 server flag is assumed to work.
- Official Playwright images include browsers but not the JavaScript package. Browser/package versions must remain aligned, including downstream projects that bring their own package manifests.
- Preserve existing certificate and BuildKit secret requirements rather than redesigning credentials. Do not introduce host IPC sharing or broader browser privileges without a demonstrated need and explicit approval.
- Sources consulted: [official Playwright Docker guide](https://playwright.dev/docs/docker), [official OpenCode V2 introduction](https://opencode.ai/v2/docs/), and [official OpenCode V2 CLI guide](https://opencode.ai/v2/docs/cli). Registry inspection and runtime verification are still required during implementation.
