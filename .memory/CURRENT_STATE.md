# Current state — 2026-11-16

## Branch and constraints

Active worktree `.worktrees/v2`, branch `feature/marketfusion-v2`, baseline c2042cc. Draft PR9: https://github.com/netawuuu1112/marketplace_xxx_ox_ax/pull/9 against feature/core-integration. No V2 production deployment; supplied requirements §14 require separate owner permission. User confirms servers are currently unavailable: do not probe VPS again until restored. No new spending, vendor contact, second bot poller or paid AI calls authorized in this continuation.

## Implemented and observed

Shared product/variant/offer identity, incremental cancellable search, owner-scoped PostgreSQL data, favorites, regional comparison, seven watch rules with leases/outbox/history and paused legacy-watch migration. Four-tab Web/Mini App, shared bot search and existing administration/photo paths retained. Regression fixes cover MPN, condition negations, Avito uncertain state, foreign-city minimum and selected-offer region. Nginx preserves Host port so real Origin PATCH works.

Latest genuine local HTTP query Kingston NV3 1TB returned ordinary priced cards: YM8, WB15, Avito15, DNS2, AliExpress5. Exact MPN SNV3S/1000G spans YM/WB/DNS; different MPN and unknown-condition classifieds remain separate. Actual YM globalDeliveryPoint confirms Moscow. An offer-bound watch was measured twice at 1730100 minor units (17301 RUB), with history and no error. No actual price-drop event or Telegram alert occurred. Sanitized evidence: docs/qa/v2-live-summary.json.

Optional private agent routes avito,dns,aliexpress through the desktop network. Loopback8092, bearer authentication, source whitelist, 8KB request cap, 20 calls/minute, max5 queued/2 running, 80s inclusive deadline, cancellation, 2MB response cap. Agent has no DB/bot/AI secrets; Chrome is private. Earlier temporary VPS->SSH Unix socket->desktop probe returned Avito/AliExpress prices; temporary route and directory removed. No persistent VPS route or Windows autostart installed. Computer, Docker, network and SSH must stay running; 24/7 availability is unproven.

Maintained YM/WB review readers use shared source gates. Inaccessible/unusable nonempty pools return503 and remain uncached. YM requested SKU can resolve to a model family: label variant_group, do not certify selected-variant requirements, retain final scope warning, include scope/content in cache and pros/cons in prompt. Actual YM API200 returned13 reviews, rendered in real UI. Two WB IDs returned basket404->503; successful WB review read remains open. Legacy Ozon retained, ambiguous empty extraction treated as unavailable. AITunnel metadata includes gpt-4o-mini; missing vision fallback fixed and unit-tested, actual generation unverified.

## Verification

117 Python tests passed, including genuine isolated PostgreSQL, HTTP, migration, ownership, reconnect and worker checks. One Windows curl_cffi selector-fallback warning. Six browser scenarios with explicit API fixtures passed; TypeScript/Vite/Docker builds and npm audit0 passed. Actual staging smoke verified login/HttpOnly/four tabs/admin/Origin/no390px overflow. Actual product offers, two measured history points and13 source reviews rendered without API interception or JS errors. QA screenshots are labeled live vs fixture.

Nonempty local backup/restore matched full JSONB fingerprints for10 tables: products32, variants32, offers52, mf_favorites2, search observations52, watches3, watch observations3. This is not a production restore. Local API/agent/Chrome/PG/Web measured about681MiB after a prior search, not full bot/worker load on1GB VPS. Independent review corrections passed; no remaining critical/important findings,10 focused review tests passed.

Commits6dc8602 (source/region/identity) and8f75bb4 (reviews/UI/vision) plus3f012d3 (docs/checks) pushed. GitHub run43934115228 failed Compose validation because the optional profiles were omitted from a config-only command. Exact failure reproduced locally; enabling agent/browser profiles passes. Corrected CI and actual UI evidence are the current final follow-up; final run must be read separately. Prior29cd6f9 had four passing jobs.

## Remaining and historical production

Fresh Nov16 failures: Ozon403, Citilink429/Qrator, Megamarket403, Lamoda403(queryкроссовки), Taobao login/CAPTCHA. Full all-source MVP is incomplete. Other actual regions/delivery, stable load, successful WB reviews, actual AI/photo, Telegram alert delivery, production backup/restore and VPS load acceptance remain open. No fabricated delivered totals or regional watches for unknown geography.

Last known production Nov15: Russia48.103.149.93 `/opt/marketfusion`, domain marketfusionai.kosmo-connect.ru, alias codex-vps-2. Old core-integration stack; owner confirmed bot and MiniApp. Migration preserved counts2 users/1 favorite/1 AI provider/5 AI routes/2 sessions. Finland SOCKS5 remains; old project removed after verification; guarded stale-DNS bridge retirement scheduledNov17. Preserve proxy/unrelated services.

Production had YM/WB priced search and real YM worker history; DNS returned cards without prices. Latest SSH banner/HTTPS timed out; owner then confirmed servers unavailable. Read-only production backup failed before SQL/env read, no fresh dump obtained. V2 did not change production application or DB. Stop all VPS calls while unavailable.

Next: finish final CI/PR/package evidence and retain the local reviewable stack. After servers return: fresh backup/restore/load/live acceptance, then separate §14 release permission.
