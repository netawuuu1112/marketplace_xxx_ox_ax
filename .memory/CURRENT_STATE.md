# Current state — 2026-11-21

## New VPS deployment

The owner authorized deployment on the new `codex-russia` VPS only. Ubuntu 24.04.4 amd64, 1 vCPU, 961 MiB RAM, 96 GB disk, 4 GiB swap added. SSH uses remote NAT port 51678; guest address is private. External HTTP requests to 80/443/8080 did not receive the guest test listener's response. DNS pointed to the previous VPS at check time. Access is through the loopback SSH tunnel documented in docs/MARKETFUSION_V2_RUSSIA_VPS.md. No old server was contacted.

Application checked out from GitHub in /opt/marketfusion on deploy/marketfusion-v2-russia. Docker starts at boot. Web/API/PostgreSQL/worker/private Chromium are running with unless-stopped; PostgreSQL and Chromium profile have distinct persistent volumes. Fresh database; old production data was not migrated. Bot still disabled: direct Telegram HTTPS timed out and sole ownership of existing bot token has not been confirmed. No paid AI calls. Phase-specific constraints and historical V2 evidence follow below.

Client browser passed login and navigation to Favorites, Monitoring and Profile over SSH. Authenticated API and anonymous admin denial passed. Chromium proxy initially failed with EACCES due to secure checkout file mode. COPY --chmod=0644 and healthcheck against the proxy on 9222 fixed it; rebuilt and CDP status reachable from API. Repeated real search: Yandex 8 ordinary prices in Moscow; DNS 2 cards without price; WB API403 and browser no tiles, Avito CDP timeout, AliExpress no tiles. Dedicated running worker recorded 1646600 minor units in Moscow history. The new verification watch was retained and paused. The follow-up private archive restored independently with 2 migration records, 4 products and 1 watch. The actual watch observation survived DB restart and authenticated API checks passed again. Ozon and Citilink did not complete browser navigation, Megamarket timed out and Lamoda/Taobao required a challenge. This one VPS check does not replace earlier local five-source proof.

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

Commits6dc8602 (source/region/identity) and8f75bb4 (reviews/UI/vision) plus3f012d3 (docs/checks) pushed. GitHub run43934115228 failed Compose validation because the optional profiles were omitted from a config-only command. Exact failure reproduced locally; enabling agent/browser profiles passes. Corrected CI and actual UI evidence pushed as96a48a43ec2146a7d4225f5ee8f32623dc669b34. GitHub run43934832807 passed all four jobs: backend/PostgreSQL, frontend/browser, Compose and extension. Code is verified at that SHA; any following commit only records evidence.

## Remaining and historical production

Fresh Nov16 failures: Ozon403, Citilink429/Qrator, Megamarket403, Lamoda403(queryкроссовки), Taobao login/CAPTCHA. Full all-source MVP is incomplete. Other actual regions/delivery, stable load, successful WB reviews, actual AI/photo, Telegram alert delivery, production backup/restore and VPS load acceptance remain open. No fabricated delivered totals or regional watches for unknown geography.

Last known production Nov15: Russia48.103.149.93 `/opt/marketfusion`, domain marketfusionai.kosmo-connect.ru, alias codex-vps-2. Old core-integration stack; owner confirmed bot and MiniApp. Migration preserved counts2 users/1 favorite/1 AI provider/5 AI routes/2 sessions. Finland SOCKS5 remains; old project removed after verification; guarded stale-DNS bridge retirement scheduledNov17. Preserve proxy/unrelated services.

Production had YM/WB priced search and real YM worker history; DNS returned cards without prices. Latest SSH banner/HTTPS timed out; owner then confirmed servers unavailable. Read-only production backup failed before SQL/env read, no fresh dump obtained. V2 did not change production application or DB. Stop all VPS calls while unavailable.

Checked code archive backups/v2/marketfusion-v2-96a48a4.zip: SHA2563bd928a526b95e5f7660598b8c487a9e83d29b429b520a464f223bf41e9f51d6,1737000bytes. ZIP integrity and tracked-file credential/excluded-file scan passed. Retain this local reviewable stack/package. After servers return: fresh backup/restore/load/live acceptance, then separate §14 release permission.
