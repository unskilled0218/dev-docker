# plan

- [plan](#plan)
  - [Scope](#scope)
  - [Implementation Plan](#implementation-plan)
    - [1. Validate the required installer early](#1-validate-the-required-installer-early)
    - [2. Add isolated regression coverage](#2-add-isolated-regression-coverage)
    - [3. Update documentation and release metadata](#3-update-documentation-and-release-metadata)
    - [4. Verify and record results](#4-verify-and-record-results)
  - [Acceptance Criteria](#acceptance-criteria)
  - [Risks And Decisions](#risks-and-decisions)

## Scope

Fix the required-installer validation warning in tasks/11-use-local-docker-installer/5-code-review.md. Reject missing or symlinked scripts/install-docker.sh during offline settings validation, before credentials, Docker, network operations, or build preparation. Leave installer execution and publication source selection unchanged.

## Implementation Plan

### 1. Validate the required installer early

- Add `regular(root, "scripts/install-docker.sh")` to settings() in scripts/release_data.py alongside existing source checks.
- Reuse regular() and its current refusal messages for missing files, symlinks, path escapes, and non-file inputs. Do not add a parallel path validator or general build-input framework.
- Keep validation local and read-only. build-all.sh already calls settings before tool checks, locks, temporary directories, certificates, credentials, or external commands; no shell sequencing change is needed.
- Leave snapshot() unchanged: local builds read working-tree bytes, and published builds read the selected Git commit blob. Do not add installer content to the release-tool script hash or require a clean checkout for offline validation.

### 2. Add isolated regression coverage

- Extend LocalContractTests in tests/test_build_all.py using temporary ReleaseFixture repositories, never removing or replacing project files.
- Add missing-installer and symlinked-installer cases. For the symlink case, use an existing regular target inside the fixture repository so rejection proves the symlink rule rather than only a path-escape or missing-target rule.
- Exercise `--validate`, `--build-only`, and the default publication invocation for each invalid input. Assert nonzero exit, the appropriate source refusal, no fake external calls, no mutation effects, and no run-owned temporary directories.
- Remove fixture token and certificate inputs before these checks to prove source rejection happens independently and before credential or certificate loading. Compare fixture file inventories before and after invocation to detect unintended filesystem effects.
- Keep the existing valid-checkout validation test passing without token or certificates. Retain the existing local-versus-selected-commit installer snapshot test to protect publication sourcing.

### 3. Update documentation and release metadata

- Briefly state in README.md and docs/image-releases.md that validation requires a regular, non-symlinked local installer and refuses invalid sources before external operations.
- During implementation, bump VERSION from 0.1.19 to 0.1.20, update scripts/release.json to docs/releases/0.1.20.md, and add matching release notes with a table of contents.
- Do not change Dockerfiles, installation behavior, certificate permissions, excluded-image policy, or historical release records.

### 4. Verify and record results

- Run the new invalid-installer cases, LocalContractTests.test_validation_has_no_external_or_filesystem_effects, and DataBoundaryTests.test_installer_snapshot_uses_worktree_locally_and_selected_commit_for_publication through `PYTHONPATH=tests python3 -B -m unittest` with their exact test names.
- Run `bash build-all.sh --validate` against the intact checkout and `git diff --check`.
- Run `python3 -B -m unittest discover -s tests -p 'test_*.py'` with a harness timeout of at least 15 minutes, or no harness timeout. The previous full run took about nine minutes.
- Record actual commands, test counts, failures, and limits in 4-implemented.md. Do not report the suite as green if the known baseline failure persists.
- No native image build or publication is needed for this local validation change. Do not install tools, read real credentials, or bypass unreadable CA inputs for verification.

## Acceptance Criteria

- Missing or symlinked installer paths cause offline validation to fail with an existing source-path refusal.
- Both build modes reject the same invalid inputs before external calls, credentials, certificate loading, locks, or run-owned temporary files.
- An intact checkout still validates without credentials, certificates, Docker, or network access.
- Local and published snapshots retain their existing installer source selection.
- Focused tests and configuration checks pass; full-suite results distinguish baseline failures from regressions.
- README, release documentation, VERSION, configured notes path, and release-note heading agree with the fix.

## Risks And Decisions

- The existing regular() check establishes file type and path safety, not executable permissions or Bash correctness. The installer is invoked through Bash; do not introduce new permission or content policies.
- Publication already checks the working-tree source path through blob() before reading committed bytes. Moving the same path check earlier does not change its source contract.
- Changing release_data.py changes the existing release-tool hash automatically. Use the new patch version rather than rewriting previous release identity records.
- The prior suite had one confirmed baseline failure: tests/test_package_release.py expects the already-deleted Dockerfile/switchboard.Dockerfile. Report it separately; do not restore the file or change that unrelated test in this task.
