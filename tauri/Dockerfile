FROM ubuntu:latest

ENV DEBIAN_FRONTEND=noninteractive
ENV WEBKIT_DISABLE_COMPOSITING_MODE=1

RUN apt update &&\
    apt install -y vim curl rustup unzip openjdk-17-jdk libwebkit2gtk-4.1-dev build-essential libxdo-dev libssl-dev libayatana-appindicator3-dev librsvg2-dev libcanberra-gtk-module libcanberra-gtk3-module &&\
    # Install Node.js 24
    curl -o- https://fnm.vercel.app/install | bash &&\
    . /root/.bashrc &&\
    fnm install 24 &&\
    rustup default stable &&\
    rustup target add x86_64-unknown-linux-gnu

EXPOSE 1420

WORKDIR /root/workdir
