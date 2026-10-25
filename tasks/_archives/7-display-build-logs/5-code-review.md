# Brooks-Lint Health Dashboard

- [Brooks-Lint Health Dashboard](#brooks-lint-health-dashboard)
  - [Dimension Scores](#dimension-scores)
  - [Module Dependency Graph](#module-dependency-graph)
  - [Test Suite Map](#test-suite-map)
  - [Top Findings](#top-findings)
    - [Warning](#warning)
  - [Verification And Limits](#verification-and-limits)
  - [Recommendation](#recommendation)

**Mode:** Health Dashboard

**Scope:** All 12 changed files on `7-display-build-logs`, comparing local base `main` (`a4bd8f7`) with implementation `d57b648`. Includes shell progress, process observation, log filtering/delivery, policy integration, release settings/version, README/docs, fixtures, tests, and implementation results. Planning documents already exist on the base branch and are review context.

**Composite Score:** 99/100

**Trend:** Previous Health Dashboard score: 98; current score: 99 (+1). The earlier entry assessed the plan, not this implementation, so the scores do not measure an implementation improvement.

**Verdict:** Changes requested before merge. One reproduced Warning finding affects the documented log privacy contract; the numerical score does not override that requirement.

## Dimension Scores

- Code Quality: 95/100. Explicit observer activation and stderr-only presentation preserve normal command behavior, but the filter's transformation order lets one protection disable another (finding 1).
- Architecture: 100/100. Release policy prepares sensitive values, the generic runner supervises child processes, and the logging component owns filtering and bounded delivery. The supervised writer addresses the plan's backpressure finding without importing release policy into the runner or introducing an import cycle.
- Tech Debt: 100/100. The added protocol serves a concrete deadline/cleanup requirement rather than speculative extensibility. The logging module participates in script identity, both modes retain capture budgets, and API/login/promotion output remains private. Coordinated edits across the feature are not unrelated change propagation.
- Test Quality: 100/100. The suite exercises live delivery with handshakes, chunk splits, decoded foreign passwords, actual undrained sinks, writer failure, signals, cleanup, and workflow outcomes. The collision regression missing from existing tests belongs to finding 1 rather than a duplicate scored finding.

Balanced scoring deducts five points once in Code Quality: `95 × 0.25 + 100 × 0.30 + 100 × 0.25 + 100 × 0.20 = 98.75`, rounded half-up to 99.

## Module Dependency Graph

```mermaid
graph TD
  Shell[build-all.sh] --> Policy[scripts/release_data.py]
  Policy --> Config[scripts/release.json and effective Docker config]
  Policy --> IO[scripts/release_io.py]
  Policy --> Logs[scripts/release_logs.py]
  Logs --> IO
  IO -. Explicit observer calls .-> Logs
  Logs --> Writer[Owned writer process]
  Writer --> Sink[Caller stderr]
  IO --> Docker[Owned Docker process group]
  Tests[Offline logging tests] --> Policy
  Tests --> Logs
  Tests --> Fake[tests/fake_release_ports.py]
```

Solid module arrows show imports/calls or owned resources; the dotted observer arrow is runtime dependency injection, not an import cycle. Only sanitized framed records cross into the writer. Acknowledgments follow sink writes, while the runner checks deadlines independently of blocking sink I/O.

## Test Suite Map

- Isolated filter/policy/transport tests: 52 methods, comprising six new `FilterTests` plus 46 existing data-boundary, HTTP-diagnostic, and package-evidence tests.
- Real subprocess streaming tests: 12 new methods covering process I/O, delivery, limits, failure, and cleanup without Docker or network services.
- Fake-boundary workflow integration tests: 56 methods, comprising eight new build-log integration tests plus 48 existing local/publication/package integration tests.
- Total: 120 test methods. Native Docker/registry end-to-end tests: none in the inspected suite. Counts exclude parameterized subcases, and no line-coverage percentage is inferred.

## Top Findings

### Warning

**1. R2 Change Propagation — Known-value replacement disables structured secret detection (Code Quality)**

Symptom: `scripts/release_logs.py:79-85` replaces configured sensitive strings before checking authorization/credential syntax and matching URLs. A valid sensitive value that overlaps a structural marker changes that marker before its protective rule runs. `credential_values()` accepts arbitrary control-free string usernames/passwords, so values such as `Authorization`, `token`, or `https` can legitimately enter this set. Existing structured-secret tests (`tests/test_build_logs.py:49-57`) use an empty known-value set and do not exercise this interaction.

Source: The Pragmatic Programmer — Orthogonality; Code Complete — defensive programming and error-handling discipline.

Consequence: The filter can display an otherwise recognizable authorization value or URL password/signature that its documented policy promises to suppress. This is not the acknowledged limitation for custom encodings or unrecognizable unknown secrets: the original records use the exact supported header and URL syntax, and the filter itself destroys that syntax. Reproduced with synthetic values only:

```text
Known value: Authorization
Input: Authorization: Bearer synthetic-unlisted-bearer
Displayed: [redacted]: Bearer synthetic-unlisted-bearer

Known value: https
Input: fetch https://user:synthetic-unlisted-password@host/file?signature=synthetic-signed-value failed
Displayed: fetch [redacted]://user:synthetic-unlisted-password@host/file?signature=synthetic-signed-value failed
```

Remedy: Make structural classification independent of known-value mutation. Detect protected authorization/assignment records and URL spans on the control-normalized original text, then suppress or mask those original spans before applying literal replacements to remaining display text. Preserve useful surrounding error context and the existing decoded-password, record-size, and chunk-boundary behavior. Add combined-policy regressions using supported Docker credential values that overlap header names, assignment keys, and URL schemes; cover both streams and read splits, and assert the unlisted header/URL secrets never reach the display sink. Do not resolve this by weakening the documented structural protections.

## Verification And Limits

- Review rerun: all 26 logging tests passed in 56.299 seconds. Their passing result does not cover the independently reproduced transformation-order case above.
- Review reproduction called the real `RecordFilter.record()` with synthetic known values and synthetic header/URL secrets. Both outputs retained the corresponding synthetic secret markers. No production credentials, remote endpoints, or service calls were used.
- `bash -n build-all.sh`, `bash build-all.sh --validate`, and `git diff main...HEAD --check` passed.
- The complete 120-test run passed in 567.720 seconds during implementation, as recorded in `4-implemented.md` and the implementation session. The complete suite was not rerun during this review.
- The two plan-review gaps are addressed: writer delivery is bounded and independently supervised, and Docker Base64 auth extraction includes decoded passwords with separate credentials in tests. The remaining issue is the interaction between literal and structural filtering, not those original gaps.
- Version `0.1.7`, the configured notes path, and the release heading agree. Source hashing includes the new logging module. No `.brooks-lint.yaml` exists; default risks and balanced scoring apply.
- The abbreviated scans considered R1–R6 and test clarity/brittleness, with privacy and process-lifecycle checks grounded in the changed behavior. No implementation code or tests were edited. No native builds, registry login, host trust changes, TLS bypass, or remote publication occurred.

## Recommendation

Fix finding 1 and add its combined-policy regression tests before merging. Re-run focused logging tests and the full offline suite after changing the filter, preserving captured stdout, output budgets, writer cleanup, and release guards. Broader refactoring is unnecessary; offline approval still cannot certify arbitrary build scripts or native Buildx privacy.
