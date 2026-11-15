# AI development changelog

## 2026-11-15 ? V2 implementation and local verification

Changed backend/catalog_v2, migrations/storage, bot/keyboards/middlewares/worker/matcher/LLM usage, frontend V2 and preserved LegacyWorkspace, tests/CI, isolated staging scripts, README and docs. Added conservative structured identity, partial bounded search, comparison/delivery, owner-scoped persistence, product-bound watches/seven rules/outbox, new Telegram/Web UX and measured AI usage. Independent review defects were reproduced then fixed with regressions (canonical source aliases, S25+, accessories/form factors, GTIN, relational offer reclassification, rolling lows and link concurrency). Final local suite: 82 passed including isolated real PG; 4 fixture browser scenarios; TypeScript/Vite and compileall passed; npm audit 0 vulnerabilities. Docker rebuilt; real local login/four-tabs/admin smoke and empty-schema pg_dump/restore counters verified. No production deployment or live marketplace/bot/paid LLM calls during V2 work. External access, region/delivery, full VPS load and live acceptance remain open; report and release/rollback instructions describe these limits.

## 2026-11-15 — WB search JSON and DNS browser check

Observed live WB search JSON through an owned raw-CDP tab; normalized ordinary prices with existing API rules, exact query/page/origin matching, and DOM fallback. Public deployed `ssd` and `kingston nv3` each returned five ordinary WB prices. Allowed DNS's initial 401 browser check to complete within a bound; public search returned five real cards without prices. Added six focused tests; total local suite passed 22 tests with 1 skipped. Rebuilt WB images and applied a connector-only DNS/core/compare image layer; API, bot and worker share the verified image. Full all-source MVP remains open; seven sources lack a working data path and DNS prices are absent.

## 2026-11-15 — WB card price evidence and GitHub source research

Changed `compare_connector.server`, `frontend/web/nginx.conf`, public probe, WB tests, source/research docs and project memory. The adapter now checks one Wallet-only WB search result against the same native product card and ranks only a `regular` price; WB source timeout is 80 seconds and web proxy timeout 120 seconds. Five focused tests failed before implementation and passed after it; full local suite passed 16 tests with 1 skipped. Built and deployed API, bot, worker and web on the Russia VPS. Public signed WB search first failed with zero product tiles, then returned 5 cards with 1 ordinary price; combined WB/Yandex search returned 10 cards with 6 ordinary prices. Isolated probes recorded eight other source failures. No other source was marked working.

## 2026-11-15 — Russia VPS migration and live watch probe

Changed Telegram proxy transport, Docker dependency/config, Nginx bridge and cleanup templates, deployment probes, README, source status and project memory. Moved production to `48.103.149.93` with PostgreSQL and Chrome profile restored, HTTPS and singleton bot; removed the old Finland app while retaining SOCKS5. Verified matching DB counts, public signed auth/favorite, private Chrome, Yandex Market priced search, user-confirmed bot/Mini App, and a worker-recorded watch price with successful temporary-watch cleanup. Full all-source MVP remains open due to live source blocks/timeouts.

## 2026-11-14 — Browser source readiness

Changed `deployment/chrome/*`, `docker-compose.browser.yml`, `backend/Dockerfile`, CI Compose validation and source status docs. Built and deployed Chrome and API images without removing volumes. Verified private CDP and public HTTPS. Public authenticated comparison returned one source with ordinary prices; full source matrix recorded in `docs/MVP_SOURCE_STATUS_RU.md`.

## 2026-11-14 — Explicit price coverage warning

Changed `frontend/web/src/App.tsx` and `frontend/web/src/api.ts` to show when a source returned products without ordinary prices. TypeScript and Vite build passed locally; rebuilt the web image on VPS and verified the public asset hash matches the local build. Live WB repeat exposed intermittent page navigation; doctor still reports card parser drift.
# 2026-11-15: Marketplace navigation and error states

- Added encoded direct search links for each source that failed or returned no ordinary price in the Mini App's marketplace results.
- Made review loading failure visible and kept comparison loading active until the real API response; comparison failures now appear on the screen.
- Documented that these client links do not restore automatic price data from blocked sources. Deployment verification is recorded separately in CURRENT_STATE.md.
