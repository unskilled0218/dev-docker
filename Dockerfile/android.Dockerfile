ARG BASE_IMAGE=npm-non-root:latest
FROM ${BASE_IMAGE}

ENV ANDROID_ADB_SERVER_ADDRESS=host.docker.internal

ENV DEBIAN_FRONTEND=noninteractive

ENV ANDROID_HOME=/home/${USER_NAME}/Android/Sdk
ENV ANDROID_SDK_ROOT=/home/${USER_NAME}/Android/Sdk
ENV GRADLE_HOME=/home/${USER_NAME}/gradle-9.5.1

USER root

RUN apt update && apt install -y openjdk-17-jdk-headless

USER ${USER_NAME}

# Setting up android dev
RUN \
  # cmdline-tools
  mkdir -p ${ANDROID_HOME}/cmdline-tools ${ANDROID_HOME}/build-tools ${ANDROID_HOME}/ndk ${ANDROID_HOME}/platforms &&\
  wget https://dl.google.com/android/repository/commandlinetools-linux-13114758_latest.zip &&\
  unzip commandlinetools-linux-13114758_latest.zip -d /home/${USER_NAME}/Android/Sdk/cmdline-tools/ &&\
  rm commandlinetools-linux-13114758_latest.zip &&\
  mv ${ANDROID_HOME}/cmdline-tools/cmdline-tools ${ANDROID_HOME}/cmdline-tools/latest &&\
  yes | ${ANDROID_HOME}/cmdline-tools/latest/bin/sdkmanager --licenses &&\
  yes | ${ANDROID_HOME}/cmdline-tools/latest/bin/sdkmanager --install "platform-tools" &&\
  yes | ${ANDROID_HOME}/cmdline-tools/latest/bin/sdkmanager "platforms;android-35" &&\
  echo 'export PATH="$PATH:${ANDROID_HOME}/platform-tools"' >> /home/${USER_NAME}/.bashrc &&\
  # Gradle
  wget https://services.gradle.org/distributions/gradle-9.5.1-bin.zip &&\
  unzip -d /home/${USER_NAME} gradle-9.5.1-bin.zip &&\
  rm gradle-9.5.1-bin.zip &&\
  echo 'export PATH=$PATH:${GRADLE_HOME}/bin' >> /home/${USER_NAME}/.bashrc
