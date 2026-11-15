# Errors and fixes

## 2026-11-15 ? V2 independent review regressions

Phone '+' variants, screen protectors, SSD form factors and GPU SUPER suffixes could collapse into exact groups because extraction omitted their distinguishing markers. Added plus normalization, shared connector accessory policy and distinguishing attributes; numeric checksum-valid GTIN queries now carry identity. Stable native offer enrichment changed JSON identity without relational mf_offers product_id/variant_id: upsert now updates both, verified by actual PG old/new product reads. Rolling-window minima retained permanent emitted bounds and lost pending candidates during cooldown: emitted timestamps age bounds once and retain new pending state. Canonical wildberries/yandex_market names were missing legacy bot actions: explicit alias mapping restores them. WB URL resolution now uses the same local/distributed source gates. Regression tests failed before fixes and passed afterward; do not infer untested universal category coverage from these examples.

## 2026-11-15 — DNS initial 401 and installed connector copies

An initial DNS 401 could be the site's JavaScript browser check, not its final page. Keeping an owned raw-CDP tab alive allowed normal site navigation to finish and exposed 24 products (prices remain absent). Added opt-in DNS-only bounded navigation waiting; unresolved 401/429 and 403 still fail. Temporary probes must set PYTHONPATH when exercising repository-source files: most connector packages in the Docker image are installed copies in site-packages, so copying a file only under /app/integrations does not update runtime imports. Production changes require image replacement.

## 2026-11-15 — WB conditional search price and intermittent empty grid

WB's JSON search endpoint returned HTTP 403 from the new VPS. Chrome search tiles exposed only WB Wallet prices, while a same-nmId card exposed an ordinary price separately. Added bounded card enrichment with exact id/type checks; a live repeat returned one ordinary WB price and a combined WB/Yandex query returned six priced offers. The initial post-deploy WB request still failed: Chrome showed the site shell but zero product tiles, and the connector reported `parser_drift`. Search-grid stability remains open; no price is fabricated on that path.

## 2026-11-15 — Isolated source failures

Separate public authenticated requests showed DNS HTTP 401, Citilink HTTP 429, Lamoda HTTP 403, Ozon HTTP 403, Avito IP firewall, Taobao login/CAPTCHA, AliExpress zero recognized tiles, and Megamarket 45-second timeout. These occurred without all-source browser contention. Do not label them all as generic timeout or treat installing another parser as a fix.

## 2026-11-15 — Old Nginx bridge returned 502

The bridge initially failed upstream certificate verification at depth 3 (error 20). Set `proxy_ssl_verify_depth 5` while retaining verification and SNI. Both the new direct HTTPS endpoint and the old bridge `/health` returned HTTP 200 afterward.

## 2026-11-15 — Telegram direct route timed out

Bot API access from the Russia VPS timed out directly. The existing Finland SOCKS5 service with remote DNS returned a valid Bot API response; configure aiogram bot sessions and worker notification requests to use `TELEGRAM_SOCKS_PROXY`. The real bot `/start` and Mini App were confirmed by the user.

## 2026-11-14 — Chromium CDP startup and connection

Initial private browser connection failed because of container sandbox restrictions, Nginx runtime paths, stale profile lock, CDP Host/WebSocket rewriting, and missing `libatomic.so.1` in the API image. Fixed in `deployment/chrome/*`, `docker-compose.browser.yml`, and `backend/Dockerfile`. Verification: `marketplace-mcp browser status` from the deployed API reported reachable Chrome/156 at `chrome:9222`.

## 2026-11-14 — Marketplace source limits

Ozon returns HTTP 403 through browser; Avito reports IP firewall; WB DOM search returns cards but only conditional Wallet prices, which compare excludes. Other source outcomes are in `docs/MVP_SOURCE_STATUS_RU.md`. These are open external or parser issues, not fixed by browser startup alone.
