# implemented

- [Changes](#changes)
- [Verification](#verification)
- [Limits](#limits)

## Changes

- Created branch `4-show-http-error-status` without reusing an existing branch.
- Added parsed numeric HTTP codes to the existing transport allowlist refusal and caller-level package/repository reads, package-link acceptance, release/tag inventory reads, release creation, registry-token acceptance, and registry evidence checks. A rejected `403` now reports `Unexpected HTTP status: 403`; a caller rejecting `404` includes `HTTP 404` with its existing contextual guidance.
- Preserved the accepted transport statuses, caller success conditions, normal registry challenge/absence flow, exception classes, source/identity guards, resource limits, TLS/authentication protections, and Bash mutation/reconciliation sequence. No raw request/response metadata is added to diagnostics.
- Added 11 focused HTTP diagnostic tests using the real parser and mocked bounded capture. Extended existing fake startup error cases to assert numeric codes, secret non-disclosure, and zero publication effects.
- Updated README and the release guide with diagnostic examples and limits. Advanced `VERSION` from `0.1.2` to `0.1.3`, added matching release notes, and updated the configured notes path without changing historical releases.

## Verification

- `python3 -B -m unittest discover -s tests -p test_http_diagnostics.py -v`: all 11 tests passed in 0.009 seconds. Coverage includes rejected and transport-allowed codes, malformed status output, transport/resource failure precedence, caller-level refusals, privacy markers, unchanged registry challenge/absence behavior, and successful-status content errors.
- `PYTHONPATH=tests python3 -B -m unittest test_package_release.PackagePublicationTests.test_package_http_errors_and_unsupported_versions_refuse_without_writes -v`: passed in 12.108 seconds. Fake `401`, `403`, `404`, `302`, and `500` startup failures report the code and record zero publication effects; synthetic body/credential markers remain absent from CLI output.
- `bash -n build-all.sh`, `bash build-all.sh --validate`, and `git diff --check`: passed.
- AST comparison against `main` confirmed both production Python modules are unchanged except for `require` refusal-message arguments. All six Python files parsed successfully; the suite contains 72 test methods.
- Table-of-contents validation covered all 19 section headings in the four updated/new documentation files. Staged whitespace checks passed; `build-all.sh` and the fake command-port implementation are unchanged.
- `python3 -B -m unittest discover -s tests -v`: all 72 tests passed in 396.526 seconds, including the existing release/retry safeguards and the new diagnostic/privacy checks.

## Limits

- No production credentials were read, no production API was contacted, and no real image build, login/push, source/tag push, release creation, package association, installation, or server configuration change was performed. All HTTP responses used for verification are synthetic.
- The underlying server error and failing endpoint remain unidentified. This change exposes the status but does not fix permissions or authorize retry/repair. Duplicate Bash ERR-trap output remains unchanged, as planned.
