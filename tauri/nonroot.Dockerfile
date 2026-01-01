FROM node:25-trixie-slim

ARG USER_NAME="node"

ENV DEBIAN_FRONTEND=noninteractive
ENV WEBKIT_DISABLE_COMPOSITING_MODE=1

RUN apt update &&\
  apt install -y vim curl unzip rustup build-essential \
  libwebkit2gtk-4.1-dev libxdo-dev libssl-dev libayatana-appindicator3-dev \
  librsvg2-dev libcanberra-gtk3-module xdg-utils

USER ${USER_NAME}

RUN rustup default stable &&\
  rustup target add x86_64-unknown-linux-gnu

EXPOSE 1420

WORKDIR /home/${USER_NAME}/workdir
