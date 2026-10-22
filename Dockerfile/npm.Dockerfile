FROM my-base:latest

USER root

RUN apt update &&\
  apt install -y \
  git wget vim unzip curl build-essential python3-full &&\
  curl -fsSL https://deb.nodesource.com/setup_lts.x | bash - &&\
  apt install -y nodejs &&\
  apt clean &&\
  rm -rf /var/lib/apt/lists/* &&\
  mkdir /home/${USER_NAME}/.npm-global  &&\
  npm config set prefix '/home/${USER_NAME}/.npm-global' &&\
  cat >> /home/${USER_NAME}/.bashrc <<'EOF'
  export PATH=/home/${USER_NAME}/.npm-global/bin:$PATH
  EOF &&\
  /bin/bash -c 'source /home/${USER_NAME}/.bashrc' &&\
  chown -R ${USER_NAME}:${GROUP_NAME} /home/${USER_NAME} &&\
  npm --version &&\
  node --version &&\
  yes | npx playwright install-deps chromium firefox

USER ${USER_NAME}

RUN npx playwright install chromium firefox