# Android dev docker

https://twosixtech.com/blog/integrating-docker-and-adb/

**Need to run before run container**

```bash
adb kill-server && adb -a nodaemon server start &> /dev/null &
```

## Command line

### Build image

```bash
docker build -t my-dev-image -f dev/Dockerfile .
```

```bash
docker build -t android-dev-image -f android/Dockerfile .
```

```bash
docker build -t react-native-dev-image -f react-native/Dockerfile .
```

```bash
docker build -t tauri-dev-image -f tauri/Dockerfile .
```

### Run

```bash
docker run -it --add-host=host.docker.internal:host-gateway android-dev-image
```

```bash
docker run -it --net=host --add-host=host.docker.internal:host-gateway react-native-dev-image
```

```bash
docker run -it --privileged --ipc=host --net=host --add-host=host.docker.internal:host-gateway --env DISPLAY=$DISPLAY -v /run/user/1000/at-spi/bus_1:/run/user/1000/at-spi/bus_1 tauri-dev-image:latest
```

```bash
docker compose run app bash
```

Can't use `-p` option with `--network=host`

* WARNING: Published ports are discarded when using host network mode

#### RN

1. Edit package.json

```json
"android-linux": "react-native bundle --platform android --dev false --entry-file index.js --bundle-output android/app/src/main/assets/index.android.bundle --assets-dest android/app/src/main/res && react-native run-android"
```

2. Run command

```bash
npm run anroid-linux
```
