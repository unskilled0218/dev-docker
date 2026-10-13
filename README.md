# dev docker

- https://twosixtech.com/blog/integrating-docker-and-adb/
- https://code.visualstudio.com/remote/advancedcontainers/add-nonroot-user

*Build base first. Images are based on base*

```bash
bash build-all.sh
```

## Bulid image and run

- [base](#base)
- [npm](#npm)
- [Android](#android)
- [tauri](#tauri)

### base

```bash
docker build -t my-base:latest -f Dockerfile/base.Dockerfile .
```

### npm

```bash
docker build -t npm-non-root -f Dockerfile/npm.Dockerfile .
```

### Android

```bash
docker build -t android-dev -f Dockerfile/android.Dockerfile .
```

### tauri

```bash
docker build -t tauri-dev -f Dockerfile/tauri.Dockerfile .
```

## Notes

### Android

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
