# Implemented

- [Changes](#changes)
- [Verification](#verification)
- [Decisions and remaining limits](#decisions-and-remaining-limits)

## Changes

- Implemented on the new branch `2-fix-review-warnings`.
- W1: added a small Docker proxy-map validator and preserved the complete validated default/per-daemon map in private publication configuration. Empty maps and explicit empty strings remain literal; null/absent settings remain absent. Malformed maps, unsupported fields, invalid types, controls, duplicate JSON fields, and oversized original configuration refuse before publication effects without printing their contents.
- Original Docker config bytes remain unchanged. Caller registry auth/helpers remain excluded; context/plugin/Buildx routing behavior is unchanged. Private directory/file permissions are 0700/0600, and existing run-owned cleanup applies to the proxy copy. Build-only still uses the original Docker config.
- W2: fixtures now generate their own committed version/tag/notes before temporary Git initialization, rather than copying production release metadata. Shared scenario helpers and fake active-tag state replace initial-version literals in successful invocations and refusal injections. Focused local-build, publication/read-only-retry, and fifth-image refusal scenarios exercise fixture versions 1.2.3 and 2.4.6.
- Added regression coverage for default/per-daemon proxy values, empty overrides, credentials/exclusions, config preservation, permissions, missing/empty/default/relative config paths, malformed/oversized inputs, private-proxy publication, failure cleanup, and fixture independence from a temporary project metadata change to 9.8.7. Fake ports compare proxy hashes and record check counts, not proxy values.
- Incremented root `VERSION` to 0.1.1, added matching release notes, updated the configured notes path, and preserved historical 0.1.0 notes. Updated README and dedicated release documentation with the proxy contract and separate native qualification checklist.

## Verification

- `python3 -B -m unittest discover -s tests -v`: passed, 39 test methods in 291.525 seconds, including multi-version subtests, proxy preservation/refusal/privacy, and existing publication safety scenarios.
- Focused helper/data checks: 11 tests passed. Focused local-contract checks: 15 tests passed. Proxy-filtered checks: five tests passed, including malformed-input refusals and private-copy failure cleanup. The separately targeted successful proxy-publication test passed and verified the private proxy map at login and all five builds.
- `bash -n build-all.sh`: passed; the shell entry point is unchanged.
- `bash build-all.sh --validate`: passed with the new version/notes metadata, without Docker, credentials, or network access.
- Python AST parsing: passed for both release helpers and both test files without bytecode output.
- `git diff --check`: passed.
- Verification used temporary Git repositories and fake external command ports only. No real Docker builds, registry login/pushes, Git remote writes, release creation, native readiness checks, dependency installation, or reads of user credentials occurred.

## Decisions and remaining limits

- Copying all validated endpoint entries preserves Docker-owned selection semantics without inventing endpoint normalization, default merging, proxy URL parsing, or another configuration interface. Unsupported proxy fields are explicit refusals, not silently dropped data.
- Proxy URLs may contain credentials. The release tooling stores values only in the caller's existing config and the run-owned private copy, not release-script arguments, source contexts, public identities, or diagnostics. Docker's intended forwarding to build environments and client/toolchain behavior that independently exposes those environments are outside this storage guarantee; native checks must use synthetic values and sanitized outcomes.
- Offline results prove data preservation, isolation/refusal boundaries, and version-independent test behavior, not native Buildx proxy forwarding or real connectivity. Those capabilities remain unverified until the separately authorized native checklist passes. Passing that checklist would not itself authorize production publication.
- No changes were made to Dockerfiles, image dependencies, publication state transitions, registry targets, token selection, Compose files, or unrelated user work. Suggestion S1 remains deferred. Existing publications retain their prior identities and are not repaired or reinterpreted by this patch.
