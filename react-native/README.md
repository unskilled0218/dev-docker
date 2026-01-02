# React Native

## Build image

### Root

```bash
docker build -t react-native-dev -f react-native/Dockerfile .
```

### Non root

```bash
docker build -t rn-non-root-dev -f react-native/nonroot.Dockerfile .
```

## Run

### Root

```bash
docker run -itd --net=host --add-host=host.docker.internal:host-gateway react-native-dev
```

### Non root

```bash
docker run -itd --net=host --add-host=host.docker.internal:host-gateway rn-non-root-dev
```

## Run android on linux

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
