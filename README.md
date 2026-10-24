# dev docker

- [dev docker](#dev-docker)
  - [Notes](#notes)
    - [Android](#android)
    - [Tauri](#tauri)
    - [RN run android on linux](#rn-run-android-on-linux)

```bash
bash build-all.sh --validate
bash build-all.sh --build-only
```

Builds five AMD64 development images. `bash build-all.sh` publishes the configured version from clean, pushed `main`. See [image releases](docs/image-releases.md) for settings, credentials, recovery, and the separate native-readiness checklist. Offline verification does not certify live publication.

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
