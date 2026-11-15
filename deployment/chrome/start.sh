#!/bin/sh
set -eu

# A container restart keeps /tmp; the previous Xvfb process is gone then.
rm -f /tmp/.X99-lock
# The persistent profile retains Chrome's host-specific singleton symlinks
# after the former container has been stopped during Compose recreation.
rm -f /home/browser/profile/SingletonLock \
  /home/browser/profile/SingletonSocket \
  /home/browser/profile/SingletonCookie
Xvfb :99 -screen 0 1280x800x24 -nolisten tcp &
xvfb_pid=$!
sleep 1

chromium \
  --no-first-run \
  --no-default-browser-check \
  --no-sandbox \
  --disable-dev-shm-usage \
  --remote-debugging-address=127.0.0.1 \
  --remote-debugging-port=9223 \
  --user-data-dir=/home/browser/profile \
  --window-size=1280,800 \
  about:blank &
chrome_pid=$!

# Chromium only accepts localhost as the CDP HTTP Host. The private proxy
# rewrites that header and forwards WebSocket upgrades within this container.
nginx -c /etc/nginx/cdp.conf -g 'daemon off;' &
proxy_pid=$!

trap 'kill "$chrome_pid" "$proxy_pid" "$xvfb_pid" 2>/dev/null || true' EXIT INT TERM
wait "$chrome_pid"
