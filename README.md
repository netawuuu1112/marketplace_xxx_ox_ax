# MarketFusion AI

Единый репозиторий проекта поиска и сравнения цен. Текущая ветка `feature/core-integration` содержит первый слой интеграции. Полное ТЗ пока **не выполнено**.

## Подключено

- Общий Python backend и Telegram-бот на основе Smart Shopper: поиск Ozon и Яндекс Маркета, анализ отзывов, сравнение, поиск по фото в боте и LLM-логика исходного проекта.
- Коннекторы ru-marketplace-mcp размещены в `integrations/ru-marketplace-mcp`. `GET /api/marketplaces/search?q=...` вызывает их общий модуль сравнения и возвращает состояние каждого источника. Некоторые площадки требуют браузерной сессии или подходящего IP.
- Один React frontend для браузера и Telegram Mini App. В браузере вход по паролю, в Telegram проверка `initData` на backend.
- Общее PostgreSQL-хранилище для сессий, кэша, избранного, настроек и счётчика LLM. SQLite доступен для разработки без Docker.
- Исходники расширения Cennik в `browser-extension`; подключение к общему API ещё не выполнено.

## Локальный запуск

Нужен Docker Desktop с Compose. Скопируйте `.env.example` в `.env` и замените `POSTGRES_PASSWORD`, `WEB_ADMIN_PASSWORD`, `WEB_SESSION_SECRET` на уникальные значения. Для Telegram задайте `SHOPPER_BOT_TOKEN` и публичный HTTPS-адрес `SHOPPER_MINIAPP_URL`.

```powershell
./install.bat
./start.bat
```

Откройте `http://localhost:8080`. Для запуска бота: `docker compose --profile telegram up -d`. Остановка: `./stop.bat`.

На Linux используйте `./install.sh`, `./start.sh`, `./stop.sh`. Для HTTPS на VPS задайте `DOMAIN` в `.env` и запустите `docker compose -f docker-compose.yml -f docker-compose.prod.yml --profile telegram up -d --build`. Домен должен указывать на VPS, порты 80/443 должны быть открыты. База хранится в Docker volume `postgres_data`.

## API

- `GET /health` — проверка процесса.
- `POST /api/auth/login` — вход веб-администратора по паролю из окружения.
- `GET /api/marketplaces/search?q=...` — агрегированный поиск по установленным коннекторам.
- `/api/search`, `/api/compare`, `/api/reviews`, `/api/budget`, `/api/stats` — функции Smart Shopper.

Поиск требует веб-сессию или проверенные Telegram `initData`. Секреты остаются в `.env` на сервере.

## Состояние интеграции

Не реализованы общая ролевая модель пользователей, планировщик мониторинга, история цен в PostgreSQL, уведомления по правилам, админ-панель с паритетом между интерфейсами, маршрутизация нескольких LLM, подключение расширения к API и перенос функционала Grex, PriceWatch и shop-scout. Наличие исходников в репозитории не означает готовность этих функций. Перед публикацией продукта нужен отдельный лицензионный разбор Grex и PriceWatch.

Сведения о происхождении компонентов: [docs/SOURCES.md](docs/SOURCES.md). Работа с GitHub: [docs/GITHUB_WORKFLOW_RU.md](docs/GITHUB_WORKFLOW_RU.md).
