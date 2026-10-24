# plan

- [scope](#scope)
- [Implementation Plan](#implementation-plan)
  - [1. Reduce the build and release graph](#1-reduce-the-build-and-release-graph)
  - [2. Update image references](#2-update-image-references)
  - [3. Associate released packages with the repository](#3-associate-released-packages-with-the-repository)
    - [3.1. Establish the supported API and owner authority](#31-establish-the-supported-api-and-owner-authority)
    - [3.2. Classify package evidence without ambiguous absence](#32-classify-package-evidence-without-ambiguous-absence)
    - [3.3. Link and verify packages before publication](#33-link-and-verify-packages-before-publication)
  - [4. Update regression tests](#4-update-regression-tests)
  - [5. Update release documentation and metadata](#5-update-release-documentation-and-metadata)
  - [6. Verify implementation without publication](#6-verify-implementation-without-publication)
- [Acceptance Criteria](#acceptance-criteria)
- [Risks And Decisions](#risks-and-decisions)
- [Review Resolution](#review-resolution)

## scope

Build and publish only `base` and `npm`, publishing under `git.lan/dev` with both `v<VERSION>` and `latest` aliases. Explicitly associate these container packages with `dev/dev-docker` so they appear on its Packages page. Keep Android, Tauri, and Switchboard Dockerfiles for manual use; exclude those images from both automated local builds and every release operation. Retained Android references use `android` as requested. Do not publish, delete existing packages, rewrite existing releases, or change application toolchains during implementation.

## Implementation Plan

### 1. Reduce the build and release graph

- In `scripts/release.json`, configure the ordered release graph as `base` using `Dockerfile/base.Dockerfile`, then `npm` using `Dockerfile/npm.Dockerfile` with parent `base`.
- In `scripts/release_data.py`, reduce the shared strict graph to `base` and `npm` for both publication and local builds. Do not introduce a separate five-image local graph.
- Ensure `settings`, `snapshot`, `prepare_image`, `build_args`, and `accept_image` use only these two images. Excluded Dockerfiles must not be automated build inputs, validation prerequisites, or release prerequisites.
- Keep release inventory, staging checks, annotated-tag digest/predecessor sets, guards, promotions, final verification, summaries, and failure status limited to `base` and `npm`.
- Replace the hard-coded five-image loop in `build-all.sh` with the two-image list supplied by the helper. Update local success messages without duplicating graph definitions.
- Preserve clean pushed `main`, digest-pinned release parents, local parent-ID checks, private credentials/proxies, locks, bounded reads, and existing refusal rules.

### 2. Update image references

- Change `Dockerfile/npm.Dockerfile` to default to `base:latest` and `Dockerfile/android.Dockerfile` to `npm:latest`.
- Change the Tauri and Switchboard Dockerfile parent defaults to `android:latest`. Retain their remaining contents and filenames.
- Update `compose/docker-compose.yml` from `git.lan/dev/my-base:latest` to `git.lan/dev/base:latest`. Keep `tauri-dev` references because that local image is not being renamed.
- Search active scripts, Compose files, tests, and documentation for old image names. Update current references without rewriting archived tasks or historical release notes.

### 3. Associate released packages with the repository

- Add narrowly scoped package-read, association-check, and link helpers in `scripts/release_data.py`, using the existing authenticated, bounded HTTPS boundary in `scripts/release_io.py`. Encode path segments; retain strict HTTPS, no redirects, and sanitized diagnostics. Never use the unlink endpoint.

#### 3.1. Establish the supported API and owner authority

- Use upstream Gitea `v1.24.7` as the initial characterized contract, not a blanket claim that every newer version or fork behaves identically. During implementation, identify the deployed version through a bounded read-only `GET /api/v1/version` if reachable; otherwise record deployment compatibility as blocked, without guessing or making remote writes. Other versions require source/schema characterization and matching fixtures before inclusion in an explicit supported-version set; never install, downgrade, or update the server automatically.
- At runtime, execute the read-only preflight before registry login, staging pushes, links, Git-tag publication, or release creation. First require a `200` version response with a supported version string. Use a small static set of characterized contracts, not a general plugin system or an automatic minimum-version assumption. Unsupported, development, custom, malformed, or unverified versions stop with compatibility guidance.
- Require `GET /api/v1/user` to return the authenticated token principal, then `GET /api/v1/users/dev` to identify the configured namespace. Require matching positive integer IDs, exact login `dev`, `active` exactly `true`, and `restricted` and `prohibit_login` exactly `false`. Matching the namespace to an authenticated individual principal establishes user ownership under this contract; the reference User schema has no `type` field, so do not invent one. Reject organization namespaces, delegated users, and admin identities other than the owner for this workflow. Configured `username` and `GIT_USERNAME` are not identity evidence. Require the effective registry login to match the verified owner too.
- Require `GET /api/v1/repos/dev/dev-docker` to return exact full name `dev/dev-docker`, a positive integer repository ID, owner ID equal to the authenticated principal, `has_packages` exactly boolean `true`, and `permissions.admin` exactly boolean `true`. Capture that identity. Missing fields, booleans used as integer IDs, mismatched names/IDs, inaccessible resources, or disabled Packages units stop; never silently change repository settings.
- Characterize `ToPackage`, `GetUserRepoPermission`, package-access middleware, and `LinkToRepository` together. In the reference contract, package and linked repository must have the same owner, and a repository owner has owner-level access. Thus a verified active owner has visibility of any valid association in that user namespace; a delegate with package access does not provide this proof. Reject null evidence unless this owner/visibility contract has passed. No claim of unlinked status may come from a null field alone.
- Document the required existing token scopes for authenticated-user reads, repository reads/releases, and package reads/writes, including access to private resources. Failed authorization is a refusal, not an invitation to broaden credentials automatically. Read capability checks do not guarantee a future write will succeed; link failures still stop safely.

#### 3.2. Classify package evidence without ambiguous absence

- For each exact name `base` and `npm`, use the characterized `GET /api/v1/packages/dev/container/{name}?page=1&limit=100` version-list route. Require `200` and a valid JSON array. A supported, authorized successful empty first page proves no non-internal package versions are present; `404`, `401`, `403`, unsupported routes, redirects, transport failures, and malformed bodies never prove absence. Do not use `/-/latest` as an absence probe.
- For nonempty listings, finish bounded pagination through a confirmed empty page. Reuse the inventory time/byte/page/item limits, reject repeated pages and duplicate version identities, and validate every record's positive integer version ID, owner ID/login, exact package name, type `container`, nonempty version, and explicit repository field. All versions must expose a consistent package-wide association. Package API `id` identifies a version, not a stable package ID; do not require IDs from different versions to match.
- Classify a nonempty package as linked-correct only when its repository ID, full name, and owner match the captured target. Classify it as unlinked only for an explicit JSON null under the verified owner/visibility contract. Missing repository fields are malformed evidence; foreign repositories, conflicting version records, unavailable visibility, and uncertain evidence stop before publication writes.
- A successful empty list proves no visible publishable version, not permission to overwrite an unseen package record. Retain the reference server's already-linked-package refusal as an additional guard; never unlink or retry with force if an internal-only or versionless package record makes the later link fail.
- Repeat the strict read/classification immediately before each association mutation. After staging, the listing must be nonempty; disappearance or an empty list is an error, not fresh-build or link authority. Repeat owner and repository identity/settings checks before mutation and completion rather than treating startup authority as permanent.

#### 3.3. Link and verify packages before publication

- After both staging images are verified, but before publishing the Git tag, ensure both packages are associated with the captured repository. Skip packages already linked correctly. For a verified unlinked package only, call `POST /api/v1/packages/dev/container/{name}/-/link/dev-docker` and require `201`; verify the exact package-wide repository association afterward through the strict listing helper. OCI source labels remain useful metadata but are not the visibility check.
- The characterized `v1.24.7` service rejects cross-owner associations and packages with an existing repository link. Preserve this protection: never unlink first, never reassign, and never assume that a different server retains this behavior. Keep single-operator exclusion because a read followed by a write is not an atomic conditional API operation.
- Add an explicit package-association phase to `build-all.sh`. Record confirmed link progress in run state and include it in sanitized failure diagnostics. Package links are additional remote writes and are not rolled back automatically.
- Reconcile a lost link response only against a fresh exact association read for this invocation's attempted write. A failed prerequisite read must never grant mutation authority. Stop on unresolved results without unlinking or reassigning packages.
- Recheck associations before tag publication, release creation, and final success. Completed-publication retries verify associations read-only; missing or foreign associations stop with manual-review guidance rather than silently repairing a completed release.
- Keep `--validate` offline and side-effect-free. `--build-only` must never read or write Gitea package associations.

### 4. Update regression tests

- Update `tests/fake_release_ports.py` with package records, repository identity/settings, supported package-read/link routes, association effects, and failure/lost-response controls. Keep all tests offline.
- Build version, principal, namespace, repository, and package-version fixtures from the characterized upstream schema and source, documenting their provenance in test comments. Model actual package association separately from its permission-filtered API representation. The fake link service must reject existing links and cross-owner targets as the reference service does; tests must not invent overwrite behavior.
- Update `tests/test_build_all.py` to assert exactly two release builds, four alias promotions, and two verified package associations. Assert exactly two local builds, named `base` and `npm`.
- Replace fifth-image release refusal cases with second-image cases. Adjust staging reuse and failed-build scenarios to fail npm after a verified base build, then reuse base on retry.
- Assert both local and release build calls exclude Android, Tauri, and Switchboard. Assert release network calls, staging, promotions, and tag digest/predecessor sets never include excluded images or legacy package names. Existing excluded/legacy registry records must remain untouched and must not block release classification. Test that excluded Dockerfiles are not required for either mode while confirming the repository retains them.
- Test absent packages, existing unlinked packages, already-correct links, foreign associations, disabled Packages units, insufficient permissions, unsupported APIs, malformed/oversized reads, failed links, lost responses, and association drift before final success.
- Add the review's hidden-association regression: a delegated principal sees `repository: null` while the fake stores a real foreign link. Require refusal during identity preflight with zero publication writes and zero link attempts. Separately verify that the characterized owner can link a genuinely unlinked package. Missing owner proof or permission evidence must never permit a null-based link decision.
- Distinguish successful empty version listings from `404` on either a supported or unsupported route, hidden-resource responses, and failed reads. Test malformed/unsupported version responses, wrong principal/namespace/repository IDs, organization ownership, missing/null/nonboolean principal status fields, `has_packages`, or admin permission, duplicate/repeated/nonterminal pages, missing repository fields, inconsistent version associations, and invalid package owner/type/name. Every unknown startup case must stop before login, build/push, link, Git-tag push, or release creation.
- Verify version IDs may differ across versions while association identity remains the same. Test internal-only/versionless records so absence classification never bypasses server refusal for an existing link, and test owner/settings drift after staging so no link or final success is authorized by stale startup evidence.
- Verify a failed association phase publishes no Git tag or release. Verify a fresh retry reuses staged images and skips links already confirmed on the server. Completed retries perform no mutations and reject missing/foreign links.
- Retain regression coverage for credentials, proxy isolation, source checks, CLI refusals, local parent identity, partial promotion refusal, and cleanup. Assert no package API calls occur in validation or local mode.

### 5. Update release documentation and metadata

- Keep `README.md` short: describe two images for both automated builds and releases, and retain the existing release-guide link.
- Update `docs/image-releases.md` with image names, the shared two-image graph, both aliases, automatic repository associations, the characterized server versions, verified owner-only policy, required user/repository/package token scopes, private-resource access, Packages-unit requirements, strict absence evidence, and the new pre-tag association phase. Clearly state that unsupported versions require characterization, not a server downgrade or a TLS/authentication bypass.
- Replace statements that package linking is manual or unsupported. Explain that association applies to the entire package, not one tag, and that foreign associations are never overwritten.
- Document that excluded images are not built by `build-all.sh` and receive no new release tags or package links. Existing remote packages and old aliases are retained; removing them is outside scope. Manual builds remain possible using retained Dockerfiles and explicitly supplied parent images; use `android:latest` for a manually built Android image consumed by Tauri or Switchboard.
- During implementation, advance the patch version from `0.1.1` to `0.1.2` if still current, create matching release notes in `docs/releases/`, and update the configured notes path together. Use a fresh version rather than trying to reinterpret an existing five-image release identity.

### 6. Verify implementation without publication

- Run `python3 -B -m unittest discover -s tests -v`, `bash -n build-all.sh`, and `bash build-all.sh --validate`.
- Inspect the final diff for retained Dockerfiles, stale active names, accidental credential output, and release paths that still assume five images.
- Record results and any unavailable checks. Do not install dependencies, run native image builds, push images/tags, or call mutating Gitea APIs as part of implementation verification.
- For separately authorized live acceptance after clean source is committed and pushed, run publication and verify matching `v<VERSION>`/`latest` digests for base/npm, correct package repository associations, and both packages visible at `https://git.lan/dev/dev-docker/packages`.

## Acceptance Criteria

- Default publication builds/releases only `base` and `npm` in dependency order; both version and `latest` aliases point to their verified digests.
- Released container packages are explicitly associated with `dev/dev-docker`; final success requires exact repository association checks, not merely source labels.
- Android, Tauri, and Switchboard are absent from automated local builds, release builds, inventory, staging, tag identity, promotion, and package-association operations. Their Dockerfiles remain available for manual builds.
- `--build-only` builds only `base:latest` and `npm:latest`, with consistent parent references. It never publishes or links packages.
- Existing remote packages, excluded images, old aliases, and historical release records are not deleted, renamed in place, or reassigned.
- Completed retries remain read-only. Conflicting or uncertain association state fails safely without automatic repair or rollback.
- Publication preflight proves the characterized API contract, authenticated user ownership, repository identity/admin visibility, and enabled Packages unit. Missing/hidden/unknown evidence never authorizes writes; a null association is actionable only with the verified owner/visibility contract.
- Package absence requires a successful authorized exact-name version listing on the supported contract. Unsupported-route and hidden-resource `404` responses are refusals, never absence evidence. Multi-version association checks finish bounded pagination and validate package identity without confusing version IDs with package identity.
- All offline verification commands pass. Live package-page visibility remains explicitly unverified until separately authorized publication and UI inspection succeed.

## Risks And Decisions

- “Latest” means the container `latest` alias, not replacing the versioned Git tag with a mutable Git tag. Preserve existing version aliases and release identity checks.
- The updated request excludes Android, Tauri, and Switchboard from both automated builds and release. Keep one two-image graph and retain the excluded Dockerfiles for manual use.
- Package renaming creates new registry package names; it does not migrate or remove old packages. Android's rename affects retained parent references and the documented manual-build tag, not an automated output.
- Gitea links apply package-wide. The characterized upstream `v1.24.7` service refuses already-linked packages; the review's overwrite claim does not apply to that implementation. Still refuse foreign/unknown associations before staging and recheck immediately before mutation; retain single-operator exclusion rather than claiming atomic compare-and-set behavior.
- Repository linking and image publication are not atomic. A failed run can leave staging images or confirmed package links; preserve evidence and require explicit review for ambiguous state.
- API support, token permissions, and repository Packages settings depend on the deployed server. This plan does not certify the installed version. Unsupported capabilities block publication rather than falling back to labels, accepting ambiguous null/404 evidence, or silently changing settings. Owner-only support deliberately excludes organization/delegate workflows until separately designed and characterized.
- Reference documentation: [Gitea package ownership and repository visibility](https://docs.gitea.com/usage/packages/overview/), [v1.24.7 API schema](https://github.com/go-gitea/gitea/blob/v1.24.7/templates/swagger/v1_json.tmpl), [package conversion](https://github.com/go-gitea/gitea/blob/v1.24.7/services/convert/package.go), [owner repository permissions](https://github.com/go-gitea/gitea/blob/v1.24.7/models/perm/access/repo_permission.go), [package routes](https://github.com/go-gitea/gitea/blob/v1.24.7/routers/api/v1/api.go), and [link service](https://github.com/go-gitea/gitea/blob/v1.24.7/services/packages/package_update.go). Public source is contract evidence, not deployed-server compatibility proof.

## Review Resolution

- Critical R6: Sections 3.1 and 3.2 now require authenticated owner identity and a characterized complete-visibility contract before treating explicit null as unlinked. Hidden-null/delegate regressions require zero publication writes. No unlink or force-reassignment path is allowed.
- Warning R1: Sections 3.1 and 3.2 now define a version gate, exact identity/boolean checks, a concrete successful-listing absence rule, bounded multi-version validation, and fail-closed behavior for unsupported/hidden/failed reads. Contract-derived fixtures cover the distinct outcomes instead of using `404` as absence.
- Source correction: Inspection of upstream `v1.24.7` `LinkToRepository` confirms it rejects an existing repository link. Preserve the historical review unchanged, but replace its unverified overwrite assumption in this plan with the verified service behavior. No implementation, deployed-server verification, or publication was performed for this plan update.
