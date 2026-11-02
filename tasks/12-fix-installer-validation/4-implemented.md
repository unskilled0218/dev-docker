# Implementation

- [Implementation](#implementation)
  - [Changes](#changes)
  - [Verification](#verification)
  - [Limits](#limits)

## Changes

- Created branch `12-fix-installer-validation` from `60829be`.
- Added the existing regular() check for scripts/install-docker.sh to settings() in scripts/release_data.py. Missing or symlinked installer paths now fail before external operations in all modes.
- Added two fixture-based regression tests covering six refusal scenarios across validation, local build, and publication. Checks use missing fixture credentials and certificates and assert source-specific errors, no external calls or mutation effects, no locks or run-owned temporary directories, and unchanged file inventories.
- Preserved snapshot source selection and left installer execution, Dockerfiles, and historical release metadata unchanged.
- Updated README.md and docs/image-releases.md. Bumped VERSION to `0.1.20`, updated the configured notes path, and added docs/releases/0.1.20.md.

## Verification

- `PYTHONPATH=tests python3 -B -m unittest test_build_all.LocalContractTests.test_missing_installer_refuses_all_modes_before_external_operations test_build_all.LocalContractTests.test_symlinked_installer_refuses_all_modes_before_external_operations test_build_all.LocalContractTests.test_validation_has_no_external_or_filesystem_effects test_build_all.DataBoundaryTests.test_installer_snapshot_uses_worktree_locally_and_selected_commit_for_publication -v`: passed, 4 tests in 0.525 seconds. Covers all six invalid-input mode combinations, valid offline validation, and local versus selected-commit installer bytes.
- `bash build-all.sh --validate`: passed without credentials or external operations.
- `git diff --check`: passed.
- `python3 -B -m unittest discover -s tests -p 'test_*.py'`: completed 131 tests in 548.465 seconds without a harness timeout; 130 passed and one failed. The only failure is the confirmed baseline test_excluded_images_remain_manual_and_do_not_block_either_mode at tests/test_package_release.py:236, which expects the already-deleted Dockerfile/switchboard.Dockerfile. No new test failures were observed; the full suite is not green.

## Limits

No native image build or publication was attempted for this local validation fix. Verification used fixture-owned credentials and certificates only; real credential files and CA permissions were not accessed or changed. The previous suite had a confirmed baseline failure in test_excluded_images_remain_manual_and_do_not_block_either_mode because Dockerfile/switchboard.Dockerfile had already been deleted. That unrelated test and file remain unchanged.
