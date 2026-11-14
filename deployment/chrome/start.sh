#!/bin/sh
set -eu

# A container restart keeps /tmp; the previous Xvfb process is gone then.
rm -f /tmp/.X99-lock
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

# Chromium binds CDP to loopback. Forward it only onto this container's private
# Compose network; the service has no published host port.
socat TCP-LISTEN:9222,bind=0.0.0.0,reuseaddr,fork TCP:127.0.0.1:9223 &
socat_pid=$!

trap 'kill "$chrome_pid" "$socat_pid" "$xvfb_pid" 2>/dev/null || true' EXIT INT TERM
wait "$chrome_pid"
