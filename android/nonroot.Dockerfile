FROM ubuntu:latest

ENV USER_NAME="ubuntu"

WORKDIR /home/${USER_NAME}

# If host use adb uncomment
# ENV ANDROID_ADB_SERVER_ADDRESS=host.docker.internal

ENV DEBIAN_FRONTEND=noninteractive
ENV ANDROID_HOME=/home/${USER_NAME}/Android/Sdk

RUN apt-get update &&\
  apt-get install -y git wget vim unzip openjdk-17-jdk

USER ${USER_NAME}

# Setting up android dev
RUN mkdir -p /home/${USER_NAME}/Android/Sdk/cmdline-tools &&\
  wget https://dl.google.com/android/repository/commandlinetools-linux-13114758_latest.zip &&\
  unzip commandlinetools-linux-13114758_latest.zip -d /home/${USER_NAME}/Android/Sdk/cmdline-tools/ &&\
  rm commandlinetools-linux-13114758_latest.zip &&\
  mv /home/${USER_NAME}/Android/Sdk/cmdline-tools/cmdline-tools /home/${USER_NAME}/Android/Sdk/cmdline-tools/latest &&\
  yes | /home/${USER_NAME}/Android/Sdk/cmdline-tools/latest/bin/sdkmanager --licenses &&\
  yes | /home/${USER_NAME}/Android/Sdk/cmdline-tools/latest/bin/sdkmanager --install "platform-tools" &&\
  echo 'export PATH="$PATH:${ANDROID_HOME}/platform-tools"' >> /home/${USER_NAME}/.bashrc

WORKDIR /home/${USER_NAME}/workdir
