# tauri

## Build image

### Root

```bash
docker build -t tauri-dev -f tauri/Dockerfile .
```

### Non root

```bash
docker build -t tauri-non-root-dev -f tauri/nonroot.Dockerfile .
```

## Run

### Root

```bash
docker run -itd --privileged --ipc=host --net=host --add-host=host.docker.internal:host-gateway --env DISPLAY=$DISPLAY --volume=/run/user/1000/at-spi/bus:/run/user/1000/at-spi/bus --volume=/home/user/.Xauthority:/root/.Xauthority tauri-dev:latest
```

#### docker compose

```bash
docker compose -f tauri/root.yml up -d
```

### Non root

```bash
docker run -itd --privileged --ipc=host --net=host --add-host=host.docker.internal:host-gateway --env DISPLAY=$DISPLAY --volume=/run/user/1000/at-spi/bus:/run/user/1000/at-spi/bus --volume=/path/to/workdir:/home/node/workdir --volume=/home/user/.Xauthority:/home/node/.Xauthority tauri-non-root-dev:latest
```

#### docker compose

```bash
docker compose -f tauri/nonroot.yml up -d
```
