# dev docker

- https://twosixtech.com/blog/integrating-docker-and-adb/
- https://code.visualstudio.com/remote/advancedcontainers/add-nonroot-user

## Bulid image and run

- [python](#python)
- [Rust](#rust)
- [npm](#npm)
- [Android](#android)
- [React Native](#react-native)
- [tauri](#tauri)

### Python

```bash
docker build -t python-non-root:3.12 -f Dockerfile/python.Dockerfile .
```

### Rust

```bash
docker build -t rust-non-root:1.96 -f Dockerfile/rust.Dockerfile .
```

### npm

```bash
docker build -t npm -f Dockerfile/npm.Dockerfile .
```

### Android

#### Build image

```bash
docker build -t android-dev -f Dockerfile/android.Dockerfile .
```

#### Run

```bash
docker run \
-itd \
-p 5037:5037 \
--device=/dev/bus/usb \
--volume=/dev/bus/usb:/dev/bus/usb \
android-dev
```

### React Native

#### Build image

```bash
docker build -t rn-dev -f Dockerfile/react-native.Dockerfile .
```

#### Run

```bash
docker run \
-itd \
--net=host \
--add-host=host.docker.internal:host-gateway \
rn-dev
```

### tauri

#### Build image

```bash
docker build -t tauri-dev -f Dockerfile/tauri.Dockerfile .
```

#### Run

```bash
docker run \
-itd \
--privileged \
--ipc=host \
--net=host \
--add-host=host.docker.internal:host-gateway \
--env DISPLAY=$DISPLAY \
--device=/dev/bus/usb \
--volume=/dev/bus/usb:/dev/bus/usb \
--volume=/run/user/1000/at-spi/bus:/run/user/1000/at-spi/bus \
--volume=/home/$(whoami)/.Xauthority:/home/ubuntu/.Xauthority \
--volume=./:/home/ubuntu/workdir \
tauri-dev:latest
```

```bash
docker compose -f tauri-compose.yml up -d
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

## To Do

- [x] Add support for andorid build +tauri
- [x] Can't build AppImage +tauri
	- permission problem, Root can build AppImage, Non root user can't build AppImage.
	- ```apt install file```
