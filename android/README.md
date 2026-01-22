# Android

## Build image

### Root

```bash
docker build -t android-dev -f android/Dockerfile .
```

### non root

```bash
docker build -t android-non-root-dev -f android/nonroot.Dockerfile .
```

## Run

### Root

```bash
docker run -itd -p 5037:5037 --device=/dev/bus/usb --volume=/dev/bus/usb:/dev/bus/usb android-dev
```

### Non root

```bash
docker run -itd -p 5037:5037 --device=/dev/bus/usb --volume=/dev/bus/usb:/dev/bus/usb android-non-root-dev
```
