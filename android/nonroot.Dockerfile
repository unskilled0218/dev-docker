FROM ubuntu:latest

ENV USER_NAME="ubuntu"

WORKDIR /home/${USER_NAME}

ENV DEBIAN_FRONTEND=noninteractive
ENV ANDROID_ADB_SERVER_ADDRESS=host.docker.internal
ENV ANDROID_HOME=/home/${USER_NAME}/Android/Sdk
ENV PATH="$PATH:$ANDROID_HOME/platform-tools"

RUN apt-get update &&\
  apt-get install -y git wget vim unzip openjdk-17-jdk

USER ${USER_NAME}

# Setting up android dev
RUN mkdir -p /home/${USER_NAME}/Android/Sdk/cmdline-tools &&\
  wget https://dl.google.com/android/repository/commandlinetools-linux-13114758_latest.zip &&\
  unzip commandlinetools-linux-13114758_latest.zip -d /home/${USER_NAME}/Android/Sdk/cmdline-tools/ &&\
  rm commandlinetools-linux-13114758_latest.zip &&\
  mv /home/${USER_NAME}/Android/Sdk/cmdline-tools/cmdline-tools /home/${USER_NAME}/Android/Sdk/cmdline-tools/latest &&\
  yes | /home/${USER_NAME}/Android/Sdk/cmdline-tools/latest/bin/sdkmanager --licenses

WORKDIR /home/${USER_NAME}/workdir
