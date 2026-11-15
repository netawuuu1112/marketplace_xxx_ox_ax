# MarketFusion V2 implementation plan

**Goal:** Execute the supplied V2 specification in an isolated branch and test environment.
**Spec:** `docs/MARKETFUSION_V2_REQUIREMENTS_RU.md`.
**Architecture:** A shared additive domain/service layer wraps installed connectors; PostgreSQL stores versioned catalog/search/watch entities; bot and web consume the same business logic. Preserve legacy authorization, favorites, AI settings, review/photo workflows and data.
**Constraints:** No secrets in Git, no paid access or vendor contact, no production deployment without fresh owner approval, one Chromium and bounded jobs, no invented prices/delivery/matching evidence.

- [x] Audit current code, source evidence, clean baseline and PR; isolate branch at c2042cc.
- [ ] Models and additive, transaction-protected PostgreSQL migrations; legacy watches need product selection.
- [ ] Query normalization and conservative category/variant matching with behavioral tests.
- [ ] Independent source adapters, bounded asynchronous search jobs, ownership, cache, diagnostics and partial results.
- [ ] Exact-only comparison, delivery totals and product/history APIs.
- [ ] Product-bound watches, seven alert conditions, leases, history, event deduplication and outbox.
- [ ] Telegram single welcome/menu button, text/photo/link routing, contextual callbacks and V2 results.
- [ ] Mini App tokens/themes, four tabs, incremental search, filters/sort, product/offer/history/watch flows and protected admin.
- [ ] Regression/integration/browser verification, staging configuration, rollback/backups instructions and final source matrix.
- [ ] Logical commits, GitHub PR against feature/core-integration; keep production unchanged pending owner permission.
