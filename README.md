# MarketFusion AI

MarketFusion AI — проект поиска и сравнения товаров и цен на российских торговых площадках. Он объединяет веб-интерфейс, Telegram-бота и Mini App, мониторинг цен и браузерное расширение.

> **Где код:** по состоянию на 12 ноября 2026 года весь код находится в ветке [`feature/core-integration`](https://github.com/netawuuu1112/marketplace_xxx_ox_ax/tree/feature/core-integration). Ветки `main` и `develop` пока не содержат приложения. Это рабочая интеграция, **не готовый релиз**. Для запуска после `git clone` нужно переключиться на рабочую ветку.

## Что есть в рабочей ветке

| Часть | Реализовано в коде | Ограничение |
| --- | --- | --- |
| Поиск и сравнение | Агрегированный поиск через `ru-marketplace-mcp`, отдельный поиск Ozon и Яндекс Маркета, сравнение предложений, отзывы и избранное | Доступность и полнота результатов зависят от площадки, IP и защиты от ботов; наличие коннектора не гарантирует живую выдачу |
| Веб и Telegram Mini App | Общий интерфейс на React; вход в веб-панель по паролю, проверка Telegram `initData` на сервере | Для Mini App нужен бот и публичный HTTPS-адрес |
| Telegram-бот | Поиск, сравнение, работа с фото, избранное, наблюдения за ценами и административные команды | Нужны токен бота и проверка с реальным Telegram |
| Мониторинг цен | PostgreSQL, отдельный worker, история проверок, пороговые уведомления в вебе и Telegram | Требуются надёжные результаты источников и проверка длительной работы |
| ИИ | Настройка OpenAI-совместимых провайдеров и моделей по задачам, шифрование ключей | Ключи и реальные вызовы провайдеров ещё не проверены; базовый поиск может работать без ИИ |
| Администрирование | Пользователи, роли `super_admin` / `admin` / `user`, журнал действий, сводка | Гибкие права для `admin` и полный паритет интерфейсов ещё не закончены |
| Расширение | Исходники Cennik для Chrome и Firefox; переход из карточки товара в общий веб-поиск | Локальный мониторинг расширения не синхронизирован с сервером |

Это описание относится к **наличию функций в коде**, а не к подтверждённой работе со всеми реальными сервисами. В репозитории также находятся коннекторы для Wildberries, Ozon, Яндекс Маркета и ряда других источников; их возможности и ограничения описаны в [рабочей ветке](https://github.com/netawuuu1112/marketplace_xxx_ox_ax/tree/feature/core-integration/integrations/ru-marketplace-mcp).

## Устройство проекта

- [`backend`](https://github.com/netawuuu1112/marketplace_xxx_ox_ax/tree/feature/core-integration/backend) — Python API, бот, поиск, настройки ИИ, хранение и мониторинг.
- [`frontend/web`](https://github.com/netawuuu1112/marketplace_xxx_ox_ax/tree/feature/core-integration/frontend/web) — React + TypeScript, веб-интерфейс и Mini App.
- [`integrations/ru-marketplace-mcp`](https://github.com/netawuuu1112/marketplace_xxx_ox_ax/tree/feature/core-integration/integrations/ru-marketplace-mcp) — коннекторы источников и сравнение предложений.
- [`browser-extension`](https://github.com/netawuuu1112/marketplace_xxx_ox_ax/tree/feature/core-integration/browser-extension) — браузерное расширение.
- `docker-compose.yml` — PostgreSQL, API, веб и worker; бот запускается через профиль `telegram`.

## Как запустить локально

Нужны Git и запущенный Docker Desktop (или Docker Engine с Compose). Для веб-проверки Telegram-бот и ключ ИИ не обязательны.

```powershell
git clone https://github.com/netawuuu1112/marketplace_xxx_ox_ax.git
cd marketplace_xxx_ox_ax
git switch feature/core-integration
Copy-Item .env.example .env
```

В `.env` задайте **свои** `POSTGRES_PASSWORD`, `WEB_ADMIN_PASSWORD` и `WEB_SESSION_SECRET`. Для настройки провайдеров ИИ создайте `LLM_ENCRYPTION_KEY` (ключ Fernet) и сохраните его там же. Не публикуйте `.env` и токены в GitHub или переписке. Для проверки без обращения к площадкам можно включить `SHOPPER_DEMO_MODE=1`; демо-каталог относится к поиску Smart Shopper, а не ко всем интегрированным источникам.

```powershell
docker compose up -d --build
docker compose ps
```

Откройте `http://localhost:8080`, войдите с `WEB_ADMIN_PASSWORD` и проверьте `http://localhost:8080/health`. Для остановки: `docker compose down`. Данные PostgreSQL сохраняются в Docker volume `postgres_data`.

На Linux/macOS вместо `Copy-Item` используйте `cp .env.example .env`. Скрипты `install.bat` / `start.bat` и `install.sh` / `start.sh` также находятся в рабочей ветке.

Для Telegram дополнительно нужны `SHOPPER_BOT_TOKEN`, ваш числовой Telegram ID в `TELEGRAM_ADMIN_IDS` и публичный HTTPS URL в `SHOPPER_MINIAPP_URL`. После настройки запустите `docker compose --profile telegram up -d --build`. Для публичного HTTPS-развёртывания предусмотрены Caddy и `docker-compose.prod.yml`; для него отдельно потребуется домен и VPS.

## Что проверить перед выпуском

1. Запустить все сервисы и пройти сценарий входа, поиска, избранного и мониторинга на живом окружении.
2. Проверить реальные площадки по отдельности: ошибки и блокировки должны показываться как ошибки источника, без выдуманных цен.
3. Проверить бота, Mini App, уведомления и права ролей с тестовыми Telegram-пользователями.
4. Проверить выбранные ИИ-провайдеры с реальными ключами и бюджетными лимитами.
5. Решить, какие функции расширения и дополнительных проектов нужны в финальном продукте, затем завершить интеграцию и лицензионную проверку.

В рабочей ветке есть [подробный README](https://github.com/netawuuu1112/marketplace_xxx_ox_ax/blob/feature/core-integration/README.md), [источники компонентов](https://github.com/netawuuu1112/marketplace_xxx_ox_ax/blob/feature/core-integration/docs/SOURCES.md) и [порядок работы с ветками и релизом](https://github.com/netawuuu1112/marketplace_xxx_ox_ax/blob/feature/core-integration/docs/GITHUB_WORKFLOW_RU.md). По принятому в проекте порядку код сначала проверяется в рабочей ветке и `develop`, затем попадает в `main` как проверенный релиз.
