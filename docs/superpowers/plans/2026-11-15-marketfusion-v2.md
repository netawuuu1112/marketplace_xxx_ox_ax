# MarketFusion V2 implementation plan

**Goal:** Execute the supplied V2 specification in an isolated branch and test environment.
**Spec:** `docs/MARKETFUSION_V2_REQUIREMENTS_RU.md`.
**Architecture:** A shared additive domain/service layer wraps installed connectors; PostgreSQL stores versioned catalog/search/watch entities; bot and web consume the same business logic. Preserve legacy authorization, favorites, AI settings, review/photo workflows and data.
**Constraints:** No secrets in Git, no paid access or vendor contact, no production deployment without fresh owner approval, one Chromium and bounded jobs, no invented prices/delivery/matching evidence.

- [x] Audit current code, source evidence, clean baseline and PR; isolate branch at c2042cc.
- [x] Models and additive, transaction-protected PostgreSQL migrations; legacy watches need product selection.
- [x] Query normalization and conservative category/variant matching with behavioral tests.
- [x] Independent source adapters, bounded asynchronous search jobs, ownership, cache, diagnostics and partial results.
- [x] Exact-only comparison, delivery totals and product/history APIs.
- [x] Product-bound watches, seven alert conditions, leases, history, event deduplication and outbox.
- [x] Telegram single welcome/menu button, text/photo/link routing, contextual callbacks and V2 results.
- [x] Mini App tokens/themes, four tabs, incremental search, filters/sort, product/offer/history/watch flows and protected admin.
- [x] Regression/integration/browser verification, staging configuration, rollback/backups instructions and final source matrix.
- [x] Logical commits, GitHub PR against feature/core-integration; keep production unchanged pending owner permission.

Local gates: 82 Python tests including real isolated PostgreSQL; four offline UI scenarios; TypeScript/Vite/compileall; npm audit zero; real Docker API smoke and empty-schema restore. Independent review fixes covered by red/green regressions. See verification report for exact scope. Full-stack production load, live V2 external integrations, regional prices/delivery and owner production approval remain open; these are not checked off by fixture tests.

Published draft PR #9: https://github.com/netawuuu1112/marketplace_xxx_ox_ax/pull/9. GitHub Actions run43752255039 passed all four jobs on code SHA5a79c08.

- [ ] External source/region/delivery data and live V2 acceptance.
- [ ] Full-stack VPS load and real production backup recovery check.
- [ ] Separate owner release permission under specification section14.
