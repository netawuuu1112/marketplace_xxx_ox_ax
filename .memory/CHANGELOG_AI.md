# AI development changelog

## 2026-11-14 — Browser source readiness

Changed `deployment/chrome/*`, `docker-compose.browser.yml`, `backend/Dockerfile`, CI Compose validation and source status docs. Built and deployed Chrome and API images without removing volumes. Verified private CDP and public HTTPS. Public authenticated comparison returned one source with ordinary prices; full source matrix recorded in `docs/MVP_SOURCE_STATUS_RU.md`.

## 2026-11-14 — Explicit price coverage warning

Changed `frontend/web/src/App.tsx` and `frontend/web/src/api.ts` to show when a source returned products without ordinary prices. TypeScript and Vite build passed locally; rebuilt the web image on VPS and verified the public asset hash matches the local build. Live WB repeat exposed intermittent page navigation; doctor still reports card parser drift.
