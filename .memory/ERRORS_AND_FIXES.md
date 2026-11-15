# Errors and fixes

## 2026-11-15 — Old Nginx bridge returned 502

The bridge initially failed upstream certificate verification at depth 3 (error 20). Set `proxy_ssl_verify_depth 5` while retaining verification and SNI. Both the new direct HTTPS endpoint and the old bridge `/health` returned HTTP 200 afterward.

## 2026-11-15 — Telegram direct route timed out

Bot API access from the Russia VPS timed out directly. The existing Finland SOCKS5 service with remote DNS returned a valid Bot API response; configure aiogram bot sessions and worker notification requests to use `TELEGRAM_SOCKS_PROXY`. The real bot `/start` and Mini App were confirmed by the user.

## 2026-11-14 — Chromium CDP startup and connection

Initial private browser connection failed because of container sandbox restrictions, Nginx runtime paths, stale profile lock, CDP Host/WebSocket rewriting, and missing `libatomic.so.1` in the API image. Fixed in `deployment/chrome/*`, `docker-compose.browser.yml`, and `backend/Dockerfile`. Verification: `marketplace-mcp browser status` from the deployed API reported reachable Chrome/156 at `chrome:9222`.

## 2026-11-14 — Marketplace source limits

Ozon returns HTTP 403 through browser; Avito reports IP firewall; WB DOM search returns cards but only conditional Wallet prices, which compare excludes. Other source outcomes are in `docs/MVP_SOURCE_STATUS_RU.md`. These are open external or parser issues, not fixed by browser startup alone.
