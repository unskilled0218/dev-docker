# plan

- [plan](#plan)
  - [Scope](#scope)
  - [Implementation plan](#implementation-plan)
    - [1. Capture private build inputs](#1-capture-private-build-inputs)
    - [2. Bind inputs to release identity](#2-bind-inputs-to-release-identity)
    - [3. Copy files into the base image](#3-copy-files-into-the-base-image)
    - [4. Remove runtime mounts and update documentation](#4-remove-runtime-mounts-and-update-documentation)
    - [5. Verify with synthetic inputs](#5-verify-with-synthetic-inputs)
  - [Acceptance criteria](#acceptance-criteria)
  - [Risks and decisions](#risks-and-decisions)

## Scope

Bake the build user's `~/.ssh`, `~/.gitconfig`, and `~/.config/token` into base and inherited npm images, using the existing private-context workflow. Replace their three Compose bind mounts. Preserve certificate trust, the two-image graph, independent publication authentication, and release safeguards. Do not add prompts, modify host credentials, publish images, or change unrelated toolchains.

## Implementation plan

### 1. Capture private build inputs

- In `scripts/release_data.py`, define three input mappings: `~/.ssh` to `user-config/ssh`, `~/.gitconfig` to `user-config/gitconfig`, and `~/.config/token` to `user-config/token`. Support nonempty `BUILD_SSH_DIR`, `BUILD_GITCONFIG_FILE`, and `BUILD_TOKEN_DIR` overrides for alternate sources and isolated tests. Empty overrides use defaults; expand `~` and resolve relative overrides from the caller's working directory, like certificates. No release configuration schema changes are needed for these defaults.
- Capture these inputs during `init()`, before builder operations, credential loading, or remote writes. Require both directories and the Git config file; allow empty directories and an empty Git config. Copy complete directory trees, including hidden files, without reading unrelated home files. Missing or unreadable inputs must stop with a sanitized input-category diagnostic, not source paths, child names, or contents.
- Keep sources outside the repository. Refuse symlinked inputs or descendants, special files such as SSH agent sockets, and traversal outside the selected roots. Use descriptor-based no-follow reads and regular-file checks rather than following links during recursive copying. Bound each file to 1 MiB, the combined capture to 16 MiB, entries to 1,024, and nesting to 16 levels; refuse excess before building.
- Store captured files only beneath the existing mode-0700 run directory. Normalize captured directories to 0700 and files to 0600, retaining owner execute permission only when present on source helper files. Never change host permissions. Capture a deterministic private manifest of relative paths, entry types, normalized modes, and content digests.
- Extend `snapshot()` to populate `context/user-config` from captured bytes, not from a fresh home-directory read. Local and publication modes use identical captured personal inputs; Dockerfiles and repository helpers retain their existing working-tree versus committed-blob rules. Existing EXIT/INT/TERM cleanup removes the new run-owned copies too. Keep `--validate` independent of home files, credentials, temporary directories, Docker, and network access.

### 2. Bind inputs to release identity

- Compute one SHA-256 fingerprint of the canonical private manifest, including empty directories and normalized permissions. Keep individual names, hashes, and contents private; expose only the aggregate fingerprint.
- Add the aggregate to `base_identity()` and `labels_for()`, using identity field `user_config` and label `dev.docker.release.user-config`. This must influence staging names and verification for both base and npm, including inherited-parent checks and completed retries.
- Extend `unchanged()` to recapture and compare source fingerprints before publication mutations. Additions, removals, content changes, or relevant permission changes must refuse continuation; builds still use the original captured files. Reuse the bounded capture logic without overwriting the original snapshot.
- Preserve strict tag/label checks and do not adopt old staging images or rewrite historical tags/releases. Use a new release version when implementing. A completed retry after changing personal inputs must refuse rather than claim the old release matches.
- Keep release authentication precedence unchanged: `GIT_TOKEN`, `FORGEJO_TOKEN_FILE`, and configured `token_file` still select the host credential used for APIs and registry login. These overrides do not silently replace the baked token directory or its `git` file.
- Extend `build_logs()` and existing filtering tests for captured token values, SSH private-key payload lines, and configured source paths. Normalize multiline values into record-safe matching values before constructing `RecordFilter`. Do not dump files, manifests, or copied credentials in build instructions or diagnostics. Retain the documented limitation that arbitrary encodings and secrets embedded in arbitrary Git configuration cannot be universally detected.

### 3. Copy files into the base image

- In `Dockerfile/base.Dockerfile`, add `COPY --chown=1000:1000` instructions from the three `user-config` inputs to `/home/container/.ssh`, `/home/container/.gitconfig`, and `/home/container/.config/token`.
- Put these copies after downloaded setup and Penpot configuration, keeping private inputs unavailable to those setup steps. Preserve normalized private permissions and leave the final user as `container`. Verify Docker's directory-copy semantics retain empty roots and intended modes; explicitly set destination root modes if necessary.
- Remove the final no-op BuildKit token mount, which currently only creates a directory. Remove its corresponding base `--secret` argument from `build_args()`; retain private release credential files for authentication and log filtering. Builds still need the independently selected Git token under the existing release-script contract.
- Keep Penpot's literal runtime file reference unchanged; it will read the baked `penpot` file. Do not require or validate particular files inside the copied token directory beyond existing publication credential checks. Missing application-specific tokens remain runtime configuration errors.
- npm inherits these files from the verified base parent. Do not add duplicate host copies or modify npm's toolchain. Manual base builds must supply the same context layout and private permissions.

### 4. Remove runtime mounts and update documentation

- Remove only the `.ssh`, `.gitconfig`, and `.config/token` bind mounts from `compose/docker-compose.yml`. Preserve workspace and Docker socket mounts, networking, image selection, and other service settings.
- Update `README.md`, `docs/image-releases.md`, and `docs/penpot-mcp.md` to describe required inputs, overrides, copy destinations, permissions, limits, manual context layout, and the removed BuildKit secret requirement. Replace claims that credentials never enter contexts/images or that Penpot keys are runtime-only. Keep README short and maintain tables of contents.
- Explain that images, inherited images, build caches, registry storage, and backups contain recoverable secrets. Private Gitea hosting does not encrypt image contents or prevent extraction by authorized readers. Rotation requires rebuilding with a new version and recreating containers; revoke compromised or obsolete credentials because old images retain them. Host Git includes and absolute SSH/token references are copied literally, not rewritten or expanded into additional files.
- Explain that all files inside the selected directories are included, not just Git and Penpot tokens. Document refusal of symlinks and SSH agent sockets, optional user-managed runtime overrides, and unchanged host authentication precedence.
- During implementation, update `VERSION`, the configured release-notes path, and matching release notes together according to the implementation workflow. Do not edit historical release notes or `todo.md`.

### 5. Verify with synthetic inputs

- Extend `ReleaseFixture` in `tests/test_build_all.py` with private synthetic SSH/config/token trees outside the fixture repository and explicit input overrides. Ensure all derived suites inherit those overrides and never inspect the developer's real home secrets. Update `tests/fake_release_ports.py` to assert the exact new context layout, expected synthetic bytes/modes, and absence of the obsolete `--secret` argument.
- Add tests for nested and hidden files, empty roots, spaces in paths, override/default/empty-override resolution using an isolated HOME, and separation between baked tokens and publication-token overrides. Assert snapshots use captured bytes even after source changes.
- Cover missing/unreadable inputs, symlinked roots and children, repository-contained paths, sockets/FIFOs, per-file/total/count/depth bounds, and sanitized errors. Verify failures happen before builder or publication effects, host files remain unchanged, and run-owned temporary files are cleaned after success, failure, and supported interruption paths.
- Test fingerprint sensitivity to additions, deletions, renamed files, content, and normalized executable modes; irrelevant source group/other modes must not change the normalized identity. Verify changed inputs reject publication guards, stale staging reuse, and completed-release retries without writes. Preserve successful unchanged retries and the existing two-image release contracts.
- Update Dockerfile/Compose assertions in `tests/test_penpot_mcp.py` for late copies, ownership, retained Penpot file interpolation, removed mount/secret assumptions, and preservation of unrelated configuration. Add static permission checks and synthetic log-redaction tests without printing fixtures' secrets.
- Run `python3 -B -m unittest discover -s tests -v`, `bash -n build-all.sh`, and `bash build-all.sh --validate`. Report any unrelated baseline failures separately. Do not run real builds, read real credentials, contact services, log in, or publish during implementation verification.
- If separately authorized later, build with disposable synthetic inputs and unique local image tags, then verify file presence, bytes, UID/GID, modes, and npm inheritance using boolean checks without displaying contents. Offline tests alone cannot certify native Docker copy behavior or actual SSH/Git/Penpot connectivity.

## Acceptance criteria

- Both build modes capture all three requested host paths into private temporary contexts and copy them to the corresponding container-user paths. npm inherits them from base.
- Files have UID/GID 1000:1000 and owner-only access; copied SSH helper executability is retained. Host inputs remain untouched and absent from tracked Git files and displayed logs.
- The three personal-config Compose mounts and obsolete BuildKit token mount/argument are removed; unrelated mounts and authentication safeguards remain intact.
- Changed personal inputs alter release identity and cannot silently reuse stale image evidence. Unchanged retries preserve current verification-only behavior.
- Validation remains offline and independent of personal inputs. Synthetic tests pass, or unrelated baseline failures are explicitly recorded. Documentation explains extractable credentials and rebuild/revocation requirements.

## Risks and decisions

- Baking private keys and tokens is the requested behavior, not secret protection. Private registry access controls and cache/backup access become part of credential security. No prompt or alternate runtime-secret architecture is added.
- Directory capture intentionally includes every regular file and subdirectory, with explicit bounds and link/special-file refusals. External includes, symlinked credential stores, agent sockets, and absolute host paths need user preparation rather than automatic resolution.
- Copying inputs late reduces setup-step exposure but does not isolate credentials from subsequent npm build commands or runtime processes. Never claim universal log redaction or protection from a malicious builder.
- Aggregate fingerprints are metadata, not encryption. Secret contents and per-file manifests must not appear in labels, tags, release notes, or Git.
- Source trees can change during capture; descriptor checks, captured-byte snapshots, and publication rechecks reduce inconsistency but do not provide an atomic filesystem snapshot. Keep selected inputs stable during builds and publication.
- Existing releases are immutable. Changed tooling and personal inputs require a new version; credential rotation does not update previously published images or revoke credentials automatically.
