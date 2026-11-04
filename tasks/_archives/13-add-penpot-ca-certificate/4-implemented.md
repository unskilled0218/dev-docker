- [Changes](#changes)
- [Verification](#verification)
- [Limitations](#limitations)

## Changes

- Implemented on new branch `13-add-penpot-ca-certificate`.
- Added `penpot_certificate_file`, defaulting to `/usr/local/share/ca-certificates/penpot.lanCA.crt`, and `BUILD_PENPOT_CERT_FILE` with existing override and validation rules.
- Extended the shared certificate registry so both build modes capture Penpot bytes, include them in private contexts and fingerprints, and recheck them in publication guards.
- Added the Penpot certificate copy before `update-ca-certificates` in the base Dockerfile; npm inherits base trust.
- Extended fixtures, fake build context assertions, overrides, relative paths, home expansion, invalid input cases, sanitized permission failures, captured snapshots, fingerprint swaps, guards, and copy-order tests.
- Updated README and trust documentation. Bumped version from `0.1.20` to `0.1.21`, added release notes, and updated the configured notes path.

## Verification

- `python3 -B -m unittest discover -s tests`: 132 tests ran in 553.604 seconds; 131 passed, one failed. The failure is `test_excluded_images_remain_manual_and_do_not_block_either_mode`, which expects `android.Dockerfile`, `tauri.Dockerfile`, and `switchboard.Dockerfile`; the repository contains only base and npm Dockerfiles.
- Reproduced that same failure against an isolated `git archive main` checkout under `/tmp/opencode`. It predates this implementation and was left outside scope.
- `python3 -B -m unittest discover -s tests -p test_build_all.py -k DataBoundaryTests`: all 20 tests passed.
- `bash build-all.sh --validate`: passed without credential loading or external operations.
- `git diff --check`: passed before final commit.
- An initial full-suite attempt exceeded its 120-second command timeout. An earlier background run used a permission-error test double with an incorrect required argument; that test double was fixed before the final full-suite run reported above.
- `bash build-all.sh --build-only`: stopped during local preflight with `git.lanCA.crt is missing, unreadable, empty, or exceeds byte limit; set BUILD_CERT_FILE`. All three default certificate files exist, but the current user cannot read the Git or ntfy CA files. Penpot's CA file is readable. No override was set.

## Limitations

- No real image was built; installed-image certificate contents and HTTPS trust remain unverified. Existing-container access to Penpot is not proof of rebuilt-image trust.
- Supply readable valid Git and ntfy CA files through `BUILD_CERT_FILE` and `BUILD_NTFY_CERT_FILE`, or correct their permissions separately, before retrying a local build. No permissions or host trust were changed.
- No images were published, no remote release records were changed, and no certificates or credentials were downloaded or committed.
