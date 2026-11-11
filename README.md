# MarketFusion AI

Единый репозиторий проекта поиска и сравнения цен. Текущая ветка `feature/core-integration` содержит первый слой интеграции. Полное ТЗ пока **не выполнено**.

## Подключено

- Общий Python backend и Telegram-бот на основе Smart Shopper: поиск Ozon и Яндекс Маркета, анализ отзывов, сравнение, поиск по фото в боте и LLM-логика исходного проекта.
- Коннекторы ru-marketplace-mcp размещены в `integrations/ru-marketplace-mcp`. `GET /api/marketplaces/search?q=...` вызывает их общий модуль сравнения и возвращает состояние каждого источника. Некоторые площадки требуют браузерной сессии или подходящего IP.
- Один React frontend для браузера и Telegram Mini App. В браузере вход по паролю, в Telegram проверка `initData` на backend.
- Общее PostgreSQL-хранилище для сессий, кэша, избранного, настроек и счётчика LLM. SQLite доступен для разработки без Docker.
- Мониторинг цен в PostgreSQL: наблюдения с интервалами от 15 минут до суток, история проверок, пороговые уведомления в вебе и Telegram. Отдельный worker восстанавливает расписание после перезапуска.
- Настройки OpenAI-совместимых LLM-провайдеров через админ-экран: зашифрованные ключи, модели и назначение задач. Поддерживаются AITUNNEL, OpenAI, Qwen, DeepSeek и произвольный совместимый API; для Kimi необходимо ввести Base URL своего API. Без ключей базовый поиск работает без LLM.
- Исходники расширения Cennik в `browser-extension`; подключение к общему API ещё не выполнено.

## Локальный запуск

Нужен Docker Desktop с Compose. Скопируйте `.env.example` в `.env` и замените `POSTGRES_PASSWORD`, `WEB_ADMIN_PASSWORD`, `WEB_SESSION_SECRET` на уникальные значения. Сгенерируйте `LLM_ENCRYPTION_KEY` командой `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` в установленном окружении Python с пакетом `cryptography`. Для Telegram задайте `SHOPPER_BOT_TOKEN`, `TELEGRAM_ADMIN_IDS` и публичный HTTPS-адрес `SHOPPER_MINIAPP_URL`.

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
- `/api/watches`, `/api/watches/{id}/history`, `/api/notifications` — мониторинг, история и уведомления. В боте команды `/watch`, `/watches`, `/history`, `/unwatch`, `/notifications`.
- `/api/admin/ai/providers`, `/api/admin/ai/routes` — настройка ИИ-провайдеров и маршрутизации; доступны веб-администратору и Telegram ID из `TELEGRAM_ADMIN_IDS`.
- `/api/search`, `/api/compare`, `/api/reviews`, `/api/budget`, `/api/stats` — функции Smart Shopper.

Поиск требует веб-сессию или проверенные Telegram `initData`. Секреты остаются в `.env` на сервере.

## Состояние интеграции

Не реализованы общая ролевая модель пользователей, дополнительные правила мониторинга, полная админ-панель с паритетом между интерфейсами, статистика затрат ИИ, подключение расширения к API и перенос функционала Grex, PriceWatch и shop-scout. API-подключения ИИ ещё не проверены с реальными ключами. Живой поиск зависит от доступности площадок: в этой среде Wildberries ответил блокировкой 403. Наличие исходников в репозитории не означает готовность этих функций. Перед публикацией продукта нужен отдельный лицензионный разбор Grex и PriceWatch.

Сведения о происхождении компонентов: [docs/SOURCES.md](docs/SOURCES.md). Работа с GitHub: [docs/GITHUB_WORKFLOW_RU.md](docs/GITHUB_WORKFLOW_RU.md).
