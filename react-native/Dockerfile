FROM ubuntu:latest

ENV DEBIAN_FRONTEND=noninteractive
ENV ANDROID_ADB_SERVER_ADDRESS=host.docker.internal
ENV ANDROID_HOME=/root/Android/Sdk
ENV PATH="$PATH:$ANDROID_HOME/platform-tools"

RUN apt-get update &&\
  apt-get install -y git wget vim unzip curl openjdk-17-jdk &&\
  curl -fsSL https://deb.nodesource.com/setup_lts.x | bash - && \
  apt-get install -y nodejs && \
  apt-get clean && rm -rf /var/lib/apt/lists/* &&\
  npm --version && \
  node --version &&\
  mkdir -p /root/Android/Sdk/cmdline-tools &&\
  wget https://dl.google.com/android/repository/commandlinetools-linux-13114758_latest.zip &&\
  unzip commandlinetools-linux-13114758_latest.zip -d /root/Android/Sdk/cmdline-tools/ &&\
  rm commandlinetools-linux-13114758_latest.zip &&\
  mv /root/Android/Sdk/cmdline-tools/cmdline-tools /root/Android/Sdk/cmdline-tools/latest &&\
  yes | /root/Android/Sdk/cmdline-tools/latest/bin/sdkmanager --licenses &&\
  yes | /root/Android/Sdk/cmdline-tools/latest/bin/sdkmanager --install "platform-tools" "platforms;android-36" &&\
  # Watchman
  wget https://github.com/facebook/watchman/releases/download/v2025.05.26.00/watchman-v2025.05.26.00-linux.zip &&\
  unzip watchman-v2025.05.26.00-linux.zip &&\
  cd watchman-v2025.05.26.00-linux &&\
  mkdir -p /usr/local/{bin,lib} /usr/local/var/run/watchman &&\
  cp bin/* /usr/local/bin &&\
  cp lib/* /usr/local/lib &&\
  chmod 755 /usr/local/bin/watchman &&\
  chmod 2777 /usr/local/var/run/watchman

EXPOSE 8081

WORKDIR /root/workdir
