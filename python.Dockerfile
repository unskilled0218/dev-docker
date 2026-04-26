FROM python:3.12

ENV USER_NAME="dev"
ENV GROUP_NAME="dev"

RUN apt update && apt full-upgrade -y &&\
    groupadd -g 1000 ${GROUP_NAME} &&\
    useradd -m -u 1000 -g ${GROUP_NAME} ${USER_NAME}

USER ${USER_NAME}

WORKDIR /home/${USER_NAME}/workdir
