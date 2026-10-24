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
