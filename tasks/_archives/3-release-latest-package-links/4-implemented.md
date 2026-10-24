# implemented

- [Changes](#changes)
- [Verification](#verification)
- [Contract characterization](#contract-characterization)
- [Limits and operational requirements](#limits-and-operational-requirements)

## Changes

- Created branch `3-release-latest-package-links` from the committed plan without reusing an existing branch.
- Reduced the shared build/release graph to `base` → `npm`. Both modes obtain image names from validated helper settings rather than a separate Bash graph. Release tags retain both `v<VERSION>` and `latest`.
- Removed Android, Tauri, and Switchboard from automated builds, validation prerequisites, snapshots, release inventory, staging, digest/predecessor identity, promotions, and package links. Retained their Dockerfiles; updated parent defaults and the base Compose reference to the renamed images. Manual Android builds should use tag `android:latest` for retained child defaults.
- Added explicit package authority, bounded version-list evidence, link, and confirmation helpers using the existing HTTPS boundary. Publication verifies the authenticated individual namespace owner, exact repository identity, enabled Packages unit, owner repository permissions, and the supported server contract before publication writes.
- Package reads require successful authorized exact-name listings and terminal empty pages, with strict version/owner/type/association validation. Null repository evidence requires verified owner visibility; failed or hidden reads never prove absence. Links apply only to verified unlinked packages; correct links are skipped and foreign/unknown links are refused.
- Added a pre-tag association phase, confirmed/attempted link diagnostics, lost-response reconciliation limited to attempted POSTs, and association checks through final completion. Fresh retries reuse verified staging and existing correct links; completed retries remain read-only and refuse missing associations rather than repairing them.
- Updated README, release documentation, and offline fake-port regressions. Advanced `VERSION` to `0.1.2`, added matching release notes, and updated the configured notes path. Historical releases/tasks and existing remote records remain untouched.

## Verification

- Final full suite: `python3 -B -m unittest discover -s tests -v` passed all 61 tests in 411.701 seconds. This includes all 39 existing regressions and 22 package-specific tests, including oversized response refusal and nonterminal pagination bounds.
- Initial regression run: `python3 -B -m unittest discover -s tests -v` passed all 39 existing tests after adapting them to the two-image graph.
- Initial focused package run: `python3 -B -m unittest discover -s tests -p test_package_release.py -v` passed all 19 tests present at that point, including both server contracts, package linking/retries, hidden/foreign association refusals, and excluded-image noninterference.
- Focused evidence checks: `PYTHONPATH=tests python3 -B -m unittest test_package_release.PackageEvidenceTests -v` passed all 8 tests, including strict identity/status fields, multi-version pagination, malformed/ambiguous evidence, missing completed links, and refusal before a POST when prerequisite reads fail.
- `bash -n build-all.sh` passed. `bash build-all.sh --validate` passed without credentials or external operations.
- Python AST parsing passed for all five script/test Python files. `git diff --check` and staged whitespace checks passed. Table-of-contents validation covered all 19 section headings in the four updated/new documentation files.

## Contract characterization

- A bounded, unauthenticated, verified-HTTPS read of `https://git.lan/api/v1/version` returned `{"version":"28.2.0"}`. No token was read for that probe and no deployed-server mutation was made.
- Added exact support for `28.2.0` after inspecting its upstream tagged schema, package routes/listing, access middleware, package conversion, owner repository permissions, and link service. This extends the plan's initial `1.24.7` reference through the additional characterization it required, not a broad newer-version assumption.
- Both contracts return package version IDs, filter repository visibility by permissions, grant the individual owner complete same-namespace repository visibility, enforce matching package/repository owners, and refuse already-linked packages. Version `28.2.0` exposes User `type`, which must be `User`; `1.24.7` has no such field. Fixtures model these differences and actual versus permission-filtered associations.
- Exact source references are documented in `docs/image-releases.md`. Runtime support is limited to these two characterized version strings; custom, development, and unknown versions fail closed.

## Limits and operational requirements

- All build/publish regression execution uses test-owned repositories and fake command/HTTP boundaries. No real image build, registry login/push, Git-tag push, release creation, package link, or UI visibility check was performed. No tools or host dependencies were installed.
- The public version response does not certify the deployed binary, token scopes, owner access, native Buildx behavior, image toolchains, or successful publication. Live visibility of `base` and `npm` at `https://git.lan/dev/dev-docker/packages` remains unverified until separately authorized publication and inspection.
- Publication still requires clean pushed `main`, AMD64 readiness, trusted HTTPS, verified owner credentials with user/repository/package scopes, enabled repository Packages, and single-operator exclusion across Git, registry, and associations. No organization/delegate workflow, forced reassignment, unlink, cleanup, rollback, or cross-service atomicity guarantee was added.
