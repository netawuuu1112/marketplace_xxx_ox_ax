#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")"
if [ "$#" -ne 1 ]; then
  printf '%s\n' 'Usage: ./update.sh v1.0.0' >&2
  exit 2
fi
exec ./scripts/deploy-release.sh "$1"
