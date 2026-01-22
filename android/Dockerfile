FROM ubuntu:latest

# If host use adb uncomment
# ENV ANDROID_ADB_SERVER_ADDRESS=host.docker.internal

ENV DEBIAN_FRONTEND=noninteractive
ENV ANDROID_HOME=/root/Android/Sdk

RUN apt-get update &&\
  apt-get install -y git wget vim unzip openjdk-17-jdk &&\
  # Setting up android dev
  mkdir -p /root/Android/Sdk/cmdline-tools &&\
  wget https://dl.google.com/android/repository/commandlinetools-linux-13114758_latest.zip &&\
  unzip commandlinetools-linux-13114758_latest.zip -d /root/Android/Sdk/cmdline-tools/ &&\
  rm commandlinetools-linux-13114758_latest.zip &&\
  mv /root/Android/Sdk/cmdline-tools/cmdline-tools /root/Android/Sdk/cmdline-tools/latest &&\
  yes | /root/Android/Sdk/cmdline-tools/latest/bin/sdkmanager --licenses &&\
  yes | /root/Android/Sdk/cmdline-tools/latest/bin/sdkmanager --install "platform-tools" "platforms;android-34" &&\
  echo 'export PATH="$PATH:${ANDROID_HOME}/platform-tools"' >> /root/.bashrc
