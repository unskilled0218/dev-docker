#!/bin/bash
set -euo pipefail

usage() {
  echo "Usage: bash build-all.sh [--build-only] [TAG]"
}

fail() {
  echo "Error: $*" >&2
  exit 1
}

publish=true
tag=latest
tag_set=false
for arg in "$@"; do
  case "$arg" in
    --build-only) publish=false ;;
    --help|-h) usage; exit 0 ;;
    -*) fail "Unknown option: $arg" ;;
    *)
      [[ "$tag_set" == false ]] || fail "Only one tag is allowed."
      tag="$arg"
      tag_set=true
      ;;
  esac
done
[[ "$tag" =~ ^[a-zA-Z0-9_][a-zA-Z0-9_.-]{0,127}$ ]] || fail "Invalid image tag: $tag"

project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
remote="$(git -C "$project_dir" remote get-url origin)"
case "$remote" in
  ssh://*|https://*|http://*)
    address="${remote#*://}"
    authority="${address%%/*}"
    registry="${authority##*@}"
    path="${address#*/}"
    # SSH ports are not registry ports; Forgejo's registry uses HTTPS.
    [[ "$remote" != ssh://* ]] || registry="${registry%%:*}"
    ;;
  *@*:*)
    address="${remote#*@}"
    registry="${address%%:*}"
    path="${address#*:}"
    ;;
  *) fail "Origin must be an SSH or HTTP(S) Forgejo remote." ;;
esac
path="${path%.git}"
[[ "$registry" != "" && "$path" =~ ^([^/]+)/([^/]+)$ ]] || fail "Origin must identify an owner and repository."
owner="${BASH_REMATCH[1]}"
repo="${BASH_REMATCH[2]}"
source_url="https://$registry/$owner/$repo"
image_prefix="${registry,,}/${owner,,}"
username="${FORGEJO_USERNAME:-$owner}"
token_file="${FORGEJO_TOKEN_FILE:-$HOME/.config/forgejo/forgejo-token}"
cert_file="${BUILD_CERT_FILE:-/usr/local/share/ca-certificates/git.lanCA.crt}"

command -v docker >/dev/null || fail "Docker is required."
[[ -s "$token_file" && -r "$token_file" ]] || fail "Cannot read Forgejo token: $token_file"
[[ -r "$cert_file" ]] || fail "Cannot read existing build certificate: $cert_file"
docker info >/dev/null

temp_dir="$(mktemp -d)"
trap 'rm -rf -- "$temp_dir"' EXIT
mkdir -p "$temp_dir/context/Dockerfile" "$temp_dir/docker-config"
cp "$project_dir"/Dockerfile/*.Dockerfile "$temp_dir/context/Dockerfile/"
cp "$cert_file" "$temp_dir/context/git.lanCA.crt"

if [[ "$publish" == true ]]; then
  docker --config "$temp_dir/docker-config" login "$registry" --username "$username" --password-stdin < "$token_file"
fi

images=(my-base npm-non-root android-dev tauri-dev)
dockerfiles=(base npm android tauri)
for index in "${!images[@]}"; do
  image="${images[$index]}"
  release_image="$image_prefix/$image:$tag"
  options=()
  if [[ "$index" == 0 ]]; then
    options+=(--secret "id=forgejo-token,src=$token_file")
  fi
  echo "Building $release_image"
  DOCKER_BUILDKIT=1 docker build "${options[@]}" \
    --label "org.opencontainers.image.source=$source_url" \
    -t "$image:latest" -t "$release_image" \
    -f "$temp_dir/context/Dockerfile/${dockerfiles[$index]}.Dockerfile" "$temp_dir/context"
done

if [[ "$publish" == true ]]; then
  for image in "${images[@]}"; do
    docker --config "$temp_dir/docker-config" push "$image_prefix/$image:$tag"
  done
fi
