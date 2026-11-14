# Browser Source Readiness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Provide an isolated Chrome CDP route for the already vendored marketplace connectors and measure what it actually unlocks on the VPS.

**Architecture:** An opt-in Compose file starts a dedicated Chromium container with a persistent profile and no published ports. API, bot and worker reach its CDP proxy over the private Compose network. The existing connector's HTTP-to-CDP fallback remains responsible for each source; the browser does not alter search results or fabricate prices.

**Tech Stack:** Docker Compose, Debian Chromium, Xvfb, private Nginx CDP proxy, Python connector CLI.

**Spec:** `docs/superpowers/specs/2026-11-14-mvp-readiness-design.md`

## Global Constraints

- No new paid services and no provider contact.
- Do not expose CDP port 9222 on the VPS host or through Nginx.
- Do not remove existing volumes, containers or unrelated services.
- Browser health must not prevent API, bot or worker startup.
- Never claim a source works based solely on an installed connector or mocked test.

---

### Task 1: Browser service

**Files:** Create `deployment/chrome/Dockerfile`, `deployment/chrome/start.sh`, `deployment/chrome/cdp-nginx.conf`, `docker-compose.browser.yml`. Modify `.github/workflows/verify.yml`.

**Interfaces:** Compose service name `chrome`; internal CDP endpoint `chrome:9222`; named volume `chrome_profile`; environment `CHROME_CDP_HOST=chrome` in API, bot and worker.

- [x] Write an opt-in Compose browser service and bootstrap script. Run Chromium as an unprivileged user with a dedicated persistent profile; bind a CDP proxy only inside its container.
- [x] Run `docker compose -f docker-compose.yml -f docker-compose.browser.yml config --quiet` with safe test values. Confirm the computed Chrome service has no `ports:` publication.
- [x] Extend CI Compose validation to include the browser override.
- [ ] Build and start the override on the VPS without changing existing database volumes. Confirm CDP answers from the API container and the public port 9222 is closed.
- [ ] Run `marketplace-mcp doctor` for Ozon, Wildberries, Avito and the remaining sources. Record observed status per source; do not infer availability from a Chrome startup alone.

### Task 2: Source report

**Files:** Create `docs/MVP_SOURCE_STATUS_RU.md`; update `README.md` with a link.

**Interfaces:** Selfcheck results from the running API container, including source status and reason.

- [ ] Record the current VPS selfcheck matrix and distinguish search health from card/review health.
- [ ] Record the results after browser activation, with date and exact limitations.
- [ ] State whether login, suitable network access or commercial credentials remain necessary for each source.
- [ ] Commit and push the verified status to `feature/core-integration`; keep PR #1 in draft until user flows pass.
