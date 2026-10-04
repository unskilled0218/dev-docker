FROM ubuntu:latest

ENV USER_NAME="dev"
ENV GROUP_NAME="container"

ENV DEBIAN_FRONTEND=noninteractive
ENV ANDROID_ADB_SERVER_ADDRESS=host.docker.internal
ENV ANDROID_HOME=/home/${USER_NAME}/Android/Sdk
ENV PATH="$PATH:$ANDROID_HOME/platform-tools"

RUN usermod -l dev "$(getent passwd 1000 | cut -d: -f1)" &&\
  groupmod -n container "$(getent group 1000 | cut -d: -f1)" &&\
  usermod -d /home/dev -m dev

RUN apt update &&\
  apt install -y git wget vim unzip curl openjdk-17-jdk &&\
  curl -fsSL https://deb.nodesource.com/setup_lts.x | bash - && \
  apt install -y nodejs && \
  apt clean && rm -rf /var/lib/apt/lists/* &&\
  mkdir /home/${USER_NAME}/.npm-global && \
  npm config set prefix '/home/${USER_NAME}/.npm-global' && \
  echo 'export PATH=/home/${USER_NAME}/.npm-global/bin:$PATH' >> /home/${USER_NAME}/.bashrc && \
  /bin/bash -c 'source /home/${USER_NAME}/.bashrc' &&\
  npm --version && \
  node --version

USER ${USER_NAME}

WORKDIR /home/${USER_NAME}

# Setting up android dev
RUN mkdir -p /home/${USER_NAME}/Android/Sdk/cmdline-tools &&\
  wget https://dl.google.com/android/repository/commandlinetools-linux-13114758_latest.zip &&\
  unzip commandlinetools-linux-13114758_latest.zip -d /home/${USER_NAME}/Android/Sdk/cmdline-tools/ &&\
  rm commandlinetools-linux-13114758_latest.zip &&\
  mv /home/${USER_NAME}/Android/Sdk/cmdline-tools/cmdline-tools /home/${USER_NAME}/Android/Sdk/cmdline-tools/latest &&\
  yes | /home/${USER_NAME}/Android/Sdk/cmdline-tools/latest/bin/sdkmanager --licenses &&\
  yes | /home/${USER_NAME}/Android/Sdk/cmdline-tools/latest/bin/sdkmanager --install "platform-tools" "platforms;android-36" &&\
  # Watchman
  wget https://github.com/facebook/watchman/releases/download/v2025.05.26.00/watchman-v2025.05.26.00-linux.zip &&\
  unzip watchman-v2025.05.26.00-linux.zip &&\
  cd watchman-v2025.05.26.00-linux

USER root

RUN mkdir -p /usr/local/{bin,lib} /usr/local/var/run/watchman &&\
  cp /home/${USER_NAME}/watchman-v2025.05.26.00-linux/bin/* /usr/local/bin &&\
  cp /home/${USER_NAME}/watchman-v2025.05.26.00-linux/lib/* /usr/local/lib &&\
  chmod 755 /usr/local/bin/watchman &&\
  chmod 2777 /usr/local/var/run/watchman

EXPOSE 8081

USER ${USER_NAME}

WORKDIR /home/${USER_NAME}/workdir
