# syntax=docker/dockerfile:1
FROM ubuntu:24.04

COPY lan.crt /usr/local/share/ca-certificates/lan.crt

ENV DEBIAN_FRONTEND=noninteractive

ENV USER_NAME="container"
ENV GROUP_NAME="container"

RUN usermod -l ${USER_NAME} "$(getent passwd 1000 | cut -d: -f1)" &&\
  groupmod -n ${GROUP_NAME} "$(getent group 1000 | cut -d: -f1)" &&\
  usermod -d /home/${USER_NAME} -m ${USER_NAME} &&\
  groupadd -g 983 docker &&\
  apt-get update &&\
  apt-get install -y \
  git wget vim unzip curl build-essential jq python3 &&\
  update-ca-certificates &&\
  rm -rf /var/lib/apt/lists/*

COPY scripts/install-docker.sh /tmp/install-docker.sh
RUN bash /tmp/install-docker.sh &&\
  rm /tmp/install-docker.sh &&\
  rm -rf /var/lib/apt/lists/*

USER ${USER_NAME}

RUN mkdir -p /home/${USER_NAME}/workdir &&\
  curl -fsSL https://git.lan/dev/agents/raw/branch/main/scripts/setup.sh | bash

COPY --chown=1000:1000 scripts/configure-penpot.py /tmp/configure-penpot.py
RUN test -x /home/${USER_NAME}/.opencode/bin/opencode &&\
  python3 /tmp/configure-penpot.py &&\
  mkdir -p -m 0700 /home/${USER_NAME}/.config/token &&\
  rm /tmp/configure-penpot.py

COPY --chown=1000:1000 user-config/ssh/ /home/container/.ssh/
COPY --chown=1000:1000 user-config/gitconfig /home/container/.gitconfig
COPY --chown=1000:1000 user-config/token/ /home/container/.config/token/
RUN chmod 0700 /home/container/.ssh /home/container/.config/token
