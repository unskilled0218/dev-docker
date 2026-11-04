- [Changes](#changes)
- [Verification](#verification)
- [Limits](#limits)

## Changes

- Created new branch `15-fix-jsonc-review-warning` from task 14's branch at `7b362a2`.
- Replaced repeated combined JSONC cleanup with separate string-aware comment removal and one guarded trailing-comma pass in `scripts/configure-penpot.py`. Commas following another comma, opening bracket, or colon are not removed. Final JSON parsing and duplicate-key validation still precede all mutation.
- Added regressions for both reviewed double-comma examples, comment/whitespace-separated commas, comma-only containers, missing values, duplicate keys, and unterminated strings. Refusal checks preserve original CRLF bytes and directory contents.
- Added valid JSONC compatibility cases covering nested containers, scalar values, commented trailing commas, escaped quotes/backslashes, and comment/comma text inside strings. Added CLI coverage for sanitized malformed-JSONC refusal without overwriting private synthetic input.
- Preserved token handling, unrelated settings, config merging, and atomic replacement. Added no dependencies and changed no live configuration or real credentials.
- Updated the relevant README note and `docs/penpot-mcp.md`. Bumped version `0.1.22` → `0.1.23`, added release notes, and updated `scripts/release.json`'s notes path. Task 14's review and historical records remain unchanged.

## Verification

- Before the fix, `python3 -B -m unittest discover -s tests -p test_penpot_mcp.py -k malformed_jsonc` ran two regression methods and reported 10 failures across the CLI case and malformed-input subtests. Both reviewed examples were reproduced as failures.
- After the fix, `python3 -B -m unittest discover -s tests -p test_penpot_mcp.py -v`: all 12 tests passed in 2.147 seconds. A final focused rerun also passed all 12 tests in 2.409 seconds.
- `bash build-all.sh --validate`: passed without credentials or external operations.
- `git diff --check`: passed.
- An additional in-memory matrix rejected all 25 malformed comma/comment combinations across objects, arrays, comma-only containers, and missing values, including CRLF and both comment styles.
- `python3 -B -m unittest discover -s tests`: 148 tests ran in 545.775 seconds; 147 passed and one failed. The sole failure, `test_excluded_images_remain_manual_and_do_not_block_either_mode`, expects manual-image Dockerfiles absent from the repository. This is the same baseline failure reproduced against `main` during task 14; this fix changes neither those files nor that test.

## Limits

- Verification used temporary directories and synthetic data. The inherited runtime-substitution check uses an isolated OpenCode config-loading seam, not live Penpot access.
- No real image build or publication is needed for this parsing-only fix. Existing real-image and authenticated-plugin verification limits from task 14 remain unchanged; this task does not claim to resolve them.
- No real tokens, host permissions, live services, or external repositories were changed.
