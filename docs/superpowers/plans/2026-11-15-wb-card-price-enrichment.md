# Wildberries Card Price Enrichment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Put a verified ordinary Wildberries price into cross-market search when the search grid only shows a WB Wallet price.

**Architecture:** Keep the existing WB search and comparison modules. For at most one Wallet-only result, read its native product card through the existing `wb_card` connector. Accept a price only if the card returns the same nmId and labels the price `regular`; keep the search result and a warning on any card failure. Give this bounded second navigation a source-specific deadline while preserving the existing deadlines for other marketplaces.

**Tech Stack:** Python, FastMCP connector, pytest, Docker Compose, private Chromium CDP.

**Spec:** `docs/superpowers/specs/2026-11-14-mvp-readiness-design.md`.

## Global Constraints

- Never use WB Wallet or crossed-out prices as ordinary prices.
- Never substitute a card from another nmId or fabricate an offer when a card read fails.
- Bound card reads to one per WB search and keep per-source diagnostics.
- No new external service, credential, vendor contact or expense.
- Live server verification is required before claiming the source works.

---

### Task 1: Reproduce and test

- [x] Confirm WB search JSON API returns 403 on the Russia VPS; Chrome search yields five cards with zero ordinary prices.
- [x] Confirm a native WB card for a search result yields `regular` price and separate Wallet price (nmId 2124848933, 3284 vs 3185 RUB).
- [x] Add failing tests for matching regular card, wrong card, conditional-only card and card failure.

### Task 2: Implement bounded enrichment

- [x] In `compare_connector.server._search_wildberries`, enrich one Wallet-only search result using `wb_card` with exact nmId validation.
- [x] Increase only WB's source deadline enough for one card navigation; keep other source ceilings unchanged.
- [x] Preserve warnings when the card fails or does not establish an ordinary price.

### Task 3: Verify and deploy

- [x] Run focused and full tests, type/build checks where applicable, and Compose validation.
- [x] Deploy on the Russia VPS without changing PostgreSQL or starting a second bot.
- [x] Probe public signed WB and cross-market searches; confirm price kind, source outcomes and service health. One WB read failed before a successful repeat; stability remains open.
- [x] Update source status, README and `.memory`, commit and push; keep the PR draft while other sources remain blocked.
