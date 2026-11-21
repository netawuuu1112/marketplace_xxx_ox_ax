# MarketFusion V2 на codex-russia

Отдельное развёртывание Ubuntu 24.04 в `/opt/marketfusion`. Провайдер выдаёт VPS частный IPv4. Вход проверен через SSH alias `codex-russia` (внешний порт 51678). С внешнего адреса через 80, 443 и 8080 не получен ответ временного слушателя. Домен `marketfusionai.kosmo-connect.ru` при проверке резолвился в прежний IP. До подтверждения входящего HTTPS Web публикуется на `127.0.0.1:8080` внутри VPS.

На Windows открыть туннель и перейти на http://127.0.0.1:8189:

```powershell
ssh -N -o ExitOnForwardFailure=yes -L 127.0.0.1:8189:127.0.0.1:8080 codex-russia
```

В другом окне PowerShell можно скопировать пароль в буфер обмена без печати на экран:

```powershell
ssh codex-russia 'sed -n s/^WEB_ADMIN_PASSWORD=//p /opt/marketfusion/.env' | Set-Clipboard
```

`.env` на сервере хранится с правами `0600`. PostgreSQL и профиль Chromium хранятся в именованных томах Docker. Docker включён при загрузке, а контейнеры используют `restart: unless-stopped`. Бот вынесен в профиль `telegram`; для него нужны подтверждённый доступ к Telegram Bot API, действующий токен, HTTPS Mini App и подтверждение, что этот токен не обслуживает другой процесс.

Чтобы проверить запуск без пользовательских данных в выводе:

```sh
cd /opt/marketfusion
docker compose -f docker-compose.yml -f docker-compose.browser.yml ps
python3 deployment/scripts/check_v2_vps.py
python3 deployment/scripts/check_v2_vps.py --sources yandex_market,wildberries,avito,dns,aliexpress
```

Откат кода выполняется с сохранением `.env` и томов. Сначала зафиксировать текущий SHA, образы и сделать резервную копию БД. Затем переключиться на ранее проверенный SHA, запустить `docker compose ... up -d --build` и повторить проверки. Переключение коммита не откатывает миграции и данные. Восстановление делать в отдельную БД перед переключением приложения. Для остановки используется `docker compose ... stop`, тома при этом сохраняются.
