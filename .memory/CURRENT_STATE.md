# Current state — 2026-11-16

## Active V2 branch

Worktree `.worktrees/v2`, branch `feature/marketfusion-v2`, baseline c2042cc, draft PR9 https://github.com/netawuuu1112/marketplace_xxx_ox_ax/pull/9 against feature/core-integration. No V2 production deployment. Binding requirements §14 require separate release permission. User explicitly confirms servers currently unavailable: stop VPS probes until restored. No new spending or vendor contact authorized.

Implemented shared product/variant/offer identity, incremental/cancellable bounded search, owner-scoped persistence/favorites, regional exact comparison, seven-rule watches with lease/outbox/history and paused legacy watch migration, four-tab Web/Mini App, shared bot search and preserved administration/photo/review paths. Distinct MPN/condition/foreign-region safeguards have regressions. Nginx Host-port loss causing local Origin PATCH403 fixed using http_host.

Live local HTTP flow query Kingston NV3 1TB returned real ordinary prices from YM8/WB15/Avito15/DNS2/AliExpress5. Same MPN SNV3S/1000G exact group contains YM+WB+DNS; different MPN and unknown-condition classifieds stay separate. YM actual globalDeliveryPoint Moscow is propagated; selected-offer watch/worker recorded1730100minor units, real history, no error. No real price-drop event or Telegram send demonstrated. docs/qa/v2-live-summary.json is sanitized actual evidence, not fixture.

Optional private agent routes selected sources via loopback8092; auth/whitelist/8KB/20calls-per-minute/5queued/2running/80s inclusive deadline/2MBresponse/cancellation. Local staging API chooses avito,dns,aliexpress via agent; Chrome private. Temporary VPS->SSH Unix socket->desktop probe previously returned15Avito/2AliExpress prices, then socket/dir removed. Persistent VPS route not installed, no Windows autostart task. Computer/Docker/SSH uptime is required; no 24/7 guarantee. Agent has no DB/bot/LLM secrets.

Reviews now use maintained YM/WB connectors under source gates; unavailable or unusable nonempty pools report503, no failureemptycache. Native YM cardroute resolves a model family; reviews labeled variant_group, pooled verdicts forced no_data with persistent warning and content/scope cache. Actual YM API20013reviews; two WBnativeIDs basket404->503 (WBsuccessful reviewread open). LegacyOzon adapter preserved, ambiguousempty reported unavailable. Separate pros/cons now reach analysisprompt. AITunnel metadata399models includes gpt-4o-mini; missing visionroute fixed. No paid AI/vision generation or botpolling started.

Latest verified local gates:117Python tests including actual isolatedPG passed (one curl_cffi Windowsselector fallback warning); six API-fixture browser scenarios passed; TypeScript/Vite and Docker builds passed; npm audit0vulnerabilities; actual Nginx/session/fourtab/admin/Origin/no390overflow smoke passed. Nonempty local restore matched fullJSONB fingerprints for10tables:products32, variants32, offers52, mf_favorites2, searchobservations52, watches3, watchobservations3 (after the repeat real flow). Independent review fixed identity/agent/watch and reviewissues; final reviewer found no remaining critical/important issues; tenfocusedreviewtests passed. Latest GitHubCI after finalpush must be read separately; previous29cd6f9 had all4passed.

## Remaining acceptance gaps

FreshNov16 blocked sources:Ozon403,Citilink429Qrator,Megamarket403,Lamoda403(queryкроссовки),Taobao login/CAPTCHA. Full all-source MVP is incomplete. Actual regions/delivery for other sources unknown; do not invent delivered totals or permit regional watches there. Stabilize under load, verify WBreview success, actual AI/photo, real Telegram alert, production backup/restore and fullstack VPSload. LocalAPI/agent/Chrome/PG/Web measured~681MiB after search, not fullbotworkerVPS proof.

## Last known production (historical, Nov15; currently unavailable)

Russia48.103.149.93 `/opt/marketfusion`, HTTPS marketfusionai.kosmo-connect.ru, SSH codex-vps-2. Old core-integration API/Web/bot/worker/PG/privateChrome; owner confirmed bot and MiniApp. Migration fromFinland preserved DB; oldcounts2users,1favorite,1AIprovider,5AIroutes,2sessions. FinlandSOCKS5 retained for Telegram and oldprojectremoved afterverification; guardedstaleDNSbridge retirement scheduledNov17. Preserve unrelated services/proxy.

Production had publicYM/WBpricedsearch and workerYMhistory; DNS5cards0prices. V2 has not changed deployed application or production DB. Latest SSHbanner/HTTPS timedout, includingcross-networkprobe. Read-only backup helper failed before SQL/envread; no freshproductiondump exists fromthiscontinuation. No further VPScalls afterownerconfirmedunavailability.

Next: push checkedcontinuation/updatePR; retain localreviewablestaging/package. Whenserversrestore, freshbackup/restore/load/liveacceptance then separate §14permission. Do not callall-sourceMVPorproductionready until evidence supportsit.
