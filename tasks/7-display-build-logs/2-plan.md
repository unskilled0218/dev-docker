- [Scope](#scope)
- [Implementation plan](#implementation-plan)
  - [Summary](#summary)
  - [1. Add a bounded live-output path](#1-add-a-bounded-live-output-path)
  - [2. Sanitize build logs before displaying them](#2-sanitize-build-logs-before-displaying-them)
  - [3. Connect logs and phase progress to the release workflow](#3-connect-logs-and-phase-progress-to-the-release-workflow)
  - [4. Verify behavior and update documentation](#4-verify-behavior-and-update-documentation)
- [Acceptance criteria](#acceptance-criteria)
- [Risks and decisions](#risks-and-decisions)

## Scope

Display useful live Docker build output and safe workflow progress during both `bash build-all.sh --build-only` and publication. Show build failure details without printing known credentials or sensitive configuration. Preserve existing evidence parsing, output/time limits, signal cleanup, release guards, and mutation authority. Do not change Dockerfiles, image dependencies, host trust, TLS verification, or remote release state in this task.

## Implementation plan

### Summary

`scripts/release_io.py:capture()` drains stdout and stderr concurrently but retains them privately. `command()` returns stdout and replaces nonzero exits with a generic tool-name error. The build dispatcher discards successful Docker stdout, so users cannot see build steps or the failing instruction. Extend the existing capture loop with an explicit display hook for Docker builds only; do not globally echo subprocess output.

### 1. Add a bounded live-output path

- Add an optional output observer to `capture()` in `scripts/release_io.py`, and an explicit opt-in path through `command()`. Leave existing callers and return values unchanged when no observer is supplied.
- Continue draining both pipes with selectors. Apply byte limits before handing accepted chunks to the observer; do not replay buffers on failure or expose the overflowing chunk. Retain the existing stdout/stderr budgets and build timeout rather than silently removing safety limits for verbose builds.
- Keep observer state separate for stdout and stderr. Buffer complete records before display so secrets split across reads cannot leak; support newline and carriage-return progress records, split UTF-8 sequences, and an unterminated final record.
- Bound each pending record at 64 KiB. Suppress an overlong record through its next delimiter and display a fixed omission notice, rather than printing an unsanitized prefix or growing memory without bound. Preserve normal process byte accounting even for suppressed records.
- Write displayed records to the parent's stderr and flush immediately. Child stdout remains captured for machine consumers; do not combine displayed output with helper return values.
- Preserve timeout and interruption handling, process-group termination, pipe cleanup, and `CommandFailed` for an ordinary nonzero child exit. A log-policy or output-sink failure must stop safely as a refusal, not become permission for lost-write reconciliation. Never fall back to raw output.

### 2. Sanitize build logs before displaying them

- Keep the display filter in a small focused component, such as `scripts/release_logs.py`, with no service calls or mutation logic. Pass it explicitly prepared sensitive values; do not let the generic process runner discover credentials or Docker configuration.
- In `release_data.py`, prepare the filter before launching a build from the private token/login files and the effective Docker configuration. Cover publication's private Docker config and build-only's original config. Use bounded reads and existing proxy validation; never modify the caller's config. Missing Docker config is valid; malformed or unreadable redaction inputs must stop before the build instead of enabling unfiltered logs.
- Redact the exact token, the current login/token Basic-auth encoding, Docker `auths` credential values, nonempty configured proxy values and their credential components, and run-owned private paths. Include relevant configured/overridden credential-file paths. Handle supported URL-encoded representations of known credential components explicitly; ignore empty redaction values and replace longer matches first.
- Strip terminal escape/control sequences before matching and display, preserving printable text. Suppress complete records containing authorization headers or recognizable credential assignments; replace URLs in remaining build output with a fixed URL placeholder so user information, query strings, and signed download tokens are not relayed.
- Test and document the exact redaction contract. Do not claim to detect arbitrary secrets, custom encodings, or credentials invented by downloaded setup scripts. Known-value and structured-record filtering must run on every displayed record before any bytes reach the terminal.
- Keep raw command arguments, environment dumps, Docker config documents, HTTP headers/bodies, login output, and Git/curl stderr private. Do not add shell tracing, a raw-log switch, or retained raw log files.

### 3. Connect logs and phase progress to the release workflow

- Add `--progress=plain` to actual `docker buildx build` arguments in `build_args()` for deterministic readable step output in both modes. Do not pass that flag to `buildx imagetools create` or unrelated Docker commands.
- In the `build` dispatcher, enable the observer only when arguments identify `docker buildx build`; promotion currently shares this dispatcher and must retain its private command behavior. Keep publication's prewrite guard before Docker execution and preserve its existing timeout.
- Display sanitized Docker records as they arrive on success and failure. On a nonzero exit, retain the generic failure summary after the useful preceding step/error records, without duplicating captured output.
- Add concise stderr phase messages in `build-all.sh` before preflight, startup inventory, snapshot preparation, image preparation/build/reuse/verification, login, package association, tag publication, alias promotion, release creation, and final verification. Only interpolate validated image names, version identifiers, and fixed mode/phase labels; do not print command lines, credentials, arbitrary endpoints, or captured helper responses.
- Keep assignments such as `classification=$(...)`, `action=$(...)`, and `oid=$(...)` free of progress output on stdout. Keep existing stdout success summaries and CLI behavior compatible. Validation and help must remain offline and free of build activity.
- Do not redesign repeated Bash failure traps in this task. Phase messages are observational and cannot authorize retries, rollback, or repair.

### 4. Verify behavior and update documentation

- Add focused tests in `tests/test_build_logs.py` for the filter and real subprocess streaming boundary, using synthetic values and temporary files under `/tmp/opencode`.
- Prove live delivery before child completion with a synchronization handshake rather than a sleep-only timing assertion. Exercise concurrent stdout/stderr, normal and failed exits, final partial records, chunk-split credentials, UTF-8 and terminal controls, carriage returns, overlong records, output bounds, timeouts, interruptions, and a failed display sink. Verify process cleanup and unchanged captured stdout.
- Cover exact token, Basic-auth, Docker auth, proxy values/components, credential paths, URL user information/query strings, and authorization/credential records across read boundaries. Assert both useful surviving text and absence of sensitive markers in displayed output and errors. Verify unknown-secret limitations through documentation rather than asserting impossible universal detection.
- Extend `tests/fake_release_ports.py` with synthetic build progress and failure records, including configurable sensitive markers. Emit failure details before the fake exits; assert `--progress=plain` only on builds.
- Extend command-level tests for local build success, publication success, build failure, staging reuse, completed read-only retry, phase ordering, and no unauthorized writes. Prove logs do not corrupt machine-readable helper results or final summaries. Keep token/proxy isolation, credential-free validation, cleanup, and existing HTTP diagnostic tests passing.
- Add the new production logging module to the committed script hash in `settings()` and update fixture source copying as needed. Its behavior affects the release script contract; do not let it vary outside release identity.
- Update `README.md` briefly and add a dedicated build-log section with table-of-contents entry in `docs/image-releases.md`. Explain stderr, default plain build progress, redaction/omission behavior, existing size/time limits, and the limitations of displaying untrusted build-tool output. Narrow the current blanket statement that no command stderr is relayed to distinguish filtered Docker build logs from still-private API and other command output. Reconcile the proxy documentation with the precise filtering guarantee.
- During implementation, bump the current project patch version, add matching release notes, and update the configured notes path according to the existing release convention. Do not rewrite historical notes or release objects.
- Run `python3 -B -m unittest discover -s tests -v` with a sufficient harness timeout, `bash -n build-all.sh`, `bash build-all.sh --validate`, and `git diff --check`. No native build, login, service probe, push, or publication is part of verification.

## Acceptance criteria

- Both build modes display readable, sanitized Docker step and failure output before the child process exits, rather than only `Command failed: docker`.
- Safe phase messages show workflow progress, including reused images and completed read-only retries, without polluting helper stdout or changing release decisions.
- Known credentials, configured sensitive proxy values, credential paths, and structured authorization/URL secrets covered by the documented policy do not appear in displayed logs, including when split across chunks.
- No raw-output fallback, generic stderr echo, shell tracing, retained raw log file, or authenticated API payload logging is introduced. Unknown or transformed secrets remain an explicit limitation, not a claimed guarantee.
- Existing capture defaults, byte/time bounds, exception semantics, process cleanup, private contexts, caller configuration, and publication guards remain intact; observer failures do not grant reconciliation authority.
- Focused and full offline tests pass, with no Docker installation, real credentials, or network dependency. README, detailed docs, version, and release notes match implemented behavior.

## Risks and decisions

- Build output is untrusted: Dockerfiles and downloaded scripts can print arbitrary data. A small filter can protect defined known values and recognizable records, not provide universal secret detection. Operators must not echo secrets in build steps and must treat terminal logs as potentially sensitive before sharing them.
- Buffering complete records prevents chunk-boundary leakage but delays newline-free output until a delimiter or EOF. Overlong records are omitted; output-budget exhaustion still stops the operation. Document these tradeoffs rather than exposing a raw prefix or weakening bounds.
- The filter must not parse live output as release evidence or alter captured stdout. Separate display from capture and keep HTTP/Git/login output private; release permissions remain based on verified state only.
- Build-only currently does not inspect proxy configuration for logging. Preparing safe redaction adds a bounded read of the effective Docker config; invalid inputs must fail before builds and be documented, without copying or changing the caller's configuration.
- Logging code changes release-script identity. A previously completed release remains read-only only with its exact matching identity; do not adopt old staging evidence or rewrite tags to make retries pass.
