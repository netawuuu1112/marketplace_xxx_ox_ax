# Current state — 2026-11-15

- Production is on Ubuntu VPS `48.103.149.93`, `/opt/marketfusion`, HTTPS `marketfusionai.kosmo-connect.ru`. Docker Compose runs db, API, web, worker, bot and private Chrome. The user confirmed live `/start` and Mini App opening.
- PostgreSQL and Chrome profile were migrated from Finland with retained restorable archives on the new VPS. Old and new DB counts matched at cutover: 2 users, 1 favorite, 1 AI provider, 5 AI routes, 2 sessions. Public signed auth returned `super_admin` and the favorite.
- Telegram Bot API is reached through the existing Finland SOCKS5 service. The Finland MarketFusion containers, volumes and `/opt/marketfusion` were removed after verification; the proxy remains running. A guarded Nginx bridge on Finland handles stale DNS until its scheduled retirement after 2026-11-17 00:00 UTC.
- Public `ssd` search on the new VPS returns five ordinary prices from Yandex Market. Wildberries sometimes returns cards without ordinary prices; the other eight sources are blocked or time out. The all-source comparison is not a complete MVP. See `docs/MVP_SOURCE_STATUS_RU.md`.
- Live watch probe verified that the worker recorded a Yandex Market ordinary price in history without error; the temporary watch was deleted and the original count restored. Price-change alerts, photo search, AI analysis and full admin flows are not yet verified end to end on the new VPS.

Next: obtain a permitted reliable data path for missing sources within the user's no-spend/no-contact constraints and verify every remaining workflow. Do not claim all-source MVP until live evidence supports it.
