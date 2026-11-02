[command](#command) | [goal](#goal)

## command

fix warning from previous code review

## goal

Fix the required-input validation warning from tasks/11-use-local-docker-installer/5-code-review.md: make `bash build-all.sh --validate` reject missing or symlinked scripts/install-docker.sh before credentials, Docker, or network operations. Add regression coverage while preserving selected-commit installer sourcing for publication.
