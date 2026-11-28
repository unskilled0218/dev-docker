# Release alignment implementation

- [Release alignment implementation](#release-alignment-implementation)
  - [Verification](#verification)

The executable `scripts/release.sh` delegates to the existing two-image workflow. Version 0.1.26 uses plain versions for both image aliases, the Git tag, Gitea release, and notes. Existing v-prefixed history remains readable; same-version legacy tags and releases block writes.

## Verification

Both entry points passed offline validation. Both Bash files passed syntax checks. Six focused tests passed, covering validation and inventory, CLI refusals, local parent selection, release-history conflicts, publication, and read-only retry. Publication tests used fake services. No native image build or live publication ran.
