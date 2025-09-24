FROM rust:latest

ENV DEBIAN_FRONTEND=noninteractive
ENV ANDROID_ADB_SERVER_ADDRESS=host.docker.internal
ENV ANDROID_HOME=/root/Android/Sdk
ENV NDK_HOME=${ANDROID_HOME}/ndk/21.3.6528147
ENV PATH="$PATH:$ANDROID_HOME/platform-tools:$ANDROID_HOME/cmdline-tools/latest/bin"
ENV WEBKIT_DISABLE_COMPOSITING_MODE=1

EXPOSE 1420

RUN apt-get update &&\
  apt-get install -y vim openjdk-17-jdk libwebkit2gtk-4.1-dev build-essential libxdo-dev libssl-dev libayatana-appindicator3-dev librsvg2-dev libcanberra-gtk-module libcanberra-gtk3-module &&\
  # Setting up android dev
  mkdir -p /root/Android/Sdk/cmdline-tools &&\
  wget https://dl.google.com/android/repository/commandlinetools-linux-13114758_latest.zip &&\
  unzip commandlinetools-linux-13114758_latest.zip -d /root/Android/Sdk/cmdline-tools/ &&\
  rm commandlinetools-linux-13114758_latest.zip &&\
  mv /root/Android/Sdk/cmdline-tools/cmdline-tools /root/Android/Sdk/cmdline-tools/latest &&\
  yes | /root/Android/Sdk/cmdline-tools/latest/bin/sdkmanager --licenses &&\
  yes | /root/Android/Sdk/cmdline-tools/latest/bin/sdkmanager --install "platform-tools" "platforms;android-35" "build-tools;35.0.0" "ndk;21.3.6528147" "cmake;3.18.1" &&\
  # Install Node.js 24
  curl -o- https://fnm.vercel.app/install | bash &&\
  . /root/.bashrc &&\
  fnm install 24

RUN rustup target add x86_64-unknown-linux-gnu

WORKDIR /root/workdir
