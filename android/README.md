# Android

## Build image

```bash
docker build -t android-dev -f android/Dockerfile .
```

## Run

```bash
docker run -itd --add-host=host.docker.internal:host-gateway android-dev
```
