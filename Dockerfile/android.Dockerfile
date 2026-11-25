FROM debian:bookworm-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl unzip openjdk-17-jre-headless libasound2 libpulse0 \
    libgl1 libegl1 libnss3 libx11-6 libxcomposite1 libxcursor1 libxi6 \
    libxrandr2 libxtst6 libxkbcommon-x11-0 libxcb-cursor0 \
  && rm -rf /var/lib/apt/lists/*

ENV ANDROID_HOME=/opt/android-sdk
ENV PATH=$ANDROID_HOME/cmdline-tools/latest/bin:$ANDROID_HOME/platform-tools:$ANDROID_HOME/emulator:$PATH

RUN useradd --create-home android && mkdir -p "$ANDROID_HOME/cmdline-tools" \
  && chown -R android:android "$ANDROID_HOME"
USER android
WORKDIR /home/android

RUN curl -fsSL https://dl.google.com/android/repository/commandlinetools-linux-11076708_latest.zip -o /tmp/tools.zip \
  && unzip -q /tmp/tools.zip -d "$ANDROID_HOME/cmdline-tools" \
  && mv "$ANDROID_HOME/cmdline-tools/cmdline-tools" "$ANDROID_HOME/cmdline-tools/latest" \
  && rm /tmp/tools.zip
RUN yes | sdkmanager --licenses >/dev/null \
  && sdkmanager 'platform-tools' 'emulator' 'system-images;android-36;google_apis;x86_64' \
  && mkdir -p /home/android/.android
