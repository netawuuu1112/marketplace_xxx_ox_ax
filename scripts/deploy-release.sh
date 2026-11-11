#!/usr/bin/env sh
set -eu
if [ "$#" -ne 1 ]; then
  printf '%s\n' 'Usage: ./scripts/deploy-release.sh v1.0.0' >&2
  exit 2
fi
tag="$1"
case "$tag" in
  v[0-9]*.[0-9]*.[0-9]*) ;;
  *) printf '%s\n' 'Expected a SemVer tag' >&2; exit 2 ;;
esac
cd "$(dirname "$0")/.."
git fetch origin main --tags
git merge-base --is-ancestor "$tag" origin/main
./backup.sh
git switch --detach "$tag"
docker compose -f docker-compose.yml -f docker-compose.prod.yml --profile telegram up -d --build
printf '%s\n' "$tag" > deployed-version
printf '%s\n' "Deployed $tag"
