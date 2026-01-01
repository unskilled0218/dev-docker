FROM node:25-trixie-slim

ENV DEBIAN_FRONTEND=noninteractive
ENV WEBKIT_DISABLE_COMPOSITING_MODE=1

RUN apt update &&\
  apt install -y git vim curl rustup unzip openjdk-17-jdk build-essential \
  libwebkit2gtk-4.1-dev libxdo-dev libssl-dev libayatana-appindicator3-dev \
  librsvg2-dev libcanberra-gtk-module libcanberra-gtk3-module xdg-utils &&\
  rustup default stable &&\
  rustup target add x86_64-unknown-linux-gnu

EXPOSE 1420

WORKDIR /root/workdir
