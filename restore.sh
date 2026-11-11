#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")"
if [ "$#" -ne 1 ] || [ ! -f "$1" ]; then
  printf '%s\n' 'Usage: ./restore.sh backups/marketfusion-YYYYMMDDTHHMMSSZ.dump' >&2
  exit 2
fi
docker compose stop api bot
docker compose exec -T db pg_restore -U marketfusion -d marketfusion --clean --if-exists --no-owner < "$1"
docker compose up -d api
