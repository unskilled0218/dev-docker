# dev docker

https://twosixtech.com/blog/integrating-docker-and-adb/

**Need to run before run container**

```bash
adb kill-server && adb -a nodaemon server start &> /dev/null &
```

## Command line

### Build image

#### Android

```bash
docker build -t android-dev -f android/Dockerfile .
```

#### React Native

```bash
docker build -t react-native-dev -f react-native/Dockerfile .
```

#### React Native non root

```bash
docker build -t rn-non-root-dev -f react-native/nonroot.Dockerfile .
```

#### Tauri

```bash
docker build -t tauri-dev -f tauri/Dockerfile .
```

#### Tauri non root

```bash
docker build -t tauri-non-root-dev -f tauri/nonroot.Dockerfile .
```

### Run

#### Android

```bash
docker run -itd --add-host=host.docker.internal:host-gateway android-dev
```

#### React Native

```bash
docker run -itd --net=host --add-host=host.docker.internal:host-gateway react-native-dev
```

#### React Native non root

```bash
docker run -itd --net=host --add-host=host.docker.internal:host-gateway rn-non-root-dev
```

#### Tauri

```bash
docker run -itd --privileged --ipc=host --net=host --add-host=host.docker.internal:host-gateway --env DISPLAY=$DISPLAY -v /run/user/1000/at-spi/bus_1:/run/user/1000/at-spi/bus_1 tauri-dev:latest
```

#### Tauri non root

```bash
docker run -itd --privileged --ipc=host --net=host --add-host=host.docker.internal:host-gateway --env DISPLAY=$DISPLAY -v /run/user/1000/at-spi/bus_1:/run/user/1000/at-spi/bus_1 --user 1000:1000 --volume=/path/to/workdir/:/home/tauri/workdir/ tauri-non-root-dev:latest
```

#### Tauri docker compose

```bash
docker compose -f tauri/root.yml up -d
docker compose -f tauri/nonroot.yml up -d

docker compose run app bash
```

## docker ports and network options

Can't use `-p` option with `--network=host`

* WARNING: Published ports are discarded when using host network mode

#### RN

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
