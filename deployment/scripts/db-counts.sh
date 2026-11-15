#!/usr/bin/env bash
set -euo pipefail
cd /opt/marketfusion
for table in users favorites watchlists price_history notifications ai_providers ai_routes sessions; do
    count="$(docker compose -f docker-compose.yml -f docker-compose.browser.yml exec -T db psql -U marketfusion -d marketfusion -Atc "select count(*) from ${table}")"
    printf '%s=%s\n' "$table" "$count"
done
