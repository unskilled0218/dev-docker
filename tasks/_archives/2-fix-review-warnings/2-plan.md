# plan

- [scope](#scope)
- [Implementation Plan](#implementation-plan)
  - [1. Preserve validated Docker build proxies](#1-preserve-validated-docker-build-proxies)
  - [2. Give tests independent release metadata](#2-give-tests-independent-release-metadata)
  - [3. Add warning-specific regression coverage](#3-add-warning-specific-regression-coverage)
  - [4. Update release metadata and documentation](#4-update-release-metadata-and-documentation)
  - [5. Verify and record results](#5-verify-and-record-results)
- [Acceptance Criteria](#acceptance-criteria)
- [Risks And Decisions](#risks-and-decisions)

## scope

Resolve only warnings W1 and W2 from `tasks/1-update-build-publish/5-code-review.md`: preserve Docker-configured build proxies during publication while retaining credential isolation, and remove test dependence on the project's initial release version. Changes belong in `scripts/release_data.py`, the existing test module/fake ports, relevant release documentation, and version/notes metadata. Do not change Dockerfiles, Compose files, publication state transitions, registry targets, credentials, image dependency policy, or unrelated user work. Suggestion S1 about Dockerfile headers is explicitly deferred. This planning step creates this document only; it neither implements fixes nor runs publication.

## Implementation Plan

### 1. Preserve validated Docker build proxies

- Extend `docker_auth()` in `scripts/release_data.py` with a small proxy-configuration validation/copy helper. Read the original Docker config through the existing bounded strict JSON loader; do not introduce another configuration file, executable shell settings, or dependency.
- Preserve the original `proxies` map as structured data in the private Docker config. Keep `default` and all per-daemon keys rather than guessing which endpoint a context name or Buildx node represents; let Docker retain its normal endpoint-selection and override semantics. Do not merge default/per-daemon entries, rewrite endpoint names, expand proxy values, or inject proxy arguments into shell commands.
- Treat absent or JSON-null `proxies` as no configured proxies; preserve empty maps and explicit empty string values. Require a map of nonempty, control-free string keys to maps containing only `httpProxy`, `httpsProxy`, `ftpProxy`, `noProxy`, and `allProxy`. Require string values without control characters, allowing empty strings and preserving punctuation, credentials, comma-separated exclusions, CIDRs, and wildcard text verbatim. Refuse malformed maps, unsupported fields, invalid types, or controls with a generic error that never includes keys or values. Do not impose HTTPS-only URL rules on Docker's proxy settings or parse `noProxy` as a URL.
- Add only the validated `proxies` field to the existing allowlist of connection/plugin configuration. Continue starting with empty `auths` and excluding caller `auths`, `credsStore`, and `credHelpers`. Preserve current context selection, Docker host/TLS environment handling, plugin paths, and `BUILDX_CONFIG` behavior. Build-only must continue using the caller's original configuration unchanged.
- Keep proxy values inside the run-owned private Docker configuration, never logs, command arguments, build contexts, settings/state summaries, Git annotations, release notes, or persistent auth files. Ensure its directory and config file remain private (0700 and 0600 respectively). Do not modify the original Docker config. Existing exit/signal cleanup must remove the private copy.
- Complete validation before registry login, staging pushes, tag publication, or alias/release writes. Invalid proxy configuration must fail before those effects; do not silently discard it or turn a validation failure into retry/reconciliation authority.

### 2. Give tests independent release metadata

- Update `ReleaseFixture` in `tests/test_build_all.py` to create explicit test-owned version, tag, notes path, and notes content before its initial temporary Git commit. Use a fixture default such as `1.2.3`, independent of root `VERSION` and the production notes path. Continue copying implementation files/configuration structure, then override only the temporary fixture's release metadata.
- Expose fixture metadata through shared attributes such as `self.version`, `self.tag`, and `self.notes_path`, with a fixture-construction option/helper for an alternate valid version. Derive the tag from that version once. Do not derive expected outcomes by calling the production `settings()` implementation under test.
- Replace initial-version literals in successful CLI invocations, final alias keys, tag/release records, orphan/conflict scenarios, notes-path mutations, and assertions with those fixture attributes. Leave intentionally invalid versions/tags explicit, but ensure each mismatch is actually different from the fixture tag.
- Remove `switchboard/v0.1.0` from `tests/fake_release_ports.py`. Carry the test's requested tag in test state and use it to select malformed fifth-image evidence and other version-sensitive injections. Keep this mechanism test-only; do not add production flags or environment overrides for test control.
- Build fixture notes/configuration from test-owned data rather than string-replacing a particular production release note. Ensure fixture setup still commits matching metadata so clean/pushed-source, tag identity, and completed-retry checks retain their current meaning.

### 3. Add warning-specific regression coverage

- Add focused proxy tests for missing config, missing/null/empty proxy settings, default-only settings, per-daemon settings, explicit empty overrides, and all five supported proxy fields. Include URL user information and nontrivial `noProxy` strings using synthetic values only. Assert exact preservation of the proxy map and unchanged original config bytes, not hand-written reimplementations of Docker's selection algorithm.
- Combine proxy preservation with existing context/plugin isolation tests: assert original registry auth/helper fields remain absent and the private config keeps context/plugin metadata and private permissions. Cover original `DOCKER_CONFIG` default/empty and relative-path handling without contacting real Docker.
- Add negative proxy cases for malformed nested structures, unsupported fields, non-string values, controls, duplicate JSON fields, and oversized original config. Through the shell entry point and fake ports, assert refusal before login/build/tag/promotion/release effects, absence of synthetic secrets in output, and private temporary cleanup.
- Extend the fake Docker build port so a publication scenario can verify it sees the expected proxy map after auth isolation, without persisting or printing its synthetic credential-bearing values. Add a successful fake publication/cleanup case with proxies. Keep checks of source context contents and registry-auth isolation intact.
- Exercise both the fixture default and an alternate version (for example `2.4.6`) for matching-tag local builds, successful fake publication with read-only completed retry, and fifth-image orphan/conflict plus malformed-evidence refusal. Assert the active alias is targeted and negative cases produce zero publication effects. Reuse focused scenario helpers rather than duplicating the entire suite through version-specific subclasses.
- Add a regression proving fixture metadata is independent of a valid project release-metadata change, using temporary copies only. Existing success/failure behavior must not require edits to test literals when root `VERSION` and its production notes path advance. Avoid line-coverage targets or interpreting fake results as native proxy/network proof.

### 4. Update release metadata and documentation

- At implementation time, increment the existing bug-fix version from 0.1.0 to 0.1.1, add `docs/releases/0.1.1.md`, and point `scripts/release.json` at those notes. Preserve historical 0.1.0 notes. If project metadata has advanced before implementation, choose the next patch version under the same convention instead of overwriting newer work.
- Update `docs/image-releases.md` to explain validated default/per-daemon proxy preservation, explicit refusals, unchanged registry-auth isolation, and the possibility of credentials inside proxy URLs. Keep proxy examples synthetic and avoid printing private Docker configuration in troubleshooting instructions.
- Extend its opt-in native checklist to compare proxy build-argument behavior before/during private-auth isolation for default and endpoint-specific settings, including exclusions, without production login/pushes or secret-bearing diagnostic output. Retain separate authorization and prerequisite requirements.
- Update the relevant README release-documentation sentence briefly; keep detailed configuration in the dedicated document and avoid duplicating the version there. Maintain tables of contents for created Markdown files and any changed headings.

### 5. Verify and record results

- Run `python3 -B -m unittest discover -s tests -v` with sufficient harness time for the existing approximately four-minute suite and added publication scenarios. Run focused proxy/fixture regressions first to shorten feedback, then the complete suite on final implementation files.
- Run `bash -n build-all.sh`, `bash build-all.sh --validate`, Python AST/syntax checks without bytecode output, and `git diff --check`. Validation must still require neither credentials nor Docker/network operations.
- Record changes, W1/W2 coverage, version update, verification results, and remaining native-readiness limits in this task's `4-implemented.md` during implementation. Follow the implementation workflow's new task-branch and commit requirements; this planning commit does not create that branch or change version files.
- Do not run real image builds, read user credentials, log into registries, push Git/image tags, create releases, install dependencies, or execute native smoke checks as part of automated verification. Report missing prerequisites or deferred checks rather than claiming readiness.

## Acceptance Criteria

- Publication preserves validated Docker proxy data, including default/per-daemon mappings and explicit empty values, without importing original registry auth/helpers or changing Docker context/plugin routing.
- Proxy data remains private and unchanged at its source. No credential-bearing values enter logs, command arguments, build contexts, public metadata, or persistent auth files; run-owned copies are cleaned up.
- Malformed, oversized, or unsupported proxy configuration refuses before publication effects, with generic errors and zero mutation/reconciliation authority.
- Test fixture version/tag/notes are independent of production release metadata. Success, completed retry, and fifth-image negative scenarios work for two distinct fixture versions; no fake-port failure target depends on the initial project tag.
- Existing five-image dependency, credential, source/target, alias-guard, lost-response, and cleanup tests remain passing. Regression assertions observe configuration/side effects and do not replace native Docker behavior with an untested claim.
- Root version and configured notes agree with the next patch release, README/docs describe relevant behavior, and all local checks pass. Actual proxy routing and native operational readiness remain explicitly unverified until separately authorized checks pass.

## Risks And Decisions

- Proxy URLs may contain credentials. Preserve them only in the private config and use synthetic test values; extending configuration preservation must not restore original registry helpers/auth or expose full config in diagnostics.
- Preserve the validated complete proxy map rather than reimplementing Docker's default/per-endpoint precedence. Shape/key validation is deliberately narrow; unsupported proxy fields fail clearly instead of silently disappearing. This does not configure daemon proxies, host curl/Git proxies, DNS, trust stores, or BuildKit server networking.
- Offline tests can prove data preservation and refusal boundaries, not that a specific native Buildx version forwards proxies or that downloads succeed. The existing operational gate remains in force.
- Independent fixture metadata must still be committed inside each temporary repository before publication tests. Updating it after fixture commit would create dirty-source failures unrelated to W2.
- Fixing W1 changes helper hashes, and the patch release changes source/version identity. Existing publications must remain immutable; do not reinterpret completed old releases as new-format ownership or repair their aliases.
- Suggestion S1, broader Dockerfile/toolchain refactoring, architecture/platform expansion, and publication recovery redesign remain outside this task.
