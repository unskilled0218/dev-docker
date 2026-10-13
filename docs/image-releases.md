# Image releases

Run `bash build-all.sh` to build all images and push the `latest` tag. Run `bash build-all.sh v1.0.0` to publish a specific tag. Run `bash build-all.sh --build-only` to build without logging in or pushing. The script works from any working directory.

The Git origin remote supplies the Forgejo registry host, package owner, and repository. With `ssh://git@git.lan/dev/dev-docker.git`, images are `git.lan/dev/my-base:latest`, `git.lan/dev/npm-non-root:latest`, `git.lan/dev/android-dev:latest`, and `git.lan/dev/tauri-dev:latest`. OCI source labels let Forgejo link new packages to the repository. Existing packages may need manual linking in Forgejo's package settings.

The login username defaults to the remote owner. For an organization-owned repository, set `FORGEJO_USERNAME` to your account name. The token defaults to `~/.config/forgejo/forgejo-token`; override it with `FORGEJO_TOKEN_FILE`. The account needs package write access. Docker receives the token through standard input and stores login credentials only in a temporary directory removed on exit.

Docker with BuildKit and a reachable Docker daemon are required. The existing certificate at `/usr/local/share/ca-certificates/git.lanCA.crt` remains a build input for the base image; use `BUILD_CERT_FILE` if it lives elsewhere. The script does not install certificates or disable TLS verification.

Images build in dependency order: base, npm, Android, and Tauri. Local `latest` tags remain available for existing Dockerfiles and Compose, even when publishing a version tag. All builds must succeed before any image is pushed. A failed push stops the release, but already pushed images remain published.

The base setup uses a BuildKit secret instead of copying the Forgejo token into an image layer. Build-only mode still needs the token for that setup. Previously built images may contain the old copied token; revoke that token if those images were shared. Do not add credentials to Dockerfiles or setup script output. Manual base builds also need `--secret id=forgejo-token,src="$HOME/.config/forgejo/forgejo-token"` and the existing certificate in their build context; prefer `build-all.sh --build-only`.

Run `python3 -B -m unittest discover -s tests -v` for mocked script tests. These tests do not build images or contact Forgejo.
