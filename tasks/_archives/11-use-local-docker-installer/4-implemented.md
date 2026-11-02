# Implementation

- [Implementation](#implementation)
  - [Changes](#changes)
  - [Verification](#verification)
  - [Limits](#limits)

## Changes

- Created branch `11-use-local-docker-installer` for this task.
- Replaced the remote Docker installer in Dockerfile/base.Dockerfile with COPY and Bash execution of scripts/install-docker.sh before USER. Removed the temporary installer and cleaned apt lists in the installation RUN; also cleaned lists in the preceding package installation layer.
- Enabled `set -euo pipefail`, replaced apt with apt-get, and quoted the user lookup in the local installer.
- Included only scripts/install-docker.sh in the isolated context, using working-tree bytes locally and selected-commit bytes for publication.
- Updated context allowlist assertions and added source-selection, installer integration, and safely stubbed failure-path regression tests.
- Updated README.md, docs/image-releases.md, VERSION, scripts/release.json, and release notes for patch version `0.1.19`.

## Verification

- `bash -n scripts/install-docker.sh`: passed.
- `bash build-all.sh --validate`: passed without credentials or external operations.
- `python3 -B -m unittest discover -s tests -p 'test_install_docker.py' -v`: passed, 3 tests, including first-package failure, final-package failure, and success scenarios through safe stubs.
- Focused snapshot regression tests: passed, 2 tests covering installer source selection, exact context contents, and captured certificate bytes.
- `python3 -B -m unittest discover -s tests -p 'test_*.py'`: completed 129 tests in 546.973 seconds; 128 passed and one failed. The initial run exceeded its 120-second harness timeout; the complete rerun used no harness timeout.
- The failure is pre-existing: test_excluded_images_remain_manual_and_do_not_block_either_mode in tests/test_package_release.py:236 requires Dockerfile/switchboard.Dockerfile, removed before this task by commit `245e329` (Remove switchboard.Dockerfile). This task changes neither that test nor the deleted file. The suite is not fully green.
- `git diff --check`: passed.

## Limits

Docker server 29.9.2 and a running Docker-driver builder advertising linux/amd64 were available. `bash build-all.sh --build-only` stopped during local preflight because the configured Git CA certificate could not be read. A read-only check also found the ntfy CA unreadable. No image was built or published, no package installation ran in this container, and certificate permissions were not changed. Live image behavior remains unverified until readable certificate inputs are provided through the documented configuration or overrides. Full-suite acceptance also remains blocked by the unrelated stale Switchboard assertion; no unrelated source deletion was reverted or hidden.
