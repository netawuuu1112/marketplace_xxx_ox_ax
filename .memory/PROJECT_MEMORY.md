# MarketFusion AI

Telegram bot, Mini App and web application for searching products, comparing marketplace prices, favorites, AI analysis, and price monitoring. Python backend and vendored `integrations/ru-marketplace-mcp` connectors, React frontend, PostgreSQL, Docker Compose, Nginx HTTPS. Working branch `feature/core-integration`; production project is `/opt/marketfusion` on Russia VPS `48.103.149.93` (SSH alias `codex-vps-2`), domain `marketfusionai.kosmo-connect.ru`. Finland VPS retains the SOCKS5 service needed for Telegram Bot API and a temporary guarded DNS bridge, but no old MarketFusion containers or project directory.

The user requires a complete working MVP across all listed sources, but allows no new expenses and does not authorize contacting data vendors. Never report a connector as working based on installation or fixture tests. Never commit or print the Telegram/AITUNNEL secrets. Do not delete unrelated VPS services or data.

`docker-compose.browser.yml` is the opt-in private Chromium route for connectors. Source health and remaining constraints are in `docs/MVP_SOURCE_STATUS_RU.md`.
