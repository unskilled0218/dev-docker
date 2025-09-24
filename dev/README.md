# SSH server inside docker

ssh to docker

## docker

1. Change `password`
2. Build image

```bash
docker build -t my-dev-image .
```

3. Run container

```bash
docker run -itd -p 322:22 my-dev-image
```

## SSH

1. ssh-copy-id

```bash
ssh-copy-id -p 322 root@localhost
```

2. SSH

```bash
ssh root@localhost -p 322
```
