# Tasks

## V2 modernization

- [x] Preserve supplied requirements; audit and isolate branch.
- [x] Implement/test domain identity, partial search, owner-scoped API, product-bound watches and migrations.
- [x] Implement/test single-message Telegram UX and mobile V2 components.
- [x] Review integration edges; run isolated staging/empty-schema restore, browser checks and document exact remaining live/load gaps.
- [x] Commit logical stages, push feature/marketfusion-v2, open draft PR #9 to feature/core-integration; four GitHub CI jobs passed on 5a79c08.
- [ ] Obtain separate owner permission before any V2 production deployment.
- [ ] Confirm external source/region/delivery support and live end-to-end acceptance separately from fixture checks.

- [x] Deploy private Chromium route and verify CDP from API.
- [x] Probe all ten comparison sources through public authenticated API and record observed state.
- [x] Deploy and verify user-facing warning for sources with cards but no ordinary price (TypeScript/Vite build and matching public bundle hash).
- [x] Migrate MarketFusion to the Russia VPS with PostgreSQL, Chrome profile, HTTPS and a single Telegram bot; retain Finland SOCKS5 and a guarded temporary DNS bridge.
- [x] Verify a real Yandex Market price watch via worker and remove the temporary watch.
- [x] Determine whether Wildberries product-card route can yield a confirmed ordinary price; add bounded same-nmId enrichment and verify one live ordinary price.
- [x] Add client-side links to marketplace search pages for failed or unpriced sources; show review/compare API errors instead of a hanging or silent screen.
- [x] Deploy and verify this frontend update through the public HTTPS site and a browser interaction check (simulated error responses in browser; live marketplace access unchanged).
- [ ] Stabilize Wildberries search grid access; one live request still returned no product tiles before a successful repeat.
- [x] Deploy and live-verify WB current-page search JSON observation: public `ssd` and `kingston nv3` each returned five ordinary prices.
- [x] Deploy and public-verify DNS browser-check waiting: five real cards, zero prices.
- [x] Restore and live-verify DNS prices on the private local agent (2 priced cards); VPS direct route and regional monitoring remain unverified.
- [ ] Obtain permitted working access for blocked marketplaces within user constraints; retest each source.
- [x] Verify same-MPN SNV3S/1000G comparison with ordinary YM/WB/DNS prices on real local V2 flow; delivery/other-source regions remain unknown.
- [ ] Verify end-to-end monitoring, alerts, AI analysis, photo search, admin and bot flows.
- [ ] Complete full MVP and merge the draft PR only when requirements and live integration checks pass.


## Continuation Nov16

- [x] Propagate actual YM delivery-point region; live selected-offer watch/worker/history in isolated staging.
- [x] Private source-agent transport and temporary Unix tunnel proof; no persistent VPS route installed.
- [x] Fix Host-port CSRF, condition negations, inline MPN, foreign-city minimum, selected-offer region, unknown-condition Avito grouping.
- [x] Connect maintained YM/WB review readers, strict failure status, shared-card scope/analysis constraints, content/scope cache and pros/cons prompt. YM13 live reviews; WB404 still open.
- [x] Add missing AITunnel vision fallback; routing test only, actual generation remains open.
- [x] 117Python tests, 6browser fixture scenarios, real staging smoke, builds, npm audit0, nonempty10table restore, independentreview.
- [ ] Read latest GitHub CI after final continuation push and synchronize PR evidence.
- [ ] Revisit production only after owner restores servers; no further probes while explicitly unavailable.
- [ ] Successful WB review read and complete real AI/photo/Telegram event acceptance.
- [ ] Confirm stable autonomous all-source access under no-spend/no-contact constraints; five sources still blocked.
