#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")"
./backup.sh
docker compose pull
docker compose build
docker compose up -d
