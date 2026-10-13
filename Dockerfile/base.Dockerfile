# syntax=docker/dockerfile:1
FROM ubuntu:24.04

COPY git.lanCA.crt /usr/local/share/ca-certificates/git.lanCA.crt

ENV DEBIAN_FRONTEND=noninteractive

ENV USER_NAME="container"
ENV GROUP_NAME="container"

RUN usermod -l ${USER_NAME} "$(getent passwd 1000 | cut -d: -f1)" &&\
  groupmod -n ${GROUP_NAME} "$(getent group 1000 | cut -d: -f1)" &&\
  usermod -d /home/${USER_NAME} -m ${USER_NAME} &&\
  groupadd -g 988 docker &&\
  apt update &&\
  apt install -y \
  git wget vim unzip curl build-essential &&\
  update-ca-certificates &&\
  curl -fsSL https://git.lan/dev/scripts/raw/branch/main/install-docker.sh | bash

RUN chown -R ${USER_NAME}:${GROUP_NAME} /home/${USER_NAME}

USER ${USER_NAME}

RUN --mount=type=secret,id=forgejo-token,target=/home/container/.config/forgejo/forgejo-token,uid=1000,required=true \
  mkdir -p /home/${USER_NAME}/workdir &&\
  curl -fsSL https://git.lan/dev/agents/raw/branch/main/scripts/setup.sh | bash

WORKDIR /home/${USER_NAME}/workdir/project
