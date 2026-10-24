# Implemented

- [Implemented](#implemented)
  - [Changes](#changes)
  - [Contract evidence](#contract-evidence)
  - [Verification](#verification)
  - [Limits](#limits)

## Changes

- Created branch `5-fix-first-publication` without reusing an existing branch.
- Added a narrow initial named-package HTTP 404 path in `scripts/release_data.py`. Existing supported-server, authenticated individual-owner, login, repository ownership, Packages-enabled, admin-permission, and captured-authority checks remain prerequisites.
- Require an independent filtered owner inventory to return successful HTTP 200 arrays through a terminal empty page before treating the missing package's non-internal versions as absent. Validate owner/type/name/version identities, case-normalized per-package version uniqueness, globally unique version IDs within the inventory, neighboring names, pagination, and existing shared resource budgets. Reject exact targets, including case variants, as contradictory evidence.
- Reuse bounded record validation for exact package inventories and owner searches. Keep ordinary `api_read` strict; do not change the transport allowlist, TLS/authentication boundary, mutation sequence, or rollback policy. A later-page exact 404 still stops immediately.
- Correct the fake external boundary for Gitea `1.24.7` missing-package `200 []` versus `28.2.0` middleware 404 behavior. Add filtered owner searches and stable namespace-wide version IDs.
- Extend first-publication, mixed existing/missing package, read-only retry, neighboring-package noninterference, inaccessible/contradictory/malformed evidence, shared-budget, and staged-package disappearance coverage. Existing internal-only conflicts, foreign associations, authority drift, and lost-response refusals remain covered.
- Update `README.md`, `docs/image-releases.md`, and release notes. Bump the patch version from `0.1.3` to `0.1.4` and point `scripts/release.json` at `docs/releases/0.1.4.md`.

## Contract evidence

Read public upstream sources at pinned tags `v1.24.7` and `v28.2.0`: `routers/api/v1/api.go`, `services/context/package.go`, `routers/api/v1/packages/package.go`, `models/packages/package_version.go`, and `services/convert/package.go`. The newer middleware resolves named packages before listing; the older middleware resolves descriptors only for version-specific requests. Owner listing avoids named resolution, applies owner/type/non-exact case-insensitive name/non-internal filters, and returns version rows without silently removing them based on repository visibility. Conversion can filter the repository field, not the version row. Existing individual-owner authority is therefore required before using an empty owner search. Source references and visibility limits are recorded in `docs/image-releases.md`.

No design deviation was needed. Shared record iteration avoids duplicating validation and budget policy across the two evidence paths. Generic API reads still require HTTP 200.

## Verification

- Disposable baseline regression: ran the committed `main` release helper against the corrected `28.2.0` fake with no packages. Reproduced `Package/repository evidence unavailable (HTTP 404)` during startup and verified zero publication effects. Only the disposable test checkout was changed for this experiment.
- `env PYTHONPATH=tests python3 -B -m unittest test_package_release.PackageEvidenceTests test_http_diagnostics -v`: passed, 28 tests, including additional HTTP 201/401 rejection cases after final test edits.
- `env PYTHONPATH=tests python3 -B -m unittest test_package_release.PackagePublicationTests -v`: passed, 18 tests at the initial focused run. The subsequently added staged-package disappearance test passed separately. The arbitrary HTTP error/unsupported-version test was rerun and passed after its test-case construction was clarified.
- `python3 -B -m unittest discover -s tests -v`: passed, all 86 tests in 480.371 seconds. This includes first publication under both supported server contracts and staged-package disappearance. Subsequent focused reruns cover the final additional rejection cases and test-only cleanup; production changes after the full suite started were whitespace-only.
- `bash -n build-all.sh`: passed.
- `bash build-all.sh --validate`: passed with `Configuration valid; no credentials or external operations used`.
- `git diff --check`: passed; repeated before commit.

## Limits

No real Docker builds, registry logins/pushes, authenticated Gitea probes, package links, Git tag pushes, or releases were performed. Public upstream source reads and offline fake-boundary tests do not prove native publication readiness. Internal-only/versionless records can still cause safe link refusals, ambiguous states still require manual inspection, and no automatic cleanup, reassignment, or rollback was added. Actual publication still requires clean, pushed `main`, existing credentials/trust/tooling, and single-operator exclusion.
