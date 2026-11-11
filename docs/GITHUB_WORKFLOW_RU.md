# Работа с GitHub

Основной репозиторий: `https://github.com/netawuuu1112/marketplace_xxx_ox_ax`.

## Новый компьютер

Установите Git, Docker Desktop или Docker Engine с Compose. Затем:

```bash
git clone https://github.com/netawuuu1112/marketplace_xxx_ox_ax.git
cd marketplace_xxx_ox_ax
git switch develop
git pull --ff-only origin develop
cp .env.example .env
```

Заполните `.env` собственными секретами. Этот файл не отправляется в Git.

## Новая задача

```bash
git switch develop
git pull --ff-only origin develop
git switch -c feature/my-task
# внести изменения
git add .
git commit -m "Добавить описание изменения"
git push -u origin feature/my-task
```

Используйте `fix/*` для исправления ошибок, `release/*` для подготовки релиза, `hotfix/*` для срочной правки стабильной версии. Создайте Pull Request из рабочей ветки в `develop`; после проверки объедините его через GitHub. В `main` переносите только проверенный релиз отдельным Pull Request.

## История и возврат

```bash
git log --oneline --decorate -20
git tag --list
git show v1.0.0
git revert <sha_ошибочного_коммита>
git push origin develop
```

Для скачивания старой версии без изменения рабочей ветки: `git clone --branch v1.0.0 --depth 1 https://github.com/netawuuu1112/marketplace_xxx_ox_ax.git old-version`. Не используйте `git reset --hard` или `push --force` для опубликованной стабильной истории.

## Релиз и VPS

После полного интеграционного прогона откройте Pull Request `develop` → `main`. После объединения создайте тег `git tag -a v1.0.0 -m "MarketFusion AI 1.0.0"`, отправьте `git push origin v1.0.0` и опубликуйте GitHub Release с изменениями, инструкцией обновления и отката.

На VPS храните `.env` и данные PostgreSQL отдельно от Git. Перед обновлением выполните `./backup.sh`, затем `./update.sh`. Для возврата к прошлому коду переключитесь на предыдущий релиз (`git switch --detach v1.0.0`) и пересоберите контейнеры. Если менялась схема базы, восстановите соответствующую резервную копию через `./restore.sh backups/marketfusion-....dump`. Проверяйте совместимость схемы перед возвратом. Номер развернутого тега фиксируйте в журнале эксплуатации.
