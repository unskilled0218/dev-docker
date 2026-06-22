FROM rust:1.96.0-slim-trixie

ENV USER_NAME="dev-container"
ENV GROUP_NAME="dev-container"

RUN apt update && apt full-upgrade -y &&\
    groupadd -g 1000 ${GROUP_NAME} &&\
    useradd -m -u 1000 -g ${GROUP_NAME} ${USER_NAME}

USER ${USER_NAME}

WORKDIR /home/${USER_NAME}/workdir
