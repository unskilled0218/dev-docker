# Implemented

- [Implemented](#implemented)
  - [Changes](#changes)
  - [Verification](#verification)
  - [Limits](#limits)

## Changes

- Branch: `16-copy-user-config-into-image`. Version: `0.1.24`.
- Capture SSH files, Git config, and the complete token directory in private build contexts. Add source overrides, bounded no-follow reads, owner-only permissions, and existing temporary-file cleanup.
- Copy files into `/home/container` after setup. npm inherits them. Remove their Compose mounts and the unused BuildKit token mount/argument.
- Include a combined fingerprint in image labels and release identity. Reject changed inputs during publication checks and completed retries; keep publication authentication separate.
- Filter captured secret lines and source paths from build output. Update README, release notes, and relevant documentation.
- Add 17 tests using fake credentials and isolated home directories. Update existing context, Dockerfile, Compose, and browser-client assertions.

## Verification

- `TMPDIR=/tmp/opencode python3 -B -m unittest discover -s tests -v`: 165 tests, 164 passed, one existing failure. All 17 new tests passed. The completed run took 625 seconds; an earlier five-minute run timed out.
- Existing failure: `test_excluded_images_remain_manual_and_do_not_block_either_mode` expects missing manual Dockerfiles, beginning with `Dockerfile/android.Dockerfile`. Reproduced the same failure using an isolated archive of unchanged commit `ca9ba84`. Left unrelated files and tests unchanged.
- `bash -n build-all.sh`: passed.
- `bash build-all.sh --validate`: passed without reading personal inputs or contacting services.
- `git diff --check`: passed.

## Limits

No real credentials, native image builds, registry login, or publication were used. Actual Docker copy behavior and service connectivity remain unverified. Images, caches, and backups intentionally retain extractable keys and tokens. Rotation requires rebuilding, recreating containers, and revoking obsolete credentials.
