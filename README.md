# dev docker

- https://twosixtech.com/blog/integrating-docker-and-adb/
- https://code.visualstudio.com/remote/advancedcontainers/add-nonroot-user

- [android](./android)
- [react native](./react-native)
- [tauri](./tauri)

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

## To Do

- [] Can't build AppImage +tauri
	- permission problem, Root can build AppImage, Non root user can't build AppImage.
