# Implemented

- [Changes](#changes)
- [Verification](#verification)
- [Decisions and limits](#decisions-and-limits)

## Changes

- Implemented on new branch `1-update-build-publish`.
- Replaced the root build/push loop with a Bash-owned, five-image release sequence and focused Python-standard-library data/I/O helpers under `scripts/`, adapted from the pinned reference without runtime release-code downloads.
- Added strict `scripts/release.json`, initial root `VERSION` 0.1.0, matching committed release notes, offline validation, CLI compatibility assertions, and documented credential precedence. No existing local/remote tags or public Gitea releases were found when selecting the initial version.
- Added AMD64 platform/driver/endpoint checks, checkout locking, private token/auth handling, context/plugin/Buildx-state preservation, bounded subprocess/HTTPS reads, committed Dockerfile snapshots, and certificate-bound release identity.
- Added `BASE_IMAGE` arguments to the four child Dockerfiles, retaining existing local defaults. Publication binds children to verified registry parent digests; build-only retains five local `latest` images and verifies parent IDs around child builds with a supported Docker-driver builder.
- Added full final-record/version/latest startup classification, pre-write guards, verified staging reuse, one deterministic annotated Git tag, digest-only version/latest promotion, a notes-only Gitea release, completed read-only retries, and narrowly reconciled lost responses. No force, deletion, automatic rollback, retention, or ambiguous-startup repair exists.
- Replaced stale four-image test expectations with 32 offline tests using temporary Git repositories and stateful Git/Docker/curl ports. Updated README and dedicated release documentation, including opt-in native readiness checks.

## Verification

- `python3 -B -m unittest discover -s tests -v`: passed, 32 tests. Coverage includes all five images, parent identities, staging reuse, complete read-only retries without staging, fifth-image conflicts/malformed evidence, orphan/partial startup refusals, lost tag/promotion/release responses, confirmed-alias reversion, source/target checks, token safety, locks, signal cleanup, argument compatibility, plugin/auth isolation, and bounded input handling. Failed pre-write reads produce refusal, never lost-write reconciliation authority.
- `bash -n build-all.sh`: passed. There are no additional shell helper files.
- `bash build-all.sh --validate`: passed without credential access, Docker, or network operations.
- Python AST parsing for both release helpers and both test files: passed without bytecode generation.
- `git diff --check`: passed.
- An early test run hit its 120-second harness timeout and exposed a malformed-404 evidence gap. Registry absence now requires recognized structured registry errors; the subsequent full run passed with a longer timeout.
- All build/publication command execution during tests used fake ports. Native Docker/Buildx/plugin/TLS/parent-filesystem checks, real five-image builds, and production publication were not run and remain unverified. No tools or host dependencies were installed.

## Decisions and limits

- Preserved the user's committed `d15c1af` base Dockerfile change: its existing BuildKit secret is now `token`, mounted at `/home/container/.config/git/token`. The older `forgejo-token` ID mentioned in the plan is no longer requested by the current source. Credential-file defaults and legacy overrides remain compatible; the base setup itself was not redesigned.
- Local image IDs are config digests, not valid registry manifest references for BuildKit `FROM`. Build-only therefore verifies the just-built parent's local ID before and after each child, resolves the checked local tag with `--pull=false`, records the ID as a parent label, and requires exclusion of concurrent local image writers. The separate native marker test must confirm actual parent-filesystem use before operational-readiness claims.
- Snapshots export only the committed Dockerfiles required by the current builds, then inject the captured certificate. They never export unrelated tracked files or ignored/untracked worktree content. Existing application downloads remain mutable and are not claimed reproducible.
- Publication supports only Linux AMD64 and the explicit five-image graph. Unsupported build-only drivers fail before building rather than switching builders or pushing parents.
- Multi-image Git/Gitea/registry changes are not atomic. Staging, a tag, or some aliases may remain after failure. The command reports known state and refuses ambiguous retries instead of repairing or rolling back.
- Native readiness is a separate opt-in gate documented in `docs/image-releases.md`; offline acceptance does not certify real routing, plugin execution, toolchain correctness, or publication safety. A passing native smoke test would not itself authorize publication.
- Unrelated `command.md`, root `docker-compose.yml`, Compose settings, and other user work remain untouched.
