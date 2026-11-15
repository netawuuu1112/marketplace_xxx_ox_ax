# Decisions

## 2026-11-15 — Wildberries price from a verified card

When WB search shows only a Wallet amount, read at most one matching native card through the existing connector. Rank its amount only when the nmId matches and the card labels it `regular`; retain an unpriced offer and warning on failure. Increase only WB's per-source ceiling to 80 seconds to allow the second browser navigation. The first live request still failed at search-grid loading, so this path improves price evidence only when the search page works.

## 2026-11-15 — Russia VPS and Telegram transport

Run production on `48.103.149.93` and route only Telegram Bot API traffic through the existing Finland SOCKS5 proxy with remote DNS. Direct Bot API traffic from the new VPS timed out. Keep Chrome private and persist the migrated PostgreSQL and browser state. Retain a guarded Finland Nginx bridge for stale DNS and retire it after 2026-11-17 00:00 UTC once new DNS and health checks pass. Preserve the proxy independently of the removed old application.

## 2026-11-14 — Private Chromium route

Run Chromium as an optional dedicated Compose service on the internal network, with no published CDP port. This supports connector browser transport without changing the database or exposing browser control publicly. It cannot defeat source IP blocks.

## 2026-11-14 — Price evidence

Keep WB Wallet and other conditional prices out of ordinary-price ranking. Surface missing ordinary-price coverage in the UI. A found card is not evidence of a comparable price.

## 2026-11-14 — External access

Use no new paid provider and send no vendor inquiry, per user instruction. Preserve external source failures explicitly; do not mark full MVP complete until live paths work.
