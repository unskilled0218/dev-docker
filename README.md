# dev docker

- https://twosixtech.com/blog/integrating-docker-and-adb/
- https://code.visualstudio.com/remote/advancedcontainers/add-nonroot-user

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
