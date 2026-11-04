# dev docker

- [dev docker](#dev-docker)
  - [Notes](#notes)
    - [Android](#android)
    - [Tauri](#tauri)
    - [RN run android on linux](#rn-run-android-on-linux)

```bash
bash build-all.sh --validate
bash build-all.sh --build-only
bash build-all.sh
```

Builds only the AMD64 `base` and `npm` development images. `bash build-all.sh` publishes version and `latest` tags from clean, pushed `main` and links both packages to this repository. Android, Tauri, and Switchboard Dockerfiles remain for manual use. See [image releases](docs/image-releases.md) for settings, package visibility, credentials, recovery, and verification limits, including [release error guidance](docs/image-releases.md#http-error-diagnostics).

First publication creates missing packages after verifying authenticated owner inventory; no prior local build or manual package creation is needed.

Builds require `git.lanCA.crt`, `ntfy.lanCA.crt`, and `penpot.lanCA.crt`. See [certificate inputs and trust](docs/image-releases.md#credentials-and-trust) for default paths and overrides.

Git and Penpot use `~/.config/token/git` and `~/.config/token/penpot` through one read-only Compose mount. Base and npm images include Penpot MCP defaults. See [setup and token migration](docs/penpot-mcp.md).

The base image installs Docker from the repository's `scripts/install-docker.sh` before switching users. Validation requires this local installer to be a regular, non-symlinked file and rejects invalid paths before external operations. See [Docker installation](docs/image-releases.md#docker-installation) for build inputs and cleanup.

Both build modes show filtered Docker build logs and phase progress on stderr. See [build logs](docs/image-releases.md#build-logs) for privacy and output limits.

Run browsers in the separate official Playwright service and connect client containers over the shared `development` network. See [remote Playwright setup](docs/playwright.md) for startup order, client versions, and independent clients. The npm image no longer installs local browsers. The base image no longer starts an OpenCode server or sets its default server password.

## Notes

### Android

- https://twosixtech.com/blog/integrating-docker-and-adb/

**Need to run before run container**

```bash
adb kill-server && adb -a nodaemon server start &> /dev/null &
```

### Tauri

```bash
xhost +local:docker
```

### RN run android on linux

1. Edit package.json

```json
{
	"scripts": {
		...

		"android-linux": "react-native bundle --platform android --dev false --entry-file index.js --bundle-output android/app/src/main/assets/index.android.bundle --assets-dest android/app/src/main/res && react-native run-android",

		...
	}
}
```

2. Run command

```bash
npm run anroid-linux
```
