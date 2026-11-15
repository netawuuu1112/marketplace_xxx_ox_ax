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
- [ ] Regression/integration/browser verification, staging configuration, rollback/backups instructions and final source matrix.
- [ ] Logical commits, GitHub PR against feature/core-integration; keep production unchanged pending owner permission.

Local gates: 82 Python tests including real isolated PostgreSQL; four offline UI scenarios; TypeScript/Vite/compileall; npm audit zero; real Docker API smoke and empty-schema restore. Independent review fixes covered by red/green regressions. See verification report for exact scope. Full-stack production load, live V2 external integrations, regional prices/delivery and owner production approval remain open; these are not checked off by fixture tests.
