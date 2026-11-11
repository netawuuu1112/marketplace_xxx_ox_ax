#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")"
mkdir -p backups
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
docker compose exec -T db pg_dump -U marketfusion -Fc marketfusion > "backups/marketfusion-$stamp.dump"
printf '%s\n' "Backup: backups/marketfusion-$stamp.dump"
