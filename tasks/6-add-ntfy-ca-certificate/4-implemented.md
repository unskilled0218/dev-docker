# Implementation results

- [Implementation results](#implementation-results)
  - [Changes](#changes)
  - [Verification](#verification)
  - [Limits and prerequisites](#limits-and-prerequisites)

## Changes

- Created branch `6-add-ntfy-ca-certificate` and implemented the reviewed plan.
- Added `ntfy_certificate_file`, defaulting to `/usr/local/share/ca-certificates/ntfy.lanCA.crt`, and the nonempty `BUILD_NTFY_CERT_FILE` override. Git's existing configuration and override remain supported.
- Added shared bounded certificate selection and deterministic fingerprinting in `scripts/release_data.py`. Both inputs must be readable, nonempty files of at most 1 MiB. Errors identify the relevant certificate and override without exposing source paths or contents.
- Capture both inputs before builder operations or credential loading; copy only captured bytes into private build contexts. Both local and publication snapshots include `git.lanCA.crt` and `ntfy.lanCA.crt`.
- Bind both filenames and individual content hashes through the existing release certificate fingerprint and OCI label. Publication guards recheck both inputs and refuse changes without changing release mutation or conflict rules.
- Added the ntfy `COPY` beside Git's copy in `Dockerfile/base.Dockerfile`, before the existing `update-ca-certificates` invocation.
- Updated fake build boundaries and added eight regression test methods covering invalid inputs, selection precedence, home expansion, sanitized read errors, combined fingerprints, guard refusals, captured-byte isolation, and Dockerfile ordering. Existing integration tests now assert both distinct certificate contents; validation still succeeds with both inputs absent.
- Updated `README.md` and `docs/image-releases.md` with prerequisites, overrides, context filenames, release compatibility, and image-versus-host trust limits.
- Bumped `VERSION` from `0.1.4` to `0.1.5`, added `docs/releases/0.1.5.md`, and updated the configured notes path.

## Verification

- `python3 -B -m unittest discover -s tests -v`: passed all 94 tests in 492.682 seconds. External Git, Docker, and curl service boundaries use offline fixtures; no real publication occurred.
- `bash -n build-all.sh`: passed.
- `bash build-all.sh --validate`: passed with `Configuration valid; no credentials or external operations used`.
- `git diff --check`: passed.
- An earlier focused `test_build_all.py` run reached the 120-second harness timeout before completion. The subsequent complete suite finished successfully with a longer timeout; no test failures were reported.

## Limits and prerequisites

Provide both valid CA files before real builds, using the configured defaults or their overrides. No certificates were downloaded, installed on the host, or committed. Offline tests establish input handling, context contents, and Dockerfile ordering, not certificate validity or live ntfy HTTPS trust. No native Docker builds, registry publication, TLS bypass, notification configuration changes, or remote release changes were performed. The combined fingerprint intentionally differs from the old Git-only identity; preserve conflict refusals for older release evidence.
