- [command](#command)
- [goal](#goal)

## command

Fix first-time publication when `base` and `npm` do not exist and `bash build-all.sh` stops with HTTP 404 during startup classification. Verify the Gitea API contract and authenticated owner/repository permissions, preserve publication safeguards, add regression tests, update documentation, and keep sensitive data out of diagnostics.

## goal

Allow `bash build-all.sh` to safely build and publish missing `base` and `npm` packages without a prior local build or manual package creation. Distinguish verified package absence from inaccessible resources without treating arbitrary HTTP 404 responses as absence. Cover first-time publication and inaccessible resources with regression tests and document the supported behavior.
