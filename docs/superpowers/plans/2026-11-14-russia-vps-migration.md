# Russia VPS Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move MarketFusion and its persistent state to `48.103.149.93`, route Telegram Bot API traffic through the existing Finland SOCKS5 service, and retire only the old MarketFusion deployment after live verification.

**Architecture:** Install Docker, Compose, Nginx, Certbot and swap on the clean Ubuntu VPS. Transfer the existing MarketFusion environment and PostgreSQL dump over SSH without printing secrets. Bring up the database, API, web and worker first; move the singleton Telegram bot only after data restore and proxy verification. Keep the Finland SOCKS5 service and unrelated services running.

**Tech Stack:** Ubuntu 24.04, Docker Compose, PostgreSQL 16, Nginx, Let's Encrypt, aiogram 3, aiohttp-socks, Dante SOCKS5.

**Spec:** `docs/superpowers/specs/2026-11-14-mvp-readiness-design.md`; user migration instruction of 2026-11-14.

## Global Constraints

- Do not print or commit credentials, private keys, proxy passwords, database content or bot tokens.
- Keep the old proxy and unrelated services intact.
- Do not run two polling instances of the same bot.
- Do not delete old MarketFusion until new DB, HTTPS, bot, API and data counts are verified; retain a restorable backup.
- No new paid data provider or vendor contact.

---

### Task 1: Inventory and readiness

- [x] Confirm SSH access to both VPSs and inspect new VPS resources, existing services, DNS and old proxy metadata.
- [x] Record migration baseline: old DB size/row counts, old app config keys, proxy URL format, DNS TTL and new VPS available resources.
- [x] Verify new IP marketplace connectivity and Telegram direct failure without secrets.

### Task 2: Telegram proxy support

**Files:** `backend/bot.py`, `backend/monitoring.py`, `backend/config.py`, `backend/requirements.txt`, tests.

- [x] Add optional `TELEGRAM_SOCKS_PROXY` to Bot API requests in bot and worker; keep direct path when unset.
- [x] Test both proxy and direct session selection without hitting live Telegram.
- [x] Transfer existing SOCKS5 credentials to new VPS only via private files and verify Bot API connectivity through proxy.

### Task 3: New server bootstrap and data transfer

- [x] Install Docker Compose, Nginx and Certbot; configure persistent swap and firewall with SSH retained.
- [x] Clone `feature/core-integration`, transfer `.env` privately, adjust deployment-only variables and proxy URL, and verify Compose config.
- [x] Make and retain a PostgreSQL dump on the old VPS; copy it to the new VPS and restore with table/row checks.
- [x] Start DB, API, web, worker and private Chrome; verify local health, logs and migrated data. VPS has persistent 4 GiB swap; monitor resource use under all-source searches.

### Task 4: HTTPS and singleton bot cutover

- [x] Confirm authoritative DNS points to `48.103.149.93`; configure Nginx and obtain certificate.
- [x] Verify public HTTPS routes and Telegram Mini App URL.
- [x] Stop the old MarketFusion bot, start the singleton new bot through SOCKS5, verify Bot API and user-confirmed `/start` and Mini App.
- [x] Verify real search, favorite, watch/worker history and signed admin access; record marketplace source outcomes from new IP. Alert delivery and other workflows remain in `.memory/TASKS.md`.

### Task 5: Retire old MarketFusion

- [x] After cutover checks, remove old MarketFusion containers, project directory and volumes; retain restorable DB and Chrome archives on the new VPS and keep Finland SOCKS5.
- [x] Verify SOCKS5 from new VPS still works and no old MarketFusion application containers remain. The temporary Finland Nginx DNS bridge is scheduled for guarded retirement after 2026-11-17 00:00 UTC.
- [x] Update README, `.memory` and PR status; run tests and record remaining MVP gaps.
