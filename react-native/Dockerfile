FROM android-dev-image

EXPOSE 8081

RUN apt-get update &&\
  apt-get install -y curl &&\
  # Install Node.js 24
  curl -o- https://fnm.vercel.app/install | bash &&\
  . /root/.bashrc &&\
  fnm install 24 &&\
  # Watchman
  wget https://github.com/facebook/watchman/releases/download/v2025.05.26.00/watchman-v2025.05.26.00-linux.zip &&\
  unzip watchman-v2025.05.26.00-linux.zip &&\
  cd watchman-v2025.05.26.00-linux &&\
  mkdir -p /usr/local/{bin,lib} /usr/local/var/run/watchman &&\
  cp bin/* /usr/local/bin &&\
  cp lib/* /usr/local/lib&&\
  chmod 755 /usr/local/bin/watchman&&\
  chmod 2777 /usr/local/var/run/watchman

WORKDIR /root/workdir
