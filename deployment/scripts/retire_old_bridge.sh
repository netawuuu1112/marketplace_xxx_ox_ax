#!/usr/bin/env bash
# Runs hourly via cron until old DNS caches have had time to expire.
set -euo pipefail

domain=marketfusionai.kosmo-connect.ru
new_ip=48.103.149.93
site=/etc/nginx/sites-available/marketfusion
enabled=/etc/nginx/sites-enabled/marketfusion
backup=/root/marketfusion-bridge-retire-backup.conf

if (( $(date -u +%s) < $(date -u -d '2026-11-17 00:00:00 UTC' +%s) )); then
    exit 0
fi

if ! curl --fail --silent --show-error --max-time 15 \
    --resolve "$domain:443:$new_ip" "https://$domain/health" >/dev/null; then
    exit 1
fi
resolved="$(getent ahostsv4 "$domain" | awk 'NR == 1 { print $1 }')"
if [[ "$resolved" != "$new_ip" ]]; then
    exit 1
fi
grep -Fq "proxy_pass https://$new_ip;" "$site"

cp -a "$site" "$backup"
rm -- "$enabled" "$site"
if nginx -t; then
    systemctl reload nginx
else
    cp -a "$backup" "$site"
    ln -s "$site" "$enabled"
    nginx -t
    exit 1
fi

certbot delete --non-interactive --cert-name "$domain" >/dev/null 2>&1 || true
rm -f -- "$backup" /etc/cron.d/marketfusion-bridge-cleanup
logger "MarketFusion DNS bridge retired; SOCKS5 proxy preserved"
rm -f -- "$0"
