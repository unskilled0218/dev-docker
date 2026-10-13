#!/bin/bash

cp /usr/local/share/ca-certificates/git.lanCA.crt ./
cp ~/.config/forgejo/forgejo-token ./

echo "my-base >"
docker build -t my-base:latest -f Dockerfile/base.Dockerfile .
echo "my-base done"

rm git.lanCA.crt forgejo-token

echo "npm-non-root >"
docker build -t npm-non-root -f Dockerfile/npm.Dockerfile .
echo "npm-non-root done"

echo "android-dev >"
docker build -t android-dev -f Dockerfile/android.Dockerfile .
echo "android-dev done"

echo "tauri-dev >"
docker build -t tauri-dev -f Dockerfile/tauri.Dockerfile .
echo "tauri-dev done"
