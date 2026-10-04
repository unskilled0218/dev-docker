FROM ubuntu:latest

ENV DEBIAN_FRONTEND=noninteractive

ENV USER_NAME="dev"
ENV GROUP_NAME="container"

usermod -l dev "$(getent passwd 1000 | cut -d: -f1)"
groupmod -n container "$(getent group 1000 | cut -d: -f1)"
usermod -d /home/dev -m dev

RUN apt-get update &&\
  apt-get install -y \
  git wget vim unzip curl build-essential &&\
  curl -fsSL https://deb.nodesource.com/setup_lts.x | bash - && \
  apt-get install -y nodejs && \
  apt-get clean && rm -rf /var/lib/apt/lists/* &&\
  mkdir /home/${USER_NAME}/.npm-global && \
  npm config set prefix '/home/${USER_NAME}/.npm-global' && \
  echo 'export PATH=/home/${USER_NAME}/.npm-global/bin:$PATH' >> /home/${USER_NAME}/.bashrc && \
  /bin/bash -c 'source /home/${USER_NAME}/.bashrc' &&\
  npm --version &&\
  node --version

USER ${USER_NAME}

WORKDIR /home/${USER_NAME}
