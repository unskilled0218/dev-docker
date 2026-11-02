# plan

- [plan](#plan)
  - [Scope](#scope)
  - [Implementation Plan](#implementation-plan)
    - [1. Harden the local installer](#1-harden-the-local-installer)
    - [2. Integrate the installer into the base image](#2-integrate-the-installer-into-the-base-image)
    - [3. Include the installer in isolated build contexts](#3-include-the-installer-in-isolated-build-contexts)
    - [4. Add regression checks and validate](#4-add-regression-checks-and-validate)
  - [Acceptance Criteria](#acceptance-criteria)
  - [Risks And Decisions](#risks-and-decisions)

## Scope

Replace the remote Docker installer with scripts/install-docker.sh, fail installation on errors, use apt-get, and clean package lists in the installation layer. Update isolated build-context handling and related tests. Do not change unrelated image setup or publication behavior.

## Implementation Plan

### 1. Harden the local installer

- Add `set -euo pipefail` immediately after the shebang in scripts/install-docker.sh.
- Replace each `apt update` and `apt install` with `apt-get update` and `apt-get install`, retaining noninteractive installation flags and current packages.
- Preserve the Docker repository configuration and UID 1000 group membership behavior. Quote the username command substitution.

### 2. Integrate the installer into the base image

- In Dockerfile/base.Dockerfile, remove only the remote Docker installer pipeline and end the existing setup RUN with update-ca-certificates followed by package-list cleanup.
- Use apt-get for the base image's existing package operations as well.
- Before `USER ${USER_NAME}`, add `COPY scripts/install-docker.sh /tmp/install-docker.sh` and a RUN that invokes `bash /tmp/install-docker.sh`, removes the temporary script, and clears `/var/lib/apt/lists/*`, joined with `&&`.
- Keep package-list cleanup in each RUN that installs packages so lists are not retained in earlier layers. Leave the separate user setup download unchanged.

### 3. Include the installer in isolated build contexts

- Extend snapshot() in scripts/release_data.py to create context/scripts and include only scripts/install-docker.sh alongside the existing Dockerfiles and certificates.
- Follow the existing Dockerfile source rules: read the checked working-tree file for local builds and the selected Git commit blob for published builds.
- Do not copy the whole scripts directory or introduce credentials into the context.

### 4. Add regression checks and validate

- Update context allowlist assertions in tests/fake_release_ports.py and tests/test_build_all.py to allow scripts containing only install-docker.sh.
- Add snapshot tests proving local builds receive working-tree installer bytes while published builds receive selected-commit bytes, even when the working-tree installer differs.
- Add focused checks for strict mode, apt-get usage, local COPY/RUN ordering before USER, removal of the remote Docker installer, and cleanup in the installation RUN.
- Use safe subprocess mocks or temporary PATH stubs to verify a failed package command stops the installer; do not execute package installation or user changes on the host.
- Run `bash -n scripts/install-docker.sh` and `python3 -m unittest discover -s tests -p 'test_*.py'`.
- If Docker and required network access, certificates, and token are available, validate the actual base image build through the existing local build workflow. Otherwise record that a live image build was not verified; do not publish images for validation.

## Acceptance Criteria

- The base image runs the local Docker installer as root before switching to USER_NAME; no remote Docker installer is fetched.
- Installer command failures terminate the script and fail its Docker RUN.
- Relevant package commands use apt-get, and temporary installer files and apt lists are removed in the appropriate RUN layers.
- Local and published build contexts contain the correct installer version, without broadening the context beyond required files.
- Shell syntax and regression tests pass; any unavailable live build validation is explicitly reported.

## Risks And Decisions

- The existing isolated context contains only Dockerfiles and certificates. Adding COPY alone would break builds, so snapshot and test changes are required.
- Strict mode may expose previously ignored failures. Preserve failure propagation rather than masking errors.
- Keep Ubuntu 24.04, Docker packages, repository settings, group IDs, and user setup behavior unchanged.
- Installation requires network access and privileged image-build steps. Tests must not install Docker into this running container.
