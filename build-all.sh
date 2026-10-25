#!/usr/bin/env bash
set -Eeuo pipefail
set +x
export PYTHONDONTWRITEBYTECODE=1

usage() {
  echo 'Usage: bash build-all.sh [--validate | --build-only] [v<VERSION>]'
  echo 'No arguments publishes VERSION from clean, pushed main. --help (-h) shows usage.'
  echo 'A positional tag is a deprecated assertion and must exactly match v<VERSION>.'
}
stop() {
  echo "Release stopped (${phase:-arguments}): $*" >&2
  if [[ -n "${work:-}" && -f "$work/state.json" ]]; then data status "$work" || true; fi
  exit 1
}

mode=publish
tag=''
flag=''
for arg in "$@"; do
  case "$arg" in
    --help|-h) [[ $# == 1 ]] || stop 'Help cannot be combined with other arguments'; usage; exit 0 ;;
    --validate|--build-only)
      [[ -z "$flag" ]] || stop 'Duplicate or combined modes'
      flag=$arg
      if [[ "$arg" == --validate ]]; then mode=validate; else mode=local; fi ;;
    -*) stop 'Unknown option' ;;
    *) [[ -z "$tag" && -n "$arg" ]] || stop 'Only one nonempty tag is allowed'; tag=$arg ;;
  esac
done
[[ "$mode" != validate || -z "$tag" ]] || stop 'Validation cannot be combined with a tag'
root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
command -v python3 >/dev/null || stop 'Install Python 3.11 or later (standard library only)'
data() { python3 -B "$root/scripts/release_data.py" "$1" "$root" "${@:2}"; }
if [[ -n "$tag" ]]; then data settings "$tag"; else data settings; fi
[[ "$mode" != validate ]] || exit 0
for tool in git docker; do command -v "$tool" >/dev/null || stop "Install required command: $tool"; done
if [[ "$mode" == publish ]]; then command -v curl >/dev/null || stop 'Install curl'; fi
if [[ -z "${RELEASE_LOCK_FD:-}" ]]; then exec python3 -B "$root/scripts/release_data.py" locked "$root" "$@"; fi
data lock-check
progress() { echo "Release phase: $*" >&2; }
umask 077
work=$(mktemp -d "${TMPDIR:-/tmp}/dev-docker-release.XXXXXXXX")
phase='local preflight'
cleanup() { rm -rf -- "$work"; }
trap cleanup EXIT
trap 'echo "Incomplete/uncertain during $phase; inspect exact remote objects without rollback" >&2; data status "$work" || true' ERR
trap 'echo "Interrupted during $phase; inspect without rollback" >&2; data status "$work" || true; exit 130' INT
trap 'echo "Interrupted during $phase; inspect without rollback" >&2; data status "$work" || true; exit 143' TERM
progress 'local preflight'
data init "$work" "$mode"
data builder "$work" "$mode"
data credentials "$work"
if [[ "$mode" == publish ]]; then
  original_docker_config=$(data docker-origin "$work")
  export BUILDX_CONFIG=${BUILDX_CONFIG:-$original_docker_config/buildx}
  # Relative paths keep the caller's working-directory meaning; this script never changes cwd.
  data docker-auth "$work"
  export DOCKER_CONFIG="$work/docker"
  data verify-builder "$work"
  phase='read-only startup classification'
  progress "$phase"
  classification=$(data startup "$work")
  if [[ "$classification" == completed ]]; then progress 'completed release verified; no publication needed'; data summary "$work"; exit 0; fi
  progress 'staging inventory'
  data staging-inventory "$work"
fi
progress 'snapshot preparation'
data snapshot "$work" "$mode"
image_list=$(data images)
mapfile -t images <<< "$image_list"
logged_in=false
for image in "${images[@]}"; do
  phase="prepare $image"
  progress "$phase"
  action=$(data prepare-image "$work" "$image" "$mode")
  if [[ "$action" == build ]]; then
    if [[ "$mode" == publish && "$logged_in" == false ]]; then progress 'registry login'; data login "$work"; logged_in=true; fi
    phase="build $image"
    progress "$phase"
    echo "Building $image ($mode)"
    data build "$work"
    progress "verify $image"
    data accept-image "$work" "$image" "$mode"
  else
    progress "reuse verified $image"
  fi
done
if [[ "$mode" == local ]]; then echo "Built ${#images[@]} local latest images; nothing published"; exit 0; fi
if [[ "$logged_in" == false ]]; then progress 'registry login'; data login "$work"; fi
# Only failed transports may be reconciled against fresh exact evidence. Input/resource
# refusals never become mutation permission, and no failure trap rolls anything back.
attempt() { local status; if "$@"; then return 0; else status=$?; fi; [[ "$status" == 2 ]] || stop 'Input/resource refusal; inspect remaining objects'; }
for image in "${images[@]}"; do
  phase="associate package $image"
  progress "$phase"
  attempt data link-package "$work" "$image"
  data confirm-package "$work" "$image"
done
phase='tag publication'
progress "$phase"
oid=$(data make-tag "$work")
attempt data push-tag "$work" "$oid"
data confirm-tag "$work" "$oid"
release_tag=$(data field "$work" tag)
for image in "${images[@]}"; do
  for alias in "$release_tag" latest; do
    phase="promote $image:$alias"
    progress "$phase"
    action=$(data promote-args "$work" "$image" "$alias")
    if [[ "$action" == promote ]]; then attempt data build "$work"; fi
    data confirm-alias "$work" "$image" "$alias"
  done
done
phase='release creation'
progress "$phase"
data payload "$work"
attempt data post-release "$work"
phase='final verification'
progress "$phase"
data finish "$work"
data summary "$work"
