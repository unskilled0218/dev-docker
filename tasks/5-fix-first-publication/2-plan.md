# plan

- [plan](#plan)
  - [scope](#scope)
  - [Implementation Plan](#implementation-plan)
    - [1. Record the version-specific API contract](#1-record-the-version-specific-api-contract)
    - [2. Add narrowly scoped absence verification](#2-add-narrowly-scoped-absence-verification)
    - [3. Correct fixtures and add regression coverage](#3-correct-fixtures-and-add-regression-coverage)
    - [4. Update documentation and validate offline](#4-update-documentation-and-validate-offline)
  - [Acceptance Criteria](#acceptance-criteria)
  - [Risks And Decisions](#risks-and-decisions)

## scope

Fix the startup package inventory in `scripts/release_data.py` so a fresh release can create missing `base` and `npm` packages through its existing staging pushes. Preserve authenticated owner/repository checks, existing package association verification, final publication ordering, bounded reads, and fail-closed behavior. Update offline tests and `docs/image-releases.md`. Do not perform live authenticated probes, builds, publication, server configuration changes, or remote cleanup during implementation.

## Implementation Plan

### 1. Record the version-specific API contract

- Confirm upstream `v1.24.7` and `v28.2.0` routing, package middleware, list handlers, search behavior, and conversion permissions before changing absence rules. Relevant sources are `routers/api/v1/api.go`, `services/context/package.go`, `routers/api/v1/packages/package.go`, package search models, and `services/convert/package.go`.
- Planning inspection found a material version difference: `v28.2.0` resolves a package by name in middleware and returns 404 before `ListPackageVersions` when the package does not exist; `v1.24.7` only resolves a descriptor when a version parameter is present, allowing a missing package's version listing to return `200 []`.
- Both versions expose authenticated `GET /api/v1/packages/{owner}` without requiring an existing named package. Its handler supports `type=container`, a non-exact name search `q`, pagination, and excludes internal versions. Confirm that the verified individual owner sees all matching non-internal versions and that the search includes an exact target name.
- Document pinned upstream references and the visibility limitations. Do not expand the supported server-version allowlist. If source inspection does not establish complete owner-list visibility and reliable filtering, stop and revise this plan rather than accepting 404 as absence.

### 2. Add narrowly scoped absence verification

- Keep `api_read` strict: HTTP 200 remains mandatory for ordinary API reads. Do not change transport status acceptance, authentication, TLS handling, or general 404 semantics.
- In `package_association`, inspect the status of the initial exact package-version request through a narrowly scoped helper or local request path. Continue existing validation and pagination for HTTP 200 responses, including the established `200 []` case.
- Only an initial exact package-list HTTP 404 may trigger independent absence verification. A 404 after any previously observed version is an incomplete inventory and must stop; other HTTP or transport failures must not trigger the fallback.
- Require the existing `package_authority` result first, including supported version, matching active individual owner/principal/login, exact repository ownership, enabled Packages, admin permission, and unchanged captured authority.
- For independent verification, request `GET /api/v1/packages/{owner}?type=container&q={name}&page=1&limit=100` with the existing URL encoding and HTTP boundary. Require HTTP 200 JSON arrays on every page through a confirmed terminal empty page; never interpret this endpoint's 404 as absence.
- Treat `q` as a non-exact search. Validate returned version identities, container type, owner identity, nonempty names/versions, unique positive version IDs, and duplicate records across pages. Allow valid neighboring names such as `base-tools`, but compare exact names locally. If any exact target record exists, refuse the contradictory exact-endpoint 404 without adopting its association or authorizing writes.
- Return `absent` only after the complete successful filtered owner inventory contains no exact target. This means no visible non-internal target versions, not proof that no internal-only or versionless package record exists.
- Apply the existing shared inventory deadline, byte, page, and item budgets, repeated-page detection, and terminal-page requirement to fallback reads. Preserve sanitized HTTP-status diagnostics without request URLs, bodies, headers, tokens, or credential paths.
- Do not cache absence across guards. Existing post-staging reads must observe actual package versions before linking; `link_package` must still reject absent packages. Completed retries, confirmed links, and tag-bound states must still require linked packages and never repair them.

### 3. Correct fixtures and add regression coverage

- In `tests/fake_release_ports.py`, model missing named-package reads by server version: 404 on `28.2.0`, `200 []` on `1.24.7`. Keep existing empty-version package records distinct from nonexistent packages.
- Add the authenticated owner-list route with container/name filters and pagination. Ensure generated version IDs are unique across packages for owner-wide results, stable across pages, and compatible with existing version identity tests.
- Extend `tests/test_package_release.py` with fresh publication for both characterized versions starting with no packages, plus one missing package alongside an existing correctly linked or unlinked package. Assert ordered builds, package creation through staging, required links, aliases, tag/release creation, and a read-only completed retry.
- Add evidence tests proving an initial exact 404 only becomes absence after a complete authorized owner inventory. Cover neighboring names, exact targets on later pages, multiple pages, and the older server's direct empty-list behavior.
- Keep arbitrary exact 404 refusal tests meaningful: make independent owner evidence unavailable, contradictory, or invalid instead of expecting every initial named-package 404 to fail. Preserve existing HTTP-status and secret-redaction assertions for refusal paths.
- Cover owner-list 401/403/404/5xx, transport failure, malformed/non-array/oversized JSON, invalid owner/type/identity fields, duplicate IDs, repeated pages, missing termination, and resource budgets. Verify failures occur before login/build/push/link/tag/release effects during startup.
- Verify wrong principal, disabled Packages, insufficient repository access, unsupported versions, foreign associations, partial exact inventories followed by 404, and authority drift remain refusals. Preserve internal-only/versionless conflict handling and lost-response tests; absence must never confirm a lost link response or authorize reassignment.
- Update focused mocks and call-count expectations affected by the additional request path, including HTTP diagnostic tests where needed. Keep excluded images and unrelated packages untouched.

### 4. Update documentation and validate offline

- Update `docs/image-releases.md` package visibility, HTTP diagnostics, and contract references to explain the version-specific missing-package behavior and independent owner-list proof. Explain that no prior `--build-only` run or manual package creation is needed.
- Retain warnings about inaccessible resources, internal-only records, ambiguous states, single-operator exclusion, and no automatic repair or rollback. Keep README simple and do not change `todo.md`.
- Run `python3 -B -m unittest discover -s tests -v`, `bash -n build-all.sh`, `bash build-all.sh --validate`, and `git diff --check`. Review the diff for any broadened absence or mutation authority.
- Record offline results and distinguish them from unperformed native verification. Actual Gitea publication remains a separately authorized operation from clean, pushed `main` with existing prerequisites.

## Acceptance Criteria

- Offline integration tests publish both images from an empty package namespace under both supported server contracts, without prior local images or manual packages.
- A named-package 404 alone never grants absence or mutation authority; a complete successful owner inventory and verified authority are required for the fallback.
- Inaccessible, contradictory, malformed, oversized, or incomplete evidence stops startup before publication effects. No sensitive request or response data appears in diagnostics.
- Existing package associations, staging reuse, post-staging verification, completed read-only retries, publication ordering, and no-reassignment/no-rollback safeguards remain intact.
- All offline checks pass and documentation accurately describes first-time publication. Offline success is not represented as proof of native publication readiness.

## Risks And Decisions

- Prefer a narrow first-page 404 fallback over replacing all exact inventories with namespace-wide reads. This preserves existing exact-version association validation and limits additional traffic to missing-package checks.
- A filtered owner listing reports versions, not every package record. Internal-only/versionless conflicts remain safe refusals after staging rather than grounds for forced linking or cleanup.
- An exact target found by the fallback contradicts the failed exact read. Refuse instead of using alternate evidence to bypass a visibility or routing problem.
- Search filters are not exact-name guarantees. Validate and paginate neighboring results without adopting, linking, or mutating them; budget exhaustion remains a refusal.
- Reads and writes are not atomic. Retain fresh guards and the single-operator requirement rather than claiming transactional publication.
- Release helper hashes participate in release identity. Do not rewrite previous tags or release objects to accommodate changed scripts.
