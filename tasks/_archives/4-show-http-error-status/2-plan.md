# plan

- [scope](#scope)
- [Implementation Plan](#implementation-plan)
  - [1. Include validated status codes in HTTP failure messages](#1-include-validated-status-codes-in-http-failure-messages)
  - [2. Add diagnostic and safety regressions](#2-add-diagnostic-and-safety-regressions)
  - [3. Update documentation and release metadata](#3-update-documentation-and-release-metadata)
  - [4. Verify offline](#4-verify-offline)
- [Acceptance Criteria](#acceptance-criteria)
- [Risks And Decisions](#risks-and-decisions)

## scope

Show the actual HTTP status code when a release HTTP request fails a status check. Preserve credential privacy, existing success/absence/authentication rules, exception types, and mutation safeguards. This task changes diagnostics only; it does not diagnose or fix the user's server permissions, retry publication, or remove duplicate Bash error-handler output. This planning stage modifies no implementation code.

## Implementation Plan

### 1. Include validated status codes in HTTP failure messages

- In `scripts/release_io.py:http`, retain bounded capture, transport-failure handling, inventory budgets, and strict three-digit status parsing. After parsing, include the numeric code in the existing allowlist refusal, for example `Unexpected HTTP status: 403`. Keep the accepted transport-level statuses exactly `200`, `201`, `401`, and `404`.
- Keep malformed status output and transport failures sanitized. Never interpolate raw curl stdout/stderr, body bytes, reason phrases, response headers, request URLs/query strings, payloads, authentication data, or credential paths into an exception. If transport/capture/status parsing fails, retain a non-status diagnostic rather than inventing a server response code. Preserve resource-limit precedence where capture refuses before a usable response is available.
- Include validated numeric status codes in caller-level status refusals too. Cover `scripts/release_data.py:api_read`, package-link acceptance in `link_package`, release/tag API inventory reads in `inventory_scan`, and release creation in `dispatch`; cover registry-token acceptance and final registry evidence checks in `scripts/release_io.py:registry`. For example, a package read rejected with the transport-allowed `404` must still report `HTTP 404` instead of losing the code in `Package/repository evidence unavailable`.
- Retain existing contextual refusal text and recovery guidance where practical, adding the code rather than replacing useful context. Use simple message formatting at the existing guards; do not introduce a new logging system, configuration flag, exception hierarchy, or broad transport rewrite.
- Preserve successful `401` registry challenge handling and confirmed `404` manifest absence. Do not print warnings for responses that the existing protocol treats as normal control flow. Do not label a successful-status response with malformed JSON, conflicting identity, or bad digest as an HTTP-status failure.
- Keep status refusals as `Refusal`, not `CommandFailed`. Status-only edits must not grant lost-response reconciliation authority or change which operations Bash attempts next.

### 2. Add diagnostic and safety regressions

- Add focused standard-library tests in the existing boundary suite, or a dedicated small HTTP-diagnostics test module if clearer. Mock `capture` to exercise the real `release_io.http` status parsing and refusal logic without network access.
- Check rejected statuses such as `302`, `400`, `403`, `429`, and `500` include the exact parsed code. Check transport-allowed `401`/`404` are returned normally at the boundary and that their caller-level rejection messages include the code where those callers require success. Exercise a package-link `200` rejected by its `201` contract and a release-create `404` rejection without performing real writes.
- Cover malformed/empty status output and nonzero curl exit status. Put synthetic secrets into captured stderr, response bodies, sensitive headers, and request/payload metadata, then assert exception text and CLI output do not expose those markers. Keep existing byte/time-limit and duplicate-JSON protections intact.
- Extend `tests/test_package_release.py:test_package_http_errors_and_unsupported_versions_refuse_without_writes` or add a focused CLI case using `tests/fake_release_ports.py` response overrides. A startup `403` must reach stderr with its code, return failure, and record zero login/build/push/link/tag/release effects. Include a `404` case to cover a caller-level refusal, not only the transport allowlist.
- Retain regression coverage for registry challenge flow, confirmed manifest absence, unknown/hidden package evidence, failed prerequisite reads, lost mutation responses, and completed read-only retries. Assert behavioral outcomes rather than freezing every surrounding error-message character or the number of repeated Bash trap messages.

### 3. Update documentation and release metadata

- Keep `README.md` changes minimal and relevant: point operators to release-error guidance in `docs/image-releases.md`, without duplicating the guide.
- In `docs/image-releases.md`, document example status-bearing errors, that status codes help distinguish failures but do not prove their cause, and that `403` can indicate insufficient permissions. State that raw request/response data and credentials remain hidden, and that adding a code changes neither refusal rules nor retry authority.
- During implementation, advance patch version `0.1.2` to `0.1.3` if still current, add matching `docs/releases/0.1.3.md`, and update `scripts/release.json`'s notes path together. Preserve historical notes. Note that this is a diagnostic-only fix and does not imply a successful production release.
- Record implementation and verification in this task's `4-implemented.md`. Include tables of contents for new Markdown documents and new guide headings.

### 4. Verify offline

- Run focused diagnostic tests, `python3 -B -m unittest discover -s tests -v`, `bash -n build-all.sh`, and `bash build-all.sh --validate`.
- Inspect the diff to confirm the HTTP allowlist, caller success conditions, registry challenge/absence branches, exception classes, Bash mutation sequence, and existing credential/TLS protections are unchanged except for diagnostic wording.
- Run `git diff --check` and record passed, failed, or unavailable checks. Tests use synthetic fixtures only; do not read production credentials, install tools, call production APIs, build real images, push source/tags/images, create releases, or associate packages as verification.

## Acceptance Criteria

- The user's reported generic `Unexpected HTTP status` failure includes its validated numeric HTTP status when reproduced with a fake response, for example `Unexpected HTTP status: 403`.
- Caller-level status failures also preserve their actual code, including transport-allowed statuses rejected by a specific API contract. Normal registry `401` challenge and confirmed `404` absence behavior is unchanged.
- Malformed response/status data, transport failures, and resource refusals remain sanitized and do not falsely claim a valid server status. Diagnostic output exposes no credentials, sensitive bodies, headers, payloads, raw command output, or request URLs.
- Status refusals remain refusals, not retry permission. Startup HTTP-error regressions produce zero publication effects, and existing release/retry guards continue to pass.
- Version, configured notes path, release notes, README, and release guide are consistent. Offline verification passes; no real publication is performed.

## Risks And Decisions

- Adding only the low-level allowlist code would leave `401`/`404` caller errors opaque. Update the existing status-check sites together without broadening accepted responses.
- HTTP status codes are safe diagnostic metadata only after strict parsing. Do not use raw response data or request URLs to make messages more informative.
- A `403` does not identify the missing scope or failing endpoint by itself. Endpoint diagnostics, actual permission repair, and repeated ERR-trap cleanup remain outside this request.
- Release scripts are part of the existing release identity. A diagnostic edit changes their hash; preserve current identity/refusal rules and use a fresh version rather than rewriting or repairing earlier remote releases.
