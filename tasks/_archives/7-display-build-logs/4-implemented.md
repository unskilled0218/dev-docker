# Implementation results

- [Implementation results](#implementation-results)
  - [Changes](#changes)
  - [Verification](#verification)
  - [Decisions and limits](#decisions-and-limits)

## Changes

- Created branch `7-display-build-logs` and implemented the updated plan, including both review findings.
- Added `scripts/release_logs.py` with bounded record filtering, supported Docker credential extraction, and a supervised writer. Known token/auth/password/proxy values, standard URL encodings, private paths, recognizable authorization/credential records, URLs, and terminal controls are handled before display. Strict Base64 Docker auth extraction protects decoded passwords as well as encoded values.
- Added opt-in observation to the existing selector-driven process runner. Default capture and command return values remain unchanged. Only actual Docker Buildx builds enable filtered output; authenticated API calls, Git, registry login, and promotion commands remain private.
- The writer receives only sanitized framed records through nonblocking communication with acknowledgments after stderr delivery. Pending packets are capped at 256 KiB, record delivery has a five-second deadline, input records are capped at 64 KiB, and displayed records at 128 KiB. Process-group cleanup and bounded waits cover Docker and the writer on failure or interruption.
- Added `--progress=plain` to both build modes and fixed-label stderr phase messages for preflight, inventories, snapshot preparation, image preparation/build/reuse/verification, login, package association, tag/alias/release publication, and final verification. Helper decisions and existing final summaries retain their stdout behavior.
- Prepared redaction inputs from the effective Docker config without copying caller auth into publication or invoking credential helpers for filtering. Invalid supported auth/config inputs refuse before builds. Added the logging module to the release-script fingerprint.
- Extended the fake Docker boundary with progress, step failures, and synthetic sensitive markers. Added 26 test methods covering filtering, actual subprocess delivery/supervision, and command-level outcomes, including decoded foreign-registry passwords, undrained open output pipes, short-record bursts, and real interruption during blocked delivery.
- Updated README and detailed build-log/privacy documentation. Bumped `VERSION` from `0.1.6` to `0.1.7`, added matching release notes, and updated the configured notes path.

## Verification

- `python3 -B -m unittest discover -s tests -v`: passed all 120 tests in 567.720 seconds against the final implementation. Output was captured privately in `/tmp/opencode/7-build-logs-final-tests.log` for verification, not as an application raw-log feature.
- Focused checks: all 25 initial logging tests passed before the burst-delivery regression was added; the final filter/streaming subset then passed all 18 tests, including that new case. The final full suite includes all 26 new logging tests.
- `bash -n build-all.sh`: passed.
- `bash build-all.sh --validate`: passed with `Configuration valid; no credentials or external operations used`.
- `git diff --check`: passed.
- Initial focused runs exposed an overbroad credential-record match, a missing original percent-encoded proxy component, and test assumptions about pipe capacity and preflight rejection timing. Corrected the implementation and fixtures before final verification. A subsequent inspection also identified one-record-per-poll delivery throttling; nonblocking batch delivery and a shorter pending-output poll interval now handle bursts without weakening queue or deadline limits.

## Decisions and limits

- Preserved the existing 16 MiB stdout, 1 MiB stderr, and 7,200-second build limits. Display filtering never changes captured release evidence or grants retry/reconciliation authority.
- Supported credential fields and decoded auth pairs containing control characters refuse before display preparation; otherwise record delimiters could split a known secret. This is a fail-closed clarification of supported credential forms.
- Standard Docker auth encodings and known values are covered, not arbitrary transformations, unknown secrets printed by downloaded scripts, or credentials held only by external helpers. Logs still require private inspection before sharing.
- Undrained build-log destinations stop supervised execution; ordinary shell progress/error output outside the capture loop remains subject to normal shell output behavior. No host stderr flags or caller configuration are changed.
- No native Docker build, real registry login, service probe, host trust change, TLS bypass, remote publication, or remote repair was performed. Offline fixtures do not certify native Buildx behavior or the privacy of arbitrary build scripts. Repeated Bash error traps remain unchanged as planned.
