# Tasks

## V2 modernization

- [x] Preserve supplied requirements; audit and isolate branch.
- [x] Implement/test domain identity, partial search, owner-scoped API, product-bound watches and migrations.
- [x] Implement/test single-message Telegram UX and mobile V2 components.
- [x] Review integration edges; run isolated staging/empty-schema restore, browser checks and document exact remaining live/load gaps.
- [ ] Commit logical stages, push feature/marketfusion-v2, open PR to feature/core-integration.
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
- [ ] Restore DNS price loading; documented AjaxState product-buy registration was absent from the current page.
- [ ] Obtain permitted working access for blocked marketplaces within user constraints; retest each source.
- [ ] Verify same-item cross-market comparison with at least two confirmed ordinary prices.
- [ ] Verify end-to-end monitoring, alerts, AI analysis, photo search, admin and bot flows.
- [ ] Complete full MVP and merge the draft PR only when requirements and live integration checks pass.
