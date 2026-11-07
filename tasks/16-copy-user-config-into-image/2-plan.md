# plan

- [plan](#plan)
  - [Scope](#scope)
  - [Changes](#changes)
  - [Checks](#checks)
  - [Risks](#risks)

## Scope

Copy `~/.ssh`, `~/.gitconfig`, and `~/.config/token` into base like the certificate files. npm inherits them. Remove their Compose mounts. No prompts or unrelated changes.

## Changes

1. Update `scripts/release_data.py` to capture these paths in the private temporary build context before builder operations. Include nested and hidden files. Allow empty directories and an empty Git config.
2. Support alternate sources through `BUILD_SSH_DIR`, `BUILD_GITCONFIG_FILE`, and `BUILD_TOKEN_DIR`. Empty overrides use the default home paths.
3. Reject missing, unreadable, repository-contained, or symlinked inputs and special files such as agent sockets. Limit files to 1 MiB each, 16 MiB total, 1,024 entries, and 16 directory levels. Never change host files.
4. Build from captured copies. Clean them up with existing temporary files. Use directory mode 0700 and file mode 0600, preserving owner execute permission where needed.
5. Add one combined file fingerprint to release identity and image labels. Recheck inputs before publication writes. Changed files must not reuse old images or pass completed-release checks. Keep publication-token selection unchanged.
6. Add `COPY --chown=1000:1000` in `Dockerfile/base.Dockerfile` after setup and Penpot configuration. Copy into the matching paths under `/home/container`. Keep Penpot's token-file reference unchanged.
7. Remove the unused BuildKit token mount and its `--secret` argument. Remove only the three personal-file mounts from `compose/docker-compose.yml`.
8. Extend log filtering for copied tokens, SSH private-key lines, and source paths. Never print credentials or commit them. Only the combined fingerprint belongs in public metadata.
9. Update `README.md`, `docs/image-releases.md`, and `docs/penpot-mcp.md`. Explain inputs, overrides, permissions, manual builds, and secret risks. Update version and release notes during implementation; preserve historical releases.

## Checks

- Use fake credentials and an isolated home directory. Do not read real secrets or run real builds or publication.
- Test copied contents, permissions, nested/hidden files, empty inputs, overrides, rejected inputs, size limits, and cleanup.
- Test changed-input detection, stale-image refusal, unchanged retries, and log filtering. Update Dockerfile, Compose, and fake-build assertions.
- Keep `--validate` offline and independent of personal files. Preserve certificate handling, publication authentication, and the base/npm build order.
- Run `python3 -B -m unittest discover -s tests -v`, `bash -n build-all.sh`, and `bash build-all.sh --validate`. Report unrelated failures separately. Real image verification requires separate approval.

## Risks

- Anyone with the image can extract its SSH keys and tokens. Private Gitea hosting does not prevent this. Caches and backups may retain them too.
- Copy all files inside the selected directories. Do not resolve external Git includes or rewrite absolute host paths.
- Rotation requires rebuilding and recreating containers. Old images keep old secrets; revoke obsolete credentials.
- Log filtering cannot detect every secret encoding. Later build steps and runtime processes can access copied credentials.
- Keep source files stable during builds. Do not rewrite old tags or releases to match changed inputs.
