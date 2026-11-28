# Release alignment plan

- [Release alignment plan](#release-alignment-plan)
  - [Implementation](#implementation)

## Implementation

1. Expose `./scripts/release.sh` for validation and publication. Delegate to the existing two-image engine and retain its local build mode, AMD64 target, private inputs, package checks, and recovery rules.
2. Use root `VERSION` verbatim for Git, Gitea, release notes, and version image aliases. Keep immutable parent selection and `latest` promotion for both images.
3. Accept older v-prefixed release history during inventory. Reject a newer release under either naming scheme and do not migrate old records.
4. Update fixtures, documentation, and version metadata. Check offline validation, fresh publication through fake ports, both image aliases, and read-only retry.
