# Android emulator on Ubuntu Server

The standalone `android` Compose service runs the headless emulator. Dev containers connect with ADB, and laptops can use scrcpy to see the screen and interact with apps. This setup works for client UI tests and simulated calls or SMS. Use a physical SIM phone for carrier and wired call-audio tests.

- [Android emulator on Ubuntu Server](#android-emulator-on-ubuntu-server)
  - [Enable KVM on the Ubuntu host](#enable-kvm-on-the-ubuntu-host)
  - [Start the standalone Compose VM](#start-the-standalone-compose-vm)
  - [Use the same Android device from multiple containers](#use-the-same-android-device-from-multiple-containers)
  - [Control Android from your laptop](#control-android-from-your-laptop)

## Enable KVM on the Ubuntu host

Run `ls -l /dev/kvm` on the x86_64 Ubuntu host. If the device is missing, check hardware virtualization and the host KVM module. If Ubuntu runs inside a VM, enable nested virtualization on the outer host first. The Compose service already maps `/dev/kvm` and uses `KVM_GID` for access.

## Start the standalone Compose VM

On an x86_64 Linux Docker host with `/dev/kvm`, run these commands from the repository root. Use Docker Compose 2.17 or later. The build downloads Google's SDK tools and API 36 system image and accepts the Android SDK licenses. Review [the license terms](https://developer.android.com/studio/terms) before building.

The image and Compose service run the emulator as UID 1000 and primary GID 1000. Compose adds the supplementary `KVM_GID` for KVM access. If reusing an existing `android-data` volume, ensure UID 1000 can write its contents.

```sh
export KVM_GID=$(stat -c %g /dev/kvm)
export COMPOSE_FILE=compose/android.yml
docker compose up -d --build --wait --wait-timeout 360
docker compose exec android id
docker compose exec android adb devices
```

Expect `id` to report UID 1000 and primary GID 1000. Expect `emulator-5554` with status `device`. Keep host loopback ports 5037, 5554, and 5555 free before startup. Compose creates the virtual device on first start and reuses it on later starts. Stop with `docker compose down` in the same shell. The named volume retains apps and device data.

## Use the same Android device from multiple containers

Keep the emulator and its ADB server running in one owner container. Only the owner needs `/dev/kvm` and the AVD volume. Other containers use ADB clients to control the same running device.

For this Ubuntu setup, use `network_mode: host` on the owner and each trusted client service. They then share host loopback. Once `adb devices` lists `emulator-5554` in the owner, run these commands in each client with the same Android platform-tools version:

```sh
export ADB_SERVER_SOCKET=tcp:127.0.0.1:5037
adb devices
adb -s emulator-5554 shell getprop sys.boot_completed
```

Expect `emulator-5554` with status `device` and a boot result of `1`. Port 5037 belongs to the shared ADB server; do not publish it or run `adb kill-server` from a client. A bridge-networked container has its own loopback, so this address will not reach the owner there.

All clients share one screen, installed apps, and app data. Run UI tests one at a time. Stopping the owner disconnects every client.

## Control Android from your laptop

Install `adb` and `scrcpy` on the laptop. The `android` service uses host networking, so SSH on the Ubuntu host can reach the emulator's ADB port (5555). In one laptop terminal, replace `user@ubuntu-server` with your SSH login and keep the tunnel open:

```sh
ssh -N -o ExitOnForwardFailure=yes -L 127.0.0.1:15555:127.0.0.1:5555 user@ubuntu-server
```

In a second laptop terminal, connect and open the interactive window:

```sh
adb connect 127.0.0.1:15555
scrcpy -s 127.0.0.1:15555
```

If Android asks to authorize the laptop before scrcpy can connect, use the `android` service's authorized ADB connection to approve the prompt. Close scrcpy when finished, run `adb disconnect 127.0.0.1:15555` on the laptop, then stop the SSH tunnel with `Ctrl+C`.
