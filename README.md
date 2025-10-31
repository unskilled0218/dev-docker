# dev docker

https://twosixtech.com/blog/integrating-docker-and-adb/

**Need to run before run container**

```bash
adb kill-server && adb -a nodaemon server start &> /dev/null &
```

## Command line

### Build image

```bash
docker build -t android-dev -f android/Dockerfile .
```

```bash
docker build -t react-native-dev -f react-native/Dockerfile .

# or

docker build -t rn-non-root-dev -f react-native/nonroot.Dockerfile .
```

```bash
docker build -t tauri-dev-image -f tauri/Dockerfile .
```

### Run

```bash
docker run -itd --add-host=host.docker.internal:host-gateway android-dev-image
```

```bash
docker run -itd --net=host --add-host=host.docker.internal:host-gateway react-native-dev-image

# or

docker run -itd --net=host --add-host=host.docker.internal:host-gateway rn-non-root-image
```

```bash
docker run -itd --privileged --ipc=host --net=host --add-host=host.docker.internal:host-gateway --env DISPLAY=$DISPLAY -v /run/user/1000/at-spi/bus_1:/run/user/1000/at-spi/bus_1 tauri-dev-image:latest
```

```bash
docker compose run app bash
```

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
