# dev docker

- https://twosixtech.com/blog/integrating-docker-and-adb/
- https://code.visualstudio.com/remote/advancedcontainers/add-nonroot-user

## Bulid image and run

- [python](#python)
- [python-node](#python-node)
- [Rust](#rust)
- [Rust node](#rust-node)
- [npm](#npm)
- [Android](#android)
- [React Native](#react-native)
- [tauri](#tauri)

### Python

```bash
docker build -t python-non-root:3.12 -f Dockerfile/python.Dockerfile .
```

### Python node

```bash
docker build -t python-node-non-root:3.12 -f Dockerfile/python-node.Dockerfile .
```

### Rust

```bash
docker build -t rust-non-root:1.96 -f Dockerfile/rust.Dockerfile .
```

### Rust node

```bash
docker build -t rust-node-non-root:1.96 -f Dockerfile/rust-node.Dockerfile .
```

### npm

```bash
docker build -t npm-non-root -f Dockerfile/npm.Dockerfile .
```

### Android

```bash
docker build -t android-dev -f Dockerfile/android.Dockerfile .
```

### React Native

```bash
docker build -t rn-dev -f Dockerfile/react-native.Dockerfile .
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
