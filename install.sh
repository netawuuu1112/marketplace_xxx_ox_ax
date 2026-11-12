#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")"
if [ ! -f .env ]; then cp .env.example .env; fi
printf '%s\n' 'Edit .env, then run ./start.sh.'
docker compose build
