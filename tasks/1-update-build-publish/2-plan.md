# plan

- [scope](#scope)
- [Implementation Plan](#implementation-plan)
  - [1. Define the adapted release contract](#1-define-the-adapted-release-contract)
  - [2. Add local validation and publication preflight](#2-add-local-validation-and-publication-preflight)
  - [3. Build the five-image dependency graph](#3-build-the-five-image-dependency-graph)
  - [4. Publish and verify one release for the image set](#4-publish-and-verify-one-release-for-the-image-set)
  - [5. Test failures and document operation](#5-test-failures-and-document-operation)
- [Acceptance Criteria](#acceptance-criteria)
- [Risks And Decisions](#risks-and-decisions)

## scope

Update the root `build-all.sh` build and publication process using `https://git.lan/dev/container-release-template` version 0.4.0, inspected at commit `1d051b36888fd64d9bfcd49e8e09f504943b6a1a`, as a reviewed reference rather than a runtime dependency. Adapt its Bash-first, explicit-configuration, committed-source, digest-verified release model to this repository's five images. Keep implementation limited to the build/release entry point, focused helpers and settings, version and release notes, dependency-image arguments, tests, and release documentation. Do not change application setup, Compose files, `command.md`, or unrelated user work. This task only writes this plan; it does not implement or publish anything.

## Implementation Plan

### 1. Define the adapted release contract

- Keep `bash build-all.sh` as the public entry point. No arguments publishes the configured version; `--validate` performs side-effect-free local validation; `--build-only` builds local images without publication; `--help` describes the contract. Reject unsupported or combined modes before external effects.
- Replace positional release tags with root `VERSION` containing strict `MAJOR.MINOR.PATCH`, derive `v<VERSION>`, and require committed matching release notes. Record this intentional CLI change in documentation. Choose the initial version after checking existing repository tags/releases; do not overwrite existing history.
- Add `scripts/release.json` and focused Bash/Python-standard-library helpers under `scripts/`. Configure the actual `https://git.lan`, `dev/dev-docker`, login, notes path, token path, certificate path, and all five image names explicitly. Never inherit the template's Hello World image or publish target.
- Model the ordered image graph as `my-base` from `Dockerfile/base.Dockerfile`, `npm-non-root` from base, `android-dev` from npm, and `tauri-dev` plus `switchboard` from Android. Validate duplicate names, unknown keys, path escapes, mismatched registry/owner scopes, and malformed configuration before execution.
- Configure only `linux/amd64` initially. The current Switchboard Java path and downloaded Android/Watchman tooling are architecture-specific; multi-platform enablement and toolchain repair are separate work.

### 2. Add local validation and publication preflight

- Make `--validate` check settings, graph, version, notes, and required source paths without reading credentials, contacting services, invoking Docker, or creating locks/temp state. Help must need only Bash.
- For publication, require Bash, Python 3.11+, Git, curl, Docker Buildx, a builder advertising the configured platform, trusted HTTPS, and a clean, already-pushed `main`. Verify effective fetch and push targets and exact remote main before registry writes; do not push source automatically.
- Use a checkout-local lock and private run-owned temporary directory, with explicit exit/signal cleanup. Ignore only new runtime state paths. Recheck captured source and configuration before publication writes.
- Default the publication credential to `~/.config/git/token`, with `GIT_TOKEN` as a file-path override and `GIT_USERNAME` as a login override, matching the reference. Document migration from `FORGEJO_TOKEN_FILE` and `FORGEJO_USERNAME`. Require a readable, non-symlink, user-owned private token file outside the repository; do not log its contents or pass token values in arguments.
- Preserve `BUILD_CERT_FILE` and the current certificate default. Pass the selected token only through stdin for registry login and the existing `forgejo-token` BuildKit secret for the base build. Build-only still requires this build secret but must not log in or call publication APIs.
- Isolate registry auth without losing the caller's Docker host/context, TLS metadata, Buildx state, or plugin discovery. Resolve the reference's documented config-local Buildx plugin issue rather than copying it. Never install certificates, privileged emulation, or other system dependencies automatically.

### 3. Build the five-image dependency graph

- Add an `ARG BASE_IMAGE` before each dependent Dockerfile's `FROM`, preserving its current local `:latest` parent as the default. Release builds override this argument with the verified parent `registry/owner/image@sha256:...`, never a mutable local tag.
- Export only the captured committed source into the private publication build context, then inject the selected certificate. Never copy worktree files, ignored/untracked secrets, or the credential into that context. Hash the certificate as part of release identity because it is an external build input.
- Build each image once into a release-specific staging tag using Buildx, with source/version/revision labels and metadata capture. Verify its digest, platform, and configuration labels before building descendants. Track the digest map for the entire graph.
- Preserve local `image:latest` availability in `--build-only` using ordered Buildx builds with `--load` on AMD64. This explicit development mode may use current Dockerfiles without clean-main or remote checks; it still validates arguments, settings, required inputs, and dependencies.
- Do not promote any public `latest` aliases, create a Git tag, or create a release until all five staging images verify. Staging pushes are unavoidable intermediate remote writes and must be reported as such on failure.

### 4. Publish and verify one release for the image set

- Adapt the reference's bounded HTTP/registry/Git reads and strict JSON handling. Treat malformed, truncated, failed, or incomplete inventory reads as refusal, never evidence of absence. Disable ambient curl configuration, redirects for authenticated calls, and credential forwarding to foreign registry token realms.
- Capture predecessor aliases for all images before staging. Bind one deterministic annotated Git tag to source, version, settings/helper hashes, notes hash, certificate hash, platform, all five image digests, and predecessors. Push only the exact non-force tag.
- Before each promotion, freshly verify the expected tag and the complete alias set. Unpromoted images may equal their captured predecessor or prepared digest; once promoted, an image must remain at its prepared digest. This avoids the reference's documented post-promotion predecessor-acceptance flaw.
- Promote verified digests to version and `latest` aliases without rebuilding, refusing any conflicting version alias. Create one Gitea release with the committed notes only after every intended alias verifies. Verify the tag, release body, immutable digests, and aliases again before returning success; print all image references and the release URL.
- On retry, reuse staging only when complete identity and image evidence match. For a fully completed publication, verify without building or writing. Refuse tag-only, release-only, conflicting, missing-content, or partially promoted startup states requiring manual review. Do not force tags, repair remote records, delete images, roll back aliases, or perform retention cleanup.
- Reconcile a lost write response only against fresh exact evidence within the same invocation. Report the failed phase and known image/alias state without leaking credentials. A checkout lock does not exclude other publishers; document the requirement for one operator across the image set.

### 5. Test failures and document operation

- Extend `tests/test_build_all.py` and add focused helper/publication tests with temporary repositories and fake Git, curl, Docker, and registry responses. Fix stale four-image assertions: the script already includes Switchboard, while the tests and release guide omit it.
- Cover all five images, graph ordering, digest-bound parents, labels, certificate/secret handling, build-only local tags, paths containing spaces, and invocation outside the repository. Verify all staging builds precede final publication.
- Cover strict configuration/version/notes validation, clean and pushed source checks, target mismatch, missing platform/tools, token permissions, Docker connection/plugin preservation, lock contention, and cleanup on failure/signals.
- Exercise staging/build/push failures, conflicting aliases, failed/oversized inventory reads, lost write responses, completed no-op retries, ambiguous partial states, changed confirmed tags, and a promoted alias reverting to its predecessor. Assert no subsequent unauthorized writes or rollback.
- Update `docs/image-releases.md` for configuration, credential migration, versioned publication, validation, build-only, all five images, prerequisites, trust, retry limits, and recovery. Keep `README.md` brief with a dedicated documentation link. Include a table of contents when creating Markdown files.
- Run `python3 -B -m unittest discover -s tests -v`, shell syntax checks for `build-all.sh` and new shell helpers, and `bash build-all.sh --validate`. Do not run a real release or install missing prerequisites; report any missing dependencies to the user.

## Acceptance Criteria

- Root `build-all.sh` supports the documented modes and explicit repository-specific settings without fetching executable release code at runtime.
- All five images build in dependency order; release children consume verified parent digests, while build-only preserves existing local names and Dockerfile defaults.
- Publication uses committed source, one version, one identity-bound tag/release, verified staging digests, and guarded final aliases. Failure never authorizes force, deletion, rollback, or silent repair.
- Validation has no credential or external side effects. Build-only performs no registry login, push, remote Git mutation, or Gitea release request.
- Credentials remain outside source contexts, logs, committed files, image layers, and persistent Docker auth. Existing certificate trust and Docker routing remain intact.
- Tests cover five-image success and negative/retry paths, and all local verification commands pass. Mocked results are not presented as live build or publication proof.
- Documentation describes breaking CLI/default-credential changes, AMD64-only support, non-atomic multi-image publication, and manual handling of uncertain states.

## Risks And Decisions

- The reference supports one image and exactly two platforms; copying its schema or running it five times would not provide one coherent release. Extend its identity and guards to the full graph, with explicit AMD64-only scope.
- Gitea, Git, and five registry aliases cannot be updated atomically. Failures can leave staging images, a tag, or some promoted aliases. Preserve evidence and stop; no automatic rollback or claim of transaction atomicity.
- The reference explicitly documents unresolved alias-guard and Buildx discovery warnings. The adaptation must cover both with tests before claiming readiness.
- Existing Dockerfiles download mutable remote scripts and packages. A captured source commit and verified output digest establish release identity, not reproducible bytes or runtime/toolchain correctness. Repairing existing image setup is outside this task.
- Base credentials are still required because the current Dockerfile requests a BuildKit secret, even though its final secret-mounted command only creates a directory. Do not redesign this unrelated setup in the release migration.
- Real image builds and publication require separate user-authorized verification with provisioned credentials, Docker, registry access, and trusted certificates. This workflow must not install privileged host dependencies or publish during tests.
