FROM rust:1.96.0-slim-trixie

ENV USER_NAME="dev-container"
ENV GROUP_NAME="dev-container"

RUN apt update && apt full-upgrade -y &&\
    groupadd -g 1000 ${GROUP_NAME} &&\
    useradd -m -u 1000 -g ${GROUP_NAME} ${USER_NAME} &&\
    apt install -y git wget vim unzip curl build-essential &&\
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

WORKDIR /home/${USER_NAME}/workdir
