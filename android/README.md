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
docker run -itd --add-host=host.docker.internal:host-gateway android-dev
```

### Non root

```bash
docker run -itd --add-host=host.docker.internal:host-gateway android-non-root-dev
```
