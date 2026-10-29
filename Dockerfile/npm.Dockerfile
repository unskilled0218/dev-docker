ARG BASE_IMAGE=base:latest
FROM ${BASE_IMAGE}

USER root

RUN apt update &&\
  apt install -y python3-full &&\
  curl -fsSL https://deb.nodesource.com/setup_lts.x | bash - &&\
  apt install -y nodejs &&\
  apt clean &&\
  rm -rf /var/lib/apt/lists/* &&\
  mkdir /home/${USER_NAME}/.npm-global &&\
  npm config set prefix '/home/${USER_NAME}/.npm-global' &&\
  /bin/bash -c 'source /home/${USER_NAME}/.bashrc' &&\
  chown -R ${USER_NAME}:${GROUP_NAME} /home/${USER_NAME} &&\
  npm --version &&\
  node --version

USER ${USER_NAME}

WORKDIR /home/${USER_NAME}

RUN printf 'export PATH=/home/%s/.npm-global/bin:$PATH\n' "$USER_NAME" >> "/home/$USER_NAME/.bashrc" &&\
  PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1 npm install --save-exact @playwright/test@1.64.1
