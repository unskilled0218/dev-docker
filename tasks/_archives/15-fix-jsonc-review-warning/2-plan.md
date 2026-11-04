- [Scope](#scope)
- [Implementation](#implementation)
- [Verification](#verification)
- [Acceptance criteria](#acceptance-criteria)

## Scope

Fix the JSONC refusal warning in task 14's code review. Preserve existing Penpot settings, token handling, config merging, and atomic writes. Do not change live configuration or real credentials.

## Implementation

1. In `scripts/configure-penpot.py`, replace repeated combined cleanup with separate, string-aware comment removal and one trailing-comma cleanup pass. Only remove a trailing comma after a value, never after an opening bracket, colon, or another comma. Keep `json.loads` and duplicate-key checks as the final validation before any file mutation. Add no dependencies or general parser framework.
2. Extend `tests/test_penpot_mcp.py` with malformed object and array cases: double commas, repeated commas separated by comments/whitespace, comma-only containers, and missing values. Assert refusal, byte-for-byte preservation, no new config file, and no temporary-file leftovers.
3. Retain valid JSONC coverage: line/block comments, comments between trailing commas and closing brackets, nested objects/arrays, escaped quotes, and strings containing comment markers or comma/bracket text. Keep existing JSON, preservation, idempotence, conflict, symlink, and runtime-substitution tests.
4. Add a CLI malformed-JSONC case proving nonzero exit, sanitized errors, and unchanged original bytes without exposing synthetic private values.
5. Update the relevant README note and `docs/penpot-mcp.md` to clarify malformed-input refusal. During implementation, bump the current patch version, add release notes, update `scripts/release.json`'s notes path, and record results in this task's `4-implemented.md`. Do not rewrite task 14's review or historical records.

## Verification

- First reproduce task 14's two examples as failing regression tests, then verify they pass after the fix.
- Run `python3 -B -m unittest discover -s tests -p test_penpot_mcp.py`, `python3 -B -m unittest discover -s tests`, `bash build-all.sh --validate`, and `git diff --check`.
- Report the known baseline missing-manual-Dockerfile test failure separately. Use isolated temporary directories and synthetic data; no Penpot requests, real-token reads, image publication, or host permission changes are needed.

## Acceptance criteria

- Malformed JSONC is rejected before writing; original bytes and config-directory contents remain unchanged.
- Valid comments and trailing commas still work, with strings and unrelated settings preserved.
- CLI errors remain sanitized, regression tests cover both reviewed examples and nearby malformed cases, and docs/release metadata match the fix.
