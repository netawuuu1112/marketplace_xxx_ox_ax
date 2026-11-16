# V2: локальный запуск, выпуск и откат

Production не обновлять без отдельного разрешения владельца (§14 [ТЗ](MARKETFUSION_V2_REQUIREMENTS_RU.md)). Ветка `feature/marketfusion-v2` основана на `c2042cc`; PR направлен в `feature/core-integration`. Создание PR не запускает production: workflow развёртывания ручной и требует стабильный release tag. Не запускать второй long-polling бот с рабочим токеном.

## Изолированный локальный стенд Windows

Нужны Docker Desktop/Compose. Из корня ветки:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File deployment/scripts/start_v2_staging.ps1
```

Открыть `http://127.0.0.1:8089`. Скрипт создаёт отдельные случайные пароли в игнорируемом `.env.v2-staging`; пароль входа — локальное значение `V2_WEB_PASSWORD`. Не отправлять и не коммитить файл. Стенд имеет собственный Docker project `marketfusion-v2-staging`, БД и тома, не читает production `.env`, не запускает бот и платный ИИ. Demo выключен. Поиск без браузера может возвращать ограниченные результаты — для необязательного локального Chrome:

```powershell
docker compose --env-file .env.v2-staging -f docker-compose.v2-staging.yml --profile browser up -d --build
```

CDP не публикуется на хосте. Остановка сохраняет данные:

```powershell
docker compose --env-file .env.v2-staging -f docker-compose.v2-staging.yml stop
```

Для нового клона установить Python-зависимости из `backend/requirements.txt` и локальные пакеты `integrations/ru-marketplace-mcp/packages/*`; создать `.venv`. В текущем worktree Python находится в родительском репозитории `..\..\.venv\Scripts\python.exe`. Фронтенд: `npm ci` в `frontend/web`. Не использовать production DATABASE_URL в тестах.

Для проверенного маршрута пяти источников включить [приватный агент](MARKETFUSION_V2_SOURCE_AGENT.md); запуск базового Compose без overlay не сохраняет агент в конфигурации API.

## Проверки

```powershell
# Нужна отдельная локальная PostgreSQL; роль должна создавать временные БД.
# Подставить свой локальный URL, не production.
$env:MARKETFUSION_TEST_DATABASE_URL='postgresql://USER:PASSWORD@127.0.0.1:PORT/TEST_DB'
python -m pytest -q tests

# Из frontend/web:
npm run build
npm run dev -- --host 127.0.0.1 --port 5173
# В другом терминале из корня:
$env:V2_UI_URL='http://127.0.0.1:5173'
python frontend/web/tests/browser_v2.py

# Реальный локальный Docker API, без запросов площадкам:
python deployment/scripts/check_v2_staging.py
powershell -NoProfile -ExecutionPolicy Bypass -File deployment/scripts/verify_v2_restore.ps1
```

Браузерные проверки требуют `pip install playwright` и установленный Google Chrome. Скрипт восстановления сначала проверяет Docker project, делает dump и восстанавливает в отдельную случайную БД, сравнивает полные JSONB-отпечатки десяти таблиц и удаляет только эту временную БД. Архив и копия локального env сохраняются под игнорируемым `backups/v2/`. Они содержат приватные данные и не включаются в PR. Проверено восстановление непустого локального стенда. Оно не заменяет проверку реальной копии production.

GitHub `verify.yml` запускает Python с PostgreSQL, сборку и шесть браузерных сценариев, Compose и расширение при PR в рабочую ветку. Успешный локальный запуск не является результатом GitHub Actions: статус CI нужно читать отдельно.

## Будущее production-обновление после разрешения

1. Записать фактический commit и image IDs работающего `/opt/marketfusion` на `codex-vps-2`. Проверить свободное место, память/swap и контейнеры. Не трогать Nginx, HTTPS, SSH, Finland SOCKS5 и другие проекты.
2. Создать приватный архив PostgreSQL (`pg_dump -Fc`), `.env`, Compose, образов/их ID и профиля единственного Chrome. Проверить размер/контрольные суммы и восстановление в отдельную БД. Архив хранить вне Git с ограниченными правами. Сохранить локально таблицу количества пользователей, избранного, сессий, AI providers/routes и watches до/после.
3. Построить проверенные V2-образы заранее. Остановить старые bot и worker на время переключения; только один poller может использовать токен. Сохранить существующие volumes. Миграции выполняются транзакционно при старте под advisory lock, версии — в `schema_migrations`. Ошибка миграции запрещает дальнейшее переключение.
4. Запустить API/Web, проверить health, Telegram HMAC и веб-сессию, роли, старое избранное и отсутствие потерь. Старые текстовые watches должны остаться видимыми с `needs_selection`; автоматически включать их нельзя. Проверить заданный регион. Только затем включить один worker и один bot через существующий SOCKS5.
5. Пройти живую приёмку: точный товар, несовместимый вариант, частичный отказ, доставка, история, порог/дедупликация, уведомление, фото/ИИ/отзывы и администрирование. Контролировать OOM, swap, время ответа и рост БД. Неподтверждённые источники не помечать рабочими.
6. Записать SHA, проверки, известные ограничения, копии до/после и итог в `.memory`. Прекратить переключение при расхождении данных или критической регрессии.

## Откат

Сначала остановить V2 bot/worker, чтобы прекратить новые записи и не получить два poller. Вернуть сохранённые образы/SHA и конфигурацию, сохраняя БД и тома. Новые таблицы добавлены отдельно и не требуют удаления для возврата старого кода. Старые watches были намеренно приостановлены миграцией: откат кода не должен молча активировать небезопасный текстовый мониторинг.

Если нужен именно возврат данных к моменту архива, сначала восстановить архив в новую БД и проверить её; переключение DATABASE_URL выполнять в согласованное окно после учёта всех новых записей. Не выполнять автоматический `DROP DATABASE`, `down -v` или очистку production. Восстановление старого архива поверх работающей базы может потерять новые данные и требует отдельного решения владельца. После отката повторить health, авторизацию, избранное, поиск и singleton polling. Удаление V2-таблиц не является обязательной частью отката.


## Продолжение 16 ноября

VPS временно недоступны по сообщению владельца. Не запускать серверные скрипты до восстановления доступа; V2 не развёрнута, свежий production dump не получен. `backup_production_readonly.py` подготовлен, но успешный live backup/restore им пока не подтверждён.

Локальные read-only проверки настоящих источников:

```powershell
python deployment/scripts/check_v2_live_flow.py
python deployment/scripts/check_v2_reviews.py
python deployment/scripts/check_v2_live_ui.py
```

Первый сценарий сохраняет реальные результаты/избранное/watch в отдельной staging-БД и запускает ровно одно измерение выбранного watch, без Telegram send/LLM. Второй читает ограниченную выборку отзывов; статус 503 фиксирует недоступность, не означает пустой пул. Оба обращаются к внешним площадкам. Для smoke без новых внешних запросов использовать check_v2_staging.py.

В текущем worktree тестовый PG имеет динамический host port, который меняется после перезапуска Docker:

```powershell
$testDbBinding=(docker port marketfusion-v2-test-db 5432/tcp | Select-Object -First 1)
$testDbPort=($testDbBinding -split ':')[-1]
$env:MARKETFUSION_TEST_DATABASE_URL="postgresql://postgres:local-v2-test@127.0.0.1:${testDbPort}/marketfusion_v2_test"
```

Это локальный тестовый контейнер; не использовать эту конфигурацию для production. На Windows с заблокированным npm.ps1 использовать npm.cmd либо прямые node node_modules/typescript/bin/tsc --noEmit и node node_modules/vite/bin/vite.js build. V2_UI_URL должен указывать на реально запущенный локальный Web/Vite, например http://127.0.0.1:8089.
