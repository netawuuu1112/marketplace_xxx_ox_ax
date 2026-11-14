FROM debian:bookworm-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
      ca-certificates chromium curl fonts-liberation nginx-light xvfb \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 browser \
    && mkdir -p /home/browser/profile \
    && chown -R browser:browser /home/browser

COPY deployment/chrome/start.sh /usr/local/bin/start-marketfusion-chrome
COPY deployment/chrome/cdp-nginx.conf /etc/nginx/cdp.conf
RUN chmod 755 /usr/local/bin/start-marketfusion-chrome

USER browser
ENV HOME=/home/browser DISPLAY=:99
WORKDIR /home/browser
ENTRYPOINT ["/usr/local/bin/start-marketfusion-chrome"]
