FROM android-dev:latest

ENV WEBKIT_DISABLE_COMPOSITING_MODE=1
ENV ANDROID_ADB_SERVER_ADDRESS=host.docker.internal
ENV ANDROID_HOME=/home/${USER_NAME}/Android/Sdk
ENV PATH="$PATH:$ANDROID_HOME/platform-tools"

USER root

RUN apt update &&\
  apt install -y \
  x11-apps rustup xdg-utils file \
  libwebkit2gtk-4.1-dev libxdo-dev libssl-dev \
  libayatana-appindicator3-dev librsvg2-dev libcanberra-gtk3-module &&\
  rustup default stable

USER ${USER_NAME}

WORKDIR /home/${USER_NAME}

EXPOSE 1420

RUN rustup default stable &&\
  rustup target add x86_64-unknown-linux-gnu &&\
  # Watchman
  wget https://github.com/facebook/watchman/releases/download/v2025.05.26.00/watchman-v2025.05.26.00-linux.zip &&\
  unzip watchman-v2025.05.26.00-linux.zip &&\
  cd watchman-v2025.05.26.00-linux

USER root

RUN mkdir -p /usr/local/{bin,lib} /usr/local/var/run/watchman &&\
  cp /home/${USER_NAME}/watchman-v2025.05.26.00-linux/bin/* /usr/local/bin &&\
  cp /home/${USER_NAME}/watchman-v2025.05.26.00-linux/lib/* /usr/local/lib &&\
  chmod 755 /usr/local/bin/watchman &&\
  chmod 2777 /usr/local/var/run/watchman

USER ${USER_NAME}
