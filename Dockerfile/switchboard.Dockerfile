FROM android-dev:latest

ARG ANDROID_COMMAND_LINE_TOOLS_VERSION=11076708
ARG ANDROID_NDK_VERSION=28.0.13004108
ARG FLUTTER_VERSION=3.29.3

ENV FLUTTER_HOME=/opt/flutter
ENV JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
ENV CARGO_TARGET_AARCH64_UNKNOWN_LINUX_GNU_LINKER=aarch64-linux-gnu-gcc
ENV PATH=${FLUTTER_HOME}/bin:${ANDROID_HOME}/cmdline-tools/latest/bin:${ANDROID_HOME}/platform-tools:${PATH}

USER root

RUN apt update &&\
  apt install -y \
  gcc-aarch64-linux-gnu clang cmake ninja-build pkg-config unzip wget xz-utils zip \
  libasound2-dev libgtk-3-dev liblzma-dev libsecret-1-dev libsqlite3-dev libglu1-mesa &&\
  rm -rf /var/lib/apt/lists/* &&\
  mkdir -p ${ANDROID_HOME}/cmdline-tools &&\
  wget -q -O /tmp/android-tools.zip "https://dl.google.com/android/repository/commandlinetools-linux-${ANDROID_COMMAND_LINE_TOOLS_VERSION}_latest.zip" &&\
  unzip -q /tmp/android-tools.zip -d ${ANDROID_HOME}/cmdline-tools &&\
  mv ${ANDROID_HOME}/cmdline-tools/cmdline-tools ${ANDROID_HOME}/cmdline-tools/latest &&\
  rm /tmp/android-tools.zip &&\
  yes | sdkmanager --licenses > /dev/null &&\
  sdkmanager "platform-tools" "platforms;android-36" "build-tools;36.0.0" "ndk;${ANDROID_NDK_VERSION}" &&\
  rustup target add aarch64-linux-android aarch64-unknown-linux-gnu &&\
  git clone --depth 1 --branch ${FLUTTER_VERSION} https://github.com/flutter/flutter.git ${FLUTTER_HOME} &&\
  chown -R ${USER_NAME}:${USER_NAME} ${FLUTTER_HOME}

WORKDIR /home/${GROUP_NAME}/workdir/switchboard

USER ${USER_NAME}

RUN flutter config --enable-android --enable-linux-desktop

CMD ["bash"]
