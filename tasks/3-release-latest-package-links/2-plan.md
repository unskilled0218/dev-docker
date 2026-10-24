# plan

- [scope](#scope)
- [Implementation Plan](#implementation-plan)
  - [1. Reduce the build and release graph](#1-reduce-the-build-and-release-graph)
  - [2. Update image references](#2-update-image-references)
  - [3. Associate released packages with the repository](#3-associate-released-packages-with-the-repository)
  - [4. Update regression tests](#4-update-regression-tests)
  - [5. Update release documentation and metadata](#5-update-release-documentation-and-metadata)
  - [6. Verify implementation without publication](#6-verify-implementation-without-publication)
- [Acceptance Criteria](#acceptance-criteria)
- [Risks And Decisions](#risks-and-decisions)

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

- Confirm the deployed Gitea version supports the package-link API and package response repository fields before relying on them. The Gitea 1.24 API documents `POST /api/v1/packages/{owner}/{type}/{name}/-/link/{repo_name}` with a `201` response; use owner `dev`, type `container`, package `base` or `npm`, and repository name `dev-docker`.
- Add narrowly scoped package-read, association-check, and link helpers in `scripts/release_data.py`, using the existing authenticated, bounded HTTPS boundary in `scripts/release_io.py`. Encode path segments; retain strict HTTPS, no redirects, and sanitized diagnostics. Never use the unlink endpoint.
- Read `GET /api/v1/repos/dev/dev-docker` during publish preflight to capture repository identity and require its Packages unit to be enabled. Do not silently enable repository settings. Document an actionable refusal if settings or permissions prevent visibility.
- Inspect both existing package associations during read-only startup, using documented package reads such as `GET /api/v1/packages/dev/container/{name}/-/latest`. Accept confirmed package absence only on a supported endpoint; reject malformed responses, permission errors, uncertain reads, or packages linked to another repository before any publication writes.
- After both staging images are verified, but before publishing the Git tag, ensure both packages are associated with the captured repository. Skip packages already linked correctly. Re-read each association immediately before a link request, refuse foreign associations, and verify the repository ID/full name afterward. OCI source labels remain useful metadata but are not the visibility check.
- Add an explicit package-association phase to `build-all.sh`. Record confirmed link progress in run state and include it in sanitized failure diagnostics. Package links are additional remote writes and are not rolled back automatically.
- Reconcile a lost link response only against a fresh exact association read for this invocation's attempted write. A failed prerequisite read must never grant mutation authority. Stop on unresolved results without unlinking or reassigning packages.
- Recheck associations before tag publication, release creation, and final success. Completed-publication retries verify associations read-only; missing or foreign associations stop with manual-review guidance rather than silently repairing a completed release.
- Keep `--validate` offline and side-effect-free. `--build-only` must never read or write Gitea package associations.

### 4. Update regression tests

- Update `tests/fake_release_ports.py` with package records, repository identity/settings, supported package-read/link routes, association effects, and failure/lost-response controls. Keep all tests offline.
- Update `tests/test_build_all.py` to assert exactly two release builds, four alias promotions, and two verified package associations. Assert exactly two local builds, named `base` and `npm`.
- Replace fifth-image release refusal cases with second-image cases. Adjust staging reuse and failed-build scenarios to fail npm after a verified base build, then reuse base on retry.
- Assert both local and release build calls exclude Android, Tauri, and Switchboard. Assert release network calls, staging, promotions, and tag digest/predecessor sets never include excluded images or legacy package names. Existing excluded/legacy registry records must remain untouched and must not block release classification. Test that excluded Dockerfiles are not required for either mode while confirming the repository retains them.
- Test absent packages, existing unlinked packages, already-correct links, foreign associations, disabled Packages units, insufficient permissions, unsupported APIs, malformed/oversized reads, failed links, lost responses, and association drift before final success.
- Verify a failed association phase publishes no Git tag or release. Verify a fresh retry reuses staged images and skips links already confirmed on the server. Completed retries perform no mutations and reject missing/foreign links.
- Retain regression coverage for credentials, proxy isolation, source checks, CLI refusals, local parent identity, partial promotion refusal, and cleanup. Assert no package API calls occur in validation or local mode.

### 5. Update release documentation and metadata

- Keep `README.md` short: describe two images for both automated builds and releases, and retain the existing release-guide link.
- Update `docs/image-releases.md` with image names, the shared two-image graph, both aliases, automatic repository associations, package permissions, Packages-unit requirements, and the new pre-tag association phase.
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
- All offline verification commands pass. Live package-page visibility remains explicitly unverified until separately authorized publication and UI inspection succeed.

## Risks And Decisions

- “Latest” means the container `latest` alias, not replacing the versioned Git tag with a mutable Git tag. Preserve existing version aliases and release identity checks.
- The updated request excludes Android, Tauri, and Switchboard from both automated builds and release. Keep one two-image graph and retain the excluded Dockerfiles for manual use.
- Package renaming creates new registry package names; it does not migrate or remove old packages. Android's rename affects retained parent references and the documented manual-build tag, not an automated output.
- Gitea links apply package-wide and can overwrite an existing association. Refuse foreign associations and recheck immediately before mutation; the existing single-operator exclusion requirement still applies because the API has no conditional-link guarantee.
- Repository linking and image publication are not atomic. A failed run can leave staging images or confirmed package links; preserve evidence and require explicit review for ambiguous state.
- API support, token permissions, and repository Packages settings depend on the deployed server. Unsupported capabilities block publication rather than falling back to labels or silently changing settings.
- Reference documentation: [Gitea package ownership and repository visibility](https://docs.gitea.com/usage/packages/overview/) and [Gitea 1.24 API schema](https://github.com/go-gitea/gitea/blob/release/v1.24/templates/swagger/v1_json.tmpl). Public API documentation is not proof of deployed-server compatibility.
