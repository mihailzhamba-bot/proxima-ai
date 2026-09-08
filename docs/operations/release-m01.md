# Runbook первого релиза M-01

Обновлено 08.09.2026: сверен с `origin/main` (`f45243e`, миграции 001-018) и с боевым сервером только чтением (`docs/state/RELEASE-READINESS-1.14.md`, §5 и блокер B3); что и почему изменилось - раздел «Сверка 08.09.2026» внизу. Исполняет Mike на VPS `proxima` (135.106.186.210) под `proxima-admin`. Дата релиза - вт 15.09.2026 по D33 (PR #89); слово «деплой» в чате в день релиза (D7). Каждая команда - копипаста, под каждой сказано, что должно появиться в ответ. Если ответ другой - не импровизировать, а идти в раздел 7 «Откат».

**Разделы идут строго по порядку.** Порядок - не стилистика: бэкфилл до первого `collect`, включение таймеров после SUCCEEDED бэкфилла. Нарушение порядка ломает ряд, а не просто задерживает релиз.

Перед первой командой: план отката (раздел 7) прочитан, тег `v2026.09.0-baseline` из раздела 0 создан. Без него откатываться некуда.

**Три формы доступа, которые повторяются ниже.**

- **SELECT по ledger миграций** (раздел 0, 2) - `sudo proxima-psql-readonly` с SQL на stdin: роль `proxima_diagnostics`, установлен на сервере (`/usr/local/sbin/`, исходник `infra/bootstrap/proxima-psql-readonly`), не зависит от compose и `.env`.
- **SELECT по таблицам лестницы** (`fact_cabinet_daily_current`, `data_status_current`, `collector_runs`; разделы 4, 7, 8) - psql владельца внутри контейнера, форма `psqlp` из `docs/state/WORKS-TODAY.md`, SQL на stdin: `sudo docker exec -i proxima-ai-postgres-1 sh -c 'psql -U "$(cat /run/secrets/postgres_user)" -d proxima -v ON_ERROR_STOP=1 -tA'`. У `proxima_diagnostics` грантов на таблицы 011+ нет (их получают только роли `proxima_*`), а `data_status_current` требует `set_config('proxima.tenant_id', …)` в той же сессии (`db/migrations/013_fact_cabinet_daily.sql:49`) - поэтому stdin, а не `-c`. Роли `postgres` в боевой базе **нет**: суперпользователь один, его имя лежит в `/etc/proxima-ai/secrets/postgres_user` (проверено 08.09: `SELECT rolname FROM pg_roles WHERE rolsuper` - одна строка, не `postgres`).
- **Compose** - всегда из `/srv/proxima-ai/repo` и без `-f`: файл compose и `PROXIMA_SECRETS_DIR` приходят из `/srv/proxima-ai/repo/.env` (`COMPOSE_FILE=infra/compose.yaml`, раздел 1.1). Это та же форма, которой compose ищут `tools/morning_run.sh`, `tools/restore_check.sh` и юниты (`WorkingDirectory=/srv/proxima-ai/repo`), - раздел 2 заодно проверяет, что она работает.

## 0. Оживить чекаут на сервере

На 08.09 боевой чекаут `/srv/proxima-ai/repo` стоит на `fd95fcb` в detached HEAD, дерево чистое, **remote пуст** - `git pull` там невозможен физически (проверено `sudo git -C /srv/proxima-ai/repo remote -v` → пусто).

```bash
sudo git -C /srv/proxima-ai/repo log --oneline -1
sudo git -C /srv/proxima-ai/repo status --short
```
Ожидается `fd95fcb Revert "fix: enforce READ-only Analytics token…"` и пустой `status`. Другой коммит или непустой статус - значит на сервер уже кто-то ходил; остановиться и разобраться.

```bash
sudo git -C /srv/proxima-ai/repo tag v2026.09.0-baseline
sudo git -C /srv/proxima-ai/repo tag --list 'v2026.09.*'
```
Ожидается `v2026.09.0-baseline`. Это единственная точка возврата.

```bash
sudo git -C /srv/proxima-ai/repo remote add origin https://github.com/mihailzhamba-bot/proxima-ai.git
sudo git -C /srv/proxima-ai/repo fetch origin --tags
sudo git -C /srv/proxima-ai/repo checkout <релизный тег>
sudo git -C /srv/proxima-ai/repo log --oneline -1
ls /srv/proxima-ai/repo/db/migrations/ | tail -1
```
Релизный тег - `v2026.09.NN-2` по AC Story 1.14, `NN` = день деплоя: по D33 (PR #89) это вт 15.09.2026, то есть `v2026.09.15-2`. Ставится на `main` за сутки до релиза и записывается здесь и в `CHANGELOG.md` (раздел 8). На 08.09 тега ещё нет (`git ls-remote --tags origin` → пусто). Ожидается коммит тега и `018_nm_daily.sql` - последняя миграция в `main` на 08.09 (Story 4.0, PR #95). Если в теге файлов больше, номер последней миграции - ожидание раздела 2.

**Проверить, что применено в боевой базе:**
```bash
printf 'SELECT version, name FROM schema_migrations ORDER BY version;\n' | sudo proxima-psql-readonly
```
Ожидается ровно шесть строк, `1|bootstrap` … `6|raw_artifact_headers` (проверено 08.09). Всё, что выше - 007…018 - применяется в разделе 2. Если там уже есть 007+, миграции применяли вручную: остановиться, это меняет план.

> Почему не `docker compose exec -T postgres psql`: без `PROXIMA_SECRETS_DIR` в окружении compose падает на интерполяции `secrets:` (`error while interpolating secrets.postgres_user.file: required variable PROXIMA_SECRETS_DIR is missing a value`, проверено 08.09), а `.env` правится только в разделе 1. Роли `postgres`, которую звала старая команда, в базе нет.

## 1. Подготовка: окружение, токены, секреты, роли

### 1.1. `.env` и `jobs.env`

`/srv/proxima-ai/repo/.env` (14.08.2026, `0600 proxima-admin`) держит 12 переменных старого контура и не содержит ни `PROXIMA_SECRETS_DIR`, которого требует `infra/compose.yaml` (`${PROXIMA_SECRETS_DIR:?…}`), ни `WEBAPP_DATA_MODE`/`WEBAPP_TENANT_ID` (overlay `infra/webapp.staging.compose.yaml`), ни `COMPOSE_FILE`. Tracked `infra/jobs.env` уже содержит контейнерные пути к raw-каталогу, spool и analytics-токену. Значения хостовых переменных - из `infra/local.env.example`; секретов здесь нет, только пути.

```bash
sudo grep -o '^[A-Za-z_]*=' /srv/proxima-ai/repo/.env | sort | tr '\n' ' '; echo
```
Ожидается ровно 12 имён: `POSTGRES_DB= POSTGRES_HOST= POSTGRES_PASSWORD_FILE= POSTGRES_PORT= POSTGRES_USER_FILE= PROXIMA_RAW_DIR= PROXIMA_SPOOL_DIR= WB_ANALYTICS_TOKEN_FILE= WB_FINANCE_TOKEN_FILE= WB_PRICES_TOKEN_FILE= WB_PROMOTION_TOKEN_FILE= WB_STATISTICS_TOKEN_FILE=`. Есть `PROXIMA_SECRETS_DIR=` или `COMPOSE_FILE=` - файл уже правили, остановиться.

```bash
sudo cp -a /srv/proxima-ai/repo/.env /var/backups/proxima/repo.env-v2026.09.0-baseline
sudo sed -i 's|^PROXIMA_RAW_DIR=.*|PROXIMA_RAW_DIR=/srv/proxima-ai/raw|' /srv/proxima-ai/repo/.env
sudo tee -a /srv/proxima-ai/repo/.env >/dev/null <<'EOF'
COMPOSE_FILE=infra/compose.yaml
PROXIMA_SECRETS_DIR=/etc/proxima-ai/secrets
WEBAPP_DATA_MODE=fixtures
WEBAPP_TENANT_ID=amirova-test
EOF
sudo grep -n '^PROXIMA_\|^COMPOSE_FILE\|^WEBAPP_' /srv/proxima-ai/repo/.env /srv/proxima-ai/repo/infra/jobs.env
```
Ожидается в `.env`: `PROXIMA_RAW_DIR=/srv/proxima-ai/raw`, `PROXIMA_SPOOL_DIR=…` (старая), `COMPOSE_FILE=infra/compose.yaml`, `PROXIMA_SECRETS_DIR=/etc/proxima-ai/secrets`, `WEBAPP_DATA_MODE=fixtures`, `WEBAPP_TENANT_ID=amirova-test`; tracked `infra/jobs.env` уже задаёт контейнерные `PROXIMA_RAW_DIR=/srv/proxima-ai/raw`, `PROXIMA_SPOOL_DIR=/srv/proxima-ai/raw/wb-async-spool` и `WB_ANALYTICS_TOKEN_FILE=/run/secrets/amirova-test_wb_analytics_token`; его на сервере не дописывать. Копия старого `.env` лежит рядом с дампами - к ней возвращается раздел 7.

Что важно знать про эти строки:

- `COMPOSE_FILE=infra/compose.yaml` - compose из `/srv/proxima-ai/repo` без `-f` иначе не находит файл (`no configuration file provided: not found`, проверено 08.09 из этого каталога), а именно так его зовут `tools/morning_run.sh`, `tools/restore_check.sh`, `tools/funnel_v3_run.sh` и юниты. Compose читает `COMPOSE_FILE` из `.env` текущего каталога (проверено 08.09 на копии `infra/` в scratch-каталоге, compose 2.40.3).
- `PROXIMA_RAW_DIR=/srv/proxima-ai/raw`, а не старый `/srv/proxima-ai/data/day1-wb-api`: CAS требует каталог `0700` без symlink (`services/collector/src/wb/cas-artifact.ts:32-38`, `raw-store.ts` `ensurePrivateDirectory`), старый каталог - `0750`, а его родитель `/srv/proxima-ai/data` тоже `0750 proxima-admin`, куда uid 1010 не войдёт. `/srv/proxima-ai` - `0755`, поэтому `/srv/proxima-ai/raw` контейнеру доступен. Значение - `infra/local.env.example:24`; каталог создаётся в 1.3.
- `WEBAPP_DATA_MODE=fixtures` - витрина в 1.14 не переключается (строка статуса на `/brief` - релиз 2.6); переменная нужна, чтобы шагу отката (раздел 7) было что возвращать, и overlay `webapp.staging.compose.yaml` в 2.6 её уже ждал.
- `infra/jobs.env` - tracked-файл: после правки `git status --short` покажет ` M infra/jobs.env`. Это ожидаемо (комментарий в самом файле: host-side edit без пересборки); раздел 7 объясняет, как вернуть.
- Побочный эффект: хостовые цели `make probe-wb-api` / `wb-async-report` / `apply-migrations` без `ENV_FILE` читают `.env` через allowlist `SAFE_ENV_KEYS` (`tools/wb_async_report.py:70`) и после добавления `COMPOSE_FILE`/`WEBAPP_*` откажут `unsupported env key`. В релизе они не используются: миграции идут в контейнере с `infra/jobs.env` (раздел 2), где все ключи - из allowlist.

```bash
cd /srv/proxima-ai/repo && sudo docker compose --profile jobs config --services
```
Ожидается четыре сервиса: `postgres`, `collector`, `control-plane`, `control-plane-admin` (порядок любой). Ошибка интерполяции - `.env` не дописан, вернуться на шаг выше.

### 1.2. Токены и owner-секреты

Токены переименовываются под схему `<tenant>_wb_<category>_token` и отдаются пользователю контейнеров `1010`. Uid 1010 - номинальный пользователь образов (`services/collector/Dockerfile`: `useradd --uid 1010 proxima-jobs` внутри образа); на хосте записи в `/etc/passwd` нет (`getent passwd 1010` → пусто), и это нормально: `chown 1010:1010` работает по числу, а compose биндит secret-файлы «как есть» (`infra/compose.yaml`: «Secret-файлы на хосте - 1010:1010 0600 (AD-6)»).

```bash
sudo ls -la /etc/proxima-ai/secrets/
```
Ожидаются `wb_analytics_token`, `wb_finance_token`, `wb_statistics_token` (`-rw------- proxima-admin`) и `postgres_user`, `postgres_password` (на 08.09 - `-rw-r----- root:proxima-monitor`). **Значения не выводить** - только `ls`.

```bash
cd /etc/proxima-ai/secrets
sudo mv wb_statistics_token amirova-test_wb_statistics_token
sudo mv wb_analytics_token  amirova-test_wb_analytics_token
sudo mv wb_finance_token    amirova-test_wb_finance_token
sudo chown 1010:1010 amirova-test_wb_*_token postgres_user postgres_password
sudo chmod 0600 amirova-test_wb_*_token postgres_user postgres_password
sudo ls -la /etc/proxima-ai/secrets/amirova-test_wb_* /etc/proxima-ai/secrets/postgres_user /etc/proxima-ai/secrets/postgres_password
```
Ожидается пять файлов, владелец `1010:1010`, права `-rw-------`. `postgres_user`/`postgres_password` входят в список потому, что `control-plane-admin` (USER 1010) читает их как `/run/secrets/*` при `apply-migrations`, а `read_secret(private_only=True)` отказывает файлу с битами группы (`tools/wb_async_report.py`, маска `0o077`); CI делает то же самое (`.github/workflows/images.yml:67-68`). Группа `proxima-monitor` ничего не теряет: каталог `/etc/proxima-ai/secrets` - `drwx------ root`, группа в него и так не входит, а `host_monitor.py` читает только `telegram_*` (`infra/monitoring/host_monitor.py:328-329`). Бэкап-скрипт (`root` из cron) читает как читал.

> **Открытый вопрос перед этим шагом.** По OQ-10 analytics-токен боевого кабинета ежедневно использует неизвестный потребитель вне VPS, ротация на read-only (PA-13) обязательна до релиза 2.6 (D32; срок в Jira - до 22.09 по D33). Переименование токен не ротирует. Для 1.14 `collect` идёт на statistics-токене, analytics-токен в этом релизе ни один включённый юнит не трогает.

### 1.3. Каталог сырых артефактов

```bash
sudo install -d -m 0700 -o 1010 -g 1010 /srv/proxima-ai/raw
sudo stat -c '%A %u:%g %n' /srv/proxima-ai/raw
```
Ожидается `drwx------ 1010:1010 /srv/proxima-ai/raw`. На 08.09 каталога нет.

### 1.4. Роли базы (первый прогон - до миграций)

`infra/bootstrap/provision-runtime-roles.sh` без аргументов не запускается: обязательны `--psql <исполняемый psql>` и `--secrets-dir` (строки 66-68 скрипта, usage в шапке). На хосте `psql` нет (`which psql` → пусто); по замыслу скрипта на VPS psql зовётся внутри контейнера postgres. Обёртка ниже - временная, в `main` её нет (проверено 08.09: в `/usr/local/sbin/` только `proxima-psql-readonly`); кандидат в `infra/bootstrap/` отдельной единицей. Пароль владельца читается внутри контейнера из `/run/secrets` и хост не покидает.

```bash
sudo tee /usr/local/sbin/proxima-psql-owner >/dev/null <<'EOF'
#!/usr/bin/env bash
# Релиз 1.14: psql владельца внутри контейнера postgres для provision-runtime-roles.sh (--psql).
# Пароль берётся из /run/secrets внутри контейнера; в main этой обёртки нет (кандидат в infra/bootstrap/).
set -euo pipefail
exec docker exec -i proxima-ai-postgres-1 sh -c \
  'PGPASSWORD="$(cat /run/secrets/postgres_password)" exec psql "$@"' sh "$@"
EOF
sudo chmod 0755 /usr/local/sbin/proxima-psql-owner
printf 'SELECT 1;\n' | sudo /usr/local/sbin/proxima-psql-owner --host postgres --port 5432 \
  --username "$(sudo cat /etc/proxima-ai/secrets/postgres_user)" --dbname proxima --no-psqlrc -tA
```
Ожидается `1`. Форма `docker exec -i … sh -c 'PGPASSWORD=… exec psql "$@"' sh <args>` проверена 08.09 с теми же флагами.

Почему `--host postgres`, а не `127.0.0.1`: скрипт одним значением `--host` и подключается сам, и пишет URI-файлы `<роль>_uri`, которые потом читают контейнеры; для них база - это `postgres:5432` (`infra/jobs.env`, CI-заглушки `images.yml:64-66`). Внутри контейнера `127.0.0.1` пускает без пароля (trust), а `postgres` - только по паролю (`fe_sendauth: no password supplied`, проверено 08.09), поэтому обёртка подставляет `PGPASSWORD`.

```bash
sudo bash /srv/proxima-ai/repo/infra/bootstrap/provision-runtime-roles.sh \
  --psql /usr/local/sbin/proxima-psql-owner --secrets-dir /etc/proxima-ai/secrets \
  --host postgres --port 5432 --database proxima \
  --admin-user "$(sudo cat /etc/proxima-ai/secrets/postgres_user)"
```
Ожидается (порядок строк как в скрипте): `provision-runtime-roles: login roles and grants on postgres:5432/proxima`, `… ensuring database proxima_test`, `… secrets owned by 1010:1010`, затем **предупреждение** `WARNING ledger group roles missing, memberships deferred (re-run after migration 011): …` - на этом шаге миграции 011+ ещё не применены, это ожидаемо, - и итоговая `provision-runtime-roles: ok (5 login roles, database proxima_test, URI files under /etc/proxima-ai/secrets; no secret value printed)`. Второй прогон - в разделе 2 после миграций: он выдаёт членства в группах и `GRANT DELETE` janitor'у (без него не работает `delete_run.py` из раздела 7). Скрипт идемпотентен.

Побочные эффекты, которые скрипт делает по AD-11/AD-12 и которые надо знать: каталог `/etc/proxima-ai/secrets` становится `1010:1010 0700`; `REVOKE CONNECT ON DATABASE proxima FROM PUBLIC` - роли без явного гранта (`proxima_dev`) теряют вход в `proxima`; `proxima_diagnostics` вход сохраняет (явный `GRANT CONNECT` в `provision-postgres-diagnostics.sh:77`), `proxima-psql-readonly` продолжает работать.

## 2. Деплой без таймеров

Таймеры на этом шаге **не включаются**. Сначала данные, потом расписание.

```bash
cd /srv/proxima-ai/repo
sudo docker compose --profile jobs build
```
Ожидается сборка образов `collector`, `control-plane`, `control-plane-admin` без ошибок (сеть: `npm ci` и `uv sync` внутри сборки).

```bash
cd /srv/proxima-ai/repo
sudo docker compose --profile jobs run --rm control-plane-admin make apply-migrations ENV_FILE=infra/jobs.env
```
Это форма AC Story 1.13 («`apply-migrations` через `control-plane-admin`»), спайна (Conventions, `sudo docker compose --profile jobs run --rm control-plane-admin make apply-migrations ENV_FILE=infra/jobs.env`) и CI (`images.yml:94`): owner-секреты живут только в этом сервисе (AD-15). Работающий контейнер postgres уже в сети `proxima-ai-private` (имя сети не менялось с `fd95fcb`), поэтому миграции идут до пересоздания контейнера. Ожидается одна строка `migrations: 007_quality_lineage_facts.sql, 008_release_records.sql, …, 018_nm_daily.sql` - двенадцать имён файлов. `migrations: already current` - миграции уже применяли, остановиться.

```bash
printf 'SELECT count(*), max(version) FROM schema_migrations;\n' | sudo proxima-psql-readonly
```
Ожидается `18|18` - число и номер последней миграции релизного тега (на 08.09 - `018_nm_daily.sql`; в разделе 0 проверено, что в теге нет более поздней).

```bash
sudo bash /srv/proxima-ai/repo/infra/bootstrap/provision-runtime-roles.sh \
  --psql /usr/local/sbin/proxima-psql-owner --secrets-dir /etc/proxima-ai/secrets \
  --host postgres --port 5432 --database proxima \
  --admin-user "$(sudo cat /etc/proxima-ai/secrets/postgres_user)"
```
Второй прогон. Ожидается без `WARNING`: `provision-runtime-roles: memberships granted for every ledger group role` и та же итоговая строка `ok (5 login roles, …)`. Это и есть проверка «provision идемпотентен» из AC 1.14: два прогона, второй ничего не ломает.

```bash
cd /srv/proxima-ai/repo
sudo docker compose up -d postgres
sudo docker ps --format '{{.Names}}\t{{.Status}}' | grep postgres
```
Compose в `fd95fcb` не знал bridge-порта `172.17.0.1:5432`, релизный знает - контейнер пересоздаётся, около десяти секунд база недоступна, это ожидаемо. Ожидается `proxima-ai-postgres-1  Up … (healthy)`.

## 3. Бэкфилл истории

**Сначала сверить артефакты.** Единственная копия истории до окна WB лежит вне git (D15).

```bash
cd ~/signal-inputs/fixtures/wb-api/statistics
sha256sum supplier-sales/20260831T155341Z__dateFrom-2023-01-01_flag-0.json \
          supplier-orders/20260831T155341Z__dateFrom-2023-01-01_flag-0.json
```
Ожидается ровно:
```
d2f1dc9581ad1f1ab67d1f7ac874b1fa93109915a06d3b09505d960e0b65ec96  supplier-sales/...
0c0318ff835d59e263a32cd1f565d8f899e28173e4eacc942c414756214daa40  supplier-orders/...
```
Совпало 08.09 (4/4 файла обеих пар, `docs/state/RELEASE-READINESS-1.14.md` §5). Не совпало - **остановиться**: сверять цифры релиза будет не с чем.

> Берётся пара от **31.08**, а не от 30.08: `docs/state/API-FACTS.md` («Артефакты для бэкфилла») говорит, что бэкфилл берёт самую свежую пару, и снимок 31.08 снят именно как страховка непрерывности ряда. В тексте историй 1.13/1.14 упоминается пара 30.08 - расхождение формулировок, факт в `API-FACTS.md`.

**Инструменты на хосте для импорта.** `tools/cas_import.ts` в образ коллектора не входит (`services/collector/Dockerfile` копирует только `contracts` и `services/collector`), поэтому импорт идёт на хосте: `node` v22.23.2 и `npx` есть (`/usr/bin`), а `tsx` появляется после установки зависимостей в чекаут (на 08.09 `services/collector/node_modules` нет, корневой `node_modules` - от старого чекаута). Под `proxima-admin`, с сетью:

```bash
cd /srv/proxima-ai/repo
PUPPETEER_SKIP_DOWNLOAD=1 npm ci --workspace @proxima/collector --include-workspace-root
ls node_modules/.bin/tsx
```
Та же команда, что в стадии `deps` Dockerfile коллектора. Ожидается `node_modules/.bin/tsx`.

**Импорт в CAS.** Запускается от `root`: репозиторий и `~/signal-inputs` - `0750`/`0700 proxima-admin`, а uid 1010 на хосте не существует, так что `sudo -u '#1010'` прочитать их не сможет. Файлы кладутся в `/srv/proxima-ai/raw` (раздел 1.3) и после импорта отдаются контейнерному пользователю.

```bash
cd /srv/proxima-ai/repo
sudo env PROXIMA_RAW_DIR=/srv/proxima-ai/raw node_modules/.bin/tsx tools/cas_import.ts \
  /home/proxima-admin/signal-inputs/fixtures/wb-api/statistics/supplier-sales/20260831T155341Z__dateFrom-2023-01-01_flag-0.json \
  --retrieved-at 2026-08-31T15:53:41Z --source official_wb_statistics
sudo env PROXIMA_RAW_DIR=/srv/proxima-ai/raw node_modules/.bin/tsx tools/cas_import.ts \
  /home/proxima-admin/signal-inputs/fixtures/wb-api/statistics/supplier-orders/20260831T155341Z__dateFrom-2023-01-01_flag-0.json \
  --retrieved-at 2026-08-31T15:53:41Z --source official_wb_statistics
sudo chown -R 1010:1010 /srv/proxima-ai/raw
sudo find /srv/proxima-ai/raw -maxdepth 2 -printf '%M %u:%g %p\n'
```
Каждый вызов печатает одну JSON-строку `{"content_sha256": "…", "object_locator": "artifact://business-signal/sha256/…", "retrieved_at": "2026-08-31T15:53:41.000Z"}` - `content_sha256` должен совпасть со сверенным выше. `find` показывает `objects/`, `imports/`, `tmp/` с `drwx------ 1010:1010` и файлы `-rw------- 1010:1010`. Инструмент отказывает, если каталог не `0700` или лежит внутри git-дерева (`cas-artifact.ts`: `CAS root must stay outside Git`).

**Бэкфилл из артефактов.** Задание в контейнере, форма вызова - `npm run <job> -- …` (Dockerfile коллектора без ENTRYPOINT, PR #90). Compose сам монтирует `${PROXIMA_RAW_DIR}` в контейнерный `/srv/proxima-ai/raw`, поэтому ручной `-v` не нужен.

```bash
cd /srv/proxima-ai/repo
sudo docker compose --profile jobs run --rm \
  collector npm run backfill -- --tenant amirova-test \
  --source artifact:d2f1dc9581ad1f1ab67d1f7ac874b1fa93109915a06d3b09505d960e0b65ec96,0c0318ff835d59e263a32cd1f565d8f899e28173e4eacc942c414756214daa40
```
`PROXIMA_RAW_DIR` внутри контейнера приходит из `infra/jobs.env` (раздел 1.1), URI роли - из `/run/secrets/proxima_collector_uri` (раздел 1.4). `run_day` берётся из манифеста CAS и будет `2026-08-31`; версии пишутся по `2026-08-30` включительно. Ожидается JSON-лог по шагам, строка `backfill committed` с `run_day`, `days`, `orders_inserted`, `sales_inserted` и последняя строка `{"run_id": "…", "tenant_id": "amirova-test", "kind": "backfill", "run_day": "2026-08-31", …}`; статус прогона - SUCCEEDED (проверка SQL в разделе 4). Тенант `amirova-test` в `tenants` есть (проверено 08.09).

**Живой хвост с перекрытием.** Compose монтирует tenant-prefixed statistics-токен в `/run/secrets/amirova-test_wb_statistics_token`; этот же контейнерный путь передаёт runner. Живые вызовы WB разрешает флаг `WB_ALLOW_LIVE_NETWORK: "1"` из `environment:` сервиса `collector` в `infra/compose.yaml` (AD-4: транспорт fail-closed, тесты сети не видят; гейт `make live-network`). Перед хвостом убедиться, что релизный compose его несёт:

```bash
cd /srv/proxima-ai/repo && sudo docker compose --profile jobs config | grep -c 'WB_ALLOW_LIVE_NETWORK: "1"'
```
Ожидается `1`. Ноль - compose без флага (до фикса 08.09): первый же HTTP-вызов упадёт с `WB_NETWORK_FORBIDDEN`; остановиться и вернуться к разделу 0 (чекаут релизного тега).

```bash
cd /srv/proxima-ai/repo
sudo docker compose --profile jobs run --rm \
  collector npm run collect -- --tenant amirova-test --date-from 2026-08-27 \
  --statistics-token-file /run/secrets/amirova-test_wb_statistics_token
```
Ожидается строка `date-from` с `"date_from": "2026-08-27", "source": "flag"`, затем `aggregate` с числом дней и последняя JSON-строка с `run_id`, `kind: collect`; статус SUCCEEDED.

`--date-from 2026-08-27` - значение AC Story 1.13 (CP-1, `epics.md:335`), а не `2026-08-28`, которое стояло здесь раньше. Правило AD-2 - `run_day − 3` артефакта: для пары 30.08, названной в AC, это 27.08; для пары 31.08, которую фактически импортирует раздел 3, - 28.08. Берётся 27.08: оно буквально совпадает с AC, а лишний день перекрытия ничего не портит - наблюдения идемпотентны (`DO NOTHING`, FR2), день получает новую версию по прогону (AD-2/AD-3), `_current` показывает последнюю. Четыре дня перекрытия вместо трёх - это самолечение, а не дубль.

## 4. Проверка цифр

Эталоны - `docs/state/API-FACTS.md`, разделы «Эталоны недельных сумм W10/W35» и «Что означают эталоны» (правило Mike 08.09.2026, ~13:40 UTC, после репетиции D35). Недели - ISO (Story 6.1 Given): W10 = 02.03-08.03.2026, W35 = 24.08-30.08.2026. W10 сверяется суммой недели; W35 - **по дням**, потому что раздел 3 грузит пару 31.08 и переписывает дни с 27.08 живым хвостом: дни 24-26.08 должны равняться паре 31.08, дни 27-30.08 - последним наблюдениям самой базы. То же самое одной командой делает `bash tools/rehearsal_run.sh check` (раздел «Репетиция на VPS»); ниже - ручная форма для боевого контейнера.

**W10 - сумма недели, копейка в копейку.**
```bash
printf '%s\n' "SELECT set_config('proxima.tenant_id','amirova-test',false);
SELECT 'W10', sum(orders_count), sum(revenue_rub) FROM fact_cabinet_daily_current
  WHERE tenant_id='amirova-test' AND calendar_day BETWEEN '2026-03-02' AND '2026-03-08';" \
| sudo docker exec -i proxima-ai-postgres-1 sh -c 'psql -U "$(cat /run/secrets/postgres_user)" -d proxima -v ON_ERROR_STOP=1 -tA'
```
Ожидается `W10|649|700860.50` - пересчёт фикстуры 30.08 по формулам глоссария (`API-FACTS.md`; первая строка `amirova-test` - эхо `set_config`).

**Дни 24-26.08 - равны паре 31.08 точь-в-точь.** Три дня W35 до окна живого хвоста (`--date-from 2026-08-27`); их единственная версия - прогон `backfill` раздела 3, ожидаемые значения - пересчёт пары 31.08 (`jq`, 08.09; БД репетиции дала то же):
```bash
printf '%s\n' "SELECT set_config('proxima.tenant_id','amirova-test',false);
SELECT calendar_day, orders_count, cancelled_count, revenue_rub FROM fact_cabinet_daily_current
  WHERE tenant_id='amirova-test' AND calendar_day BETWEEN '2026-08-24' AND '2026-08-26' ORDER BY calendar_day;" \
| sudo docker exec -i proxima-ai-postgres-1 sh -c 'psql -U "$(cat /run/secrets/postgres_user)" -d proxima -v ON_ERROR_STOP=1 -tA'
```
Ожидается ровно (после эха `amirova-test`):
```
2026-08-24|55|6|62146.87
2026-08-25|40|7|29247.90
2026-08-26|28|4|44956.00
```

**Дни 27-30.08 - равны последним наблюдениям.** Их переписал живой хвост, внешней константы для них нет (WB переключает `isCancel` неделями): факт дня должен равняться счёту строк `stg_wb_orders_latest` за московский день `date` (первые 10 символов бесзонного текста WB, AD-7) с `isCancel` не-true / true - так же считает сам агрегатор:
```bash
printf '%s\n' "SELECT set_config('proxima.tenant_id','amirova-test',false);
WITH obs AS (
  SELECT substr(payload->>'date', 1, 10)::date AS calendar_day,
         count(*) FILTER (WHERE (payload->>'isCancel')::boolean IS NOT TRUE) AS orders_count,
         count(*) FILTER (WHERE (payload->>'isCancel')::boolean IS TRUE) AS cancelled_count
    FROM stg_wb_orders_latest
   WHERE tenant_id='amirova-test' AND substr(payload->>'date', 1, 10) BETWEEN '2026-08-27' AND '2026-08-30'
   GROUP BY 1)
SELECT f.calendar_day, f.orders_count, f.cancelled_count, o.orders_count, o.cancelled_count,
       (f.orders_count = o.orders_count AND f.cancelled_count = o.cancelled_count) AS same
  FROM fact_cabinet_daily_current f
  JOIN obs o ON o.calendar_day = f.calendar_day
 WHERE f.tenant_id='amirova-test' AND f.calendar_day BETWEEN '2026-08-27' AND '2026-08-30'
 ORDER BY f.calendar_day;" \
| sudo docker exec -i proxima-ai-postgres-1 sh -c 'psql -U "$(cat /run/secrets/postgres_user)" -d proxima -v ON_ERROR_STOP=1 -tA'
```
Ожидается четыре строки (27, 28, 29, 30.08) и `t` в последней колонке у каждой. Сами числа в релизе будут не те, что на репетиции 08.09 (`33|5`, `25|18`, `21|8`, `26|6`), - сравнивается только равенство двух пар колонок; меньше четырёх строк - тоже расхождение.

Расхождение - **гейт не пройден**. Не «почти сходится»: цифры либо равны эталону, либо релиз останавливается. Сумма W35 за неделю (225 / 263 089 ₽ снимка 30.08) больше не сверяется: она снята с неполного дня 30.08 и после пары 31.08 невоспроизводима по построению (`API-FACTS.md`, «Что означают эталоны»). Ширина окна перезаписи (какие поздние отмены доходят до факта) - открытый вопрос Story 6.1/6.3, не условие релиза.

```bash
printf '%s\n' "SELECT set_config('proxima.tenant_id','amirova-test',false);
SELECT last_full_day, collected_at, stale FROM data_status_current WHERE tenant_id='amirova-test';
SELECT kind, status, started_at FROM collector_runs WHERE tenant_id='amirova-test' ORDER BY started_at;" \
| sudo docker exec -i proxima-ai-postgres-1 sh -c 'psql -U "$(cat /run/secrets/postgres_user)" -d proxima -v ON_ERROR_STOP=1 -tA'
```
Ожидается `last_full_day` = вчерашняя дата по Москве, `stale = f`, и два прогона `backfill|SUCCEEDED`, `collect|SUCCEEDED`.

Затем прогнать `docs/state/WORKS-TODAY.md` целиком и дописать в него результат этого релиза (ожидание WT-03 станет `18|18`, число таблиц - по факту).

Строка статуса на `/brief` проверяется в релизе 2.6, не здесь.

## 5. Включение таймеров

Только после SUCCEEDED бэкфилла и сошедшихся цифр.

Перед включением проверить, что релизный compose монтирует raw-каталог и tenant-prefixed statistics-токен:
```bash
cd /srv/proxima-ai/repo && sudo docker compose --profile jobs config | grep -n '/srv/proxima-ai/raw\|_wb_statistics_token'
```
Ожидаются обе строки; ноль строк - релизный compose не соответствует AD-6, остановиться и вернуться к разделу 2.

`proxima-morning@` (как и `proxima-funnel-v3@`) получает `WB_ALLOW_LIVE_NETWORK=1` через тот же compose - сервис `collector`, проверка из раздела 3, - а не через `Environment=` юнита: в юниты флаг не добавлять, гейт `make live-network` это запрещает (AD-4).

Установка юнитов (все файлы - из `infra/systemd/` релизного тега, проверены в CI `systemd-verify`):
```bash
sudo install -m 0644 /srv/proxima-ai/repo/infra/systemd/proxima-morning@.service /etc/systemd/system/
sudo install -m 0644 /srv/proxima-ai/repo/infra/systemd/proxima-morning@.timer /etc/systemd/system/
sudo install -m 0644 /srv/proxima-ai/repo/infra/systemd/proxima-restore-check@.service /etc/systemd/system/
sudo install -m 0644 /srv/proxima-ai/repo/infra/systemd/proxima-restore-check@.timer /etc/systemd/system/
sudo install -m 0644 /srv/proxima-ai/repo/infra/systemd/proxima-alert@.service /etc/systemd/system/
sudo install -m 0644 /srv/proxima-ai/repo/infra/systemd/proxima-funnel-v3@.service /etc/systemd/system/
sudo install -m 0644 /srv/proxima-ai/repo/infra/systemd/proxima-funnel-v3@.timer /etc/systemd/system/
sudo install -d -m 0755 /etc/systemd/system/proxima-funnel-v3@.service.d
sudo install -m 0644 /srv/proxima-ai/repo/infra/systemd/proxima-funnel-v3@.service.d/10-analytics-read-write.conf \
  /etc/systemd/system/proxima-funnel-v3@.service.d/10-analytics-read-write.conf
sudo systemctl daemon-reload
sudo systemctl enable --now proxima-restore-check@amirova-test.timer
sudo systemctl enable --now proxima-morning@amirova-test.timer
systemctl list-timers 'proxima*' --all --no-pager
```
Ожидается: `proxima-restore-check@amirova-test.timer` (Пн 06:00 МСК), `proxima-morning@amirova-test.timer` (05:30 МСК, если включён) и уже работавший `proxima-host-monitor.timer`. Утренний гоняет цепочку `collect → norm → brief` строго по порядку со стопом на первой ошибке (AD-6, CR от 03.09); `TimeoutStartSec=55min` несёт крайний срок 06:30 (PA-65).

**Воронка в 1.14 не включается.** `proxima-funnel-v3@.service`/`.timer` устанавливаются (чтобы drop-in ниже относился к существующему юниту), но `enable` для `proxima-funnel-v3@amirova-test.timer` здесь **нет** - шаг воронки едет релизом 2.6 (D33, PR #89; ежедневная воронка - Story 3.1/3.4). `proxima-funnel-csv@.{service,timer}` не устанавливаются и не включаются: в сентябре CSV не собирается (FR9, D23).

Drop-in `10-analytics-read-write.conf` - временное исключение PA-13 (`Environment=PROXIMA_FUNNEL_V3_ALLOW_ANALYTICS_READ_WRITE=1`, D32): пока analytics-токен read-write, `tools/funnel_v3_run.sh` без него откажет. Ставится сейчас, чтобы 2.6 не зависел от этого шага; базовый юнит `proxima-funnel-v3@.service` при установке и снятии исключения не менять (гейт `tools/verify_funnel.py` проверяет, что переменной в нём нет). После ротации на read-only (до 2.6) снять:

```bash
sudo rm /etc/systemd/system/proxima-funnel-v3@.service.d/10-analytics-read-write.conf
sudo systemctl daemon-reload
systemctl cat proxima-funnel-v3@amirova-test.service | grep -c ALLOW_ANALYTICS_READ_WRITE
```
Ожидается `0`. `systemctl restart` здесь **не** делать: юнит `Type=oneshot`, `restart` неактивного oneshot - это запуск воронки, а не перечитывание конфигурации.

## 6. Проверка алерта

Сторож, о котором никто не узнал, сторожем не является.

```bash
sudo systemctl start proxima-alert@test.service
```
Ожидается сообщение в Telegram-канале монитора в течение минуты. Не пришло - разбираться здесь, а не после релиза: `TimeoutStartSec` утреннего юнита несёт крайний срок 06:30, и без работающего алерта его превышение останется незамеченным.

Проверить, что ретрай на месте:
```bash
grep -n "retry" /srv/proxima-ai/repo/tools/proxima_alert.sh
```
Ожидается `--retry 3 --retry-delay 5` (задача PA-65) в комментарии и строки конфига curl `retry = 3`, `retry-delay = 5`. Ретрайит сам curl внутри одного вызова: транспортные ошибки (включая таймаут `max-time = 20`) и ответы HTTP 408/429/5xx повторяются (до 3 попыток, пауза 5 с); остальные 4xx (например, 401 с неверным токеном, 404) - нет: с `fail` скрипт падает с кодом 22 сразу. Отдельного пинга канала в скрипте нет - живость канала проверяется только этим тестовым сообщением: не пришло за минуту (3 попытки по `max-time` = максимум ~80 с) - чинить токен/чат здесь, до релиза.

## 7. Откат

Порядок обратный развёртыванию.

```bash
sudo systemctl disable --now proxima-morning@amirova-test.timer
sudo systemctl disable --now proxima-restore-check@amirova-test.timer
sudo rm -f /etc/systemd/system/proxima-funnel-v3@.service.d/10-analytics-read-write.conf
sudo systemctl daemon-reload
```

Удалить прогоны релиза целиком, по одному:
```bash
printf '%s\n' "SELECT set_config('proxima.tenant_id','amirova-test',false);
SELECT run_id, kind, status, started_at FROM collector_runs
  WHERE tenant_id='amirova-test' ORDER BY started_at DESC LIMIT 20;" \
| sudo docker exec -i proxima-ai-postgres-1 sh -c 'psql -U "$(cat /run/secrets/postgres_user)" -d proxima -v ON_ERROR_STOP=1 -tA'

cd /srv/proxima-ai/repo
sudo docker compose --profile jobs run --rm \
  -v /etc/proxima-ai/secrets/proxima_janitor_uri:/run/secrets/proxima_janitor_uri:ro \
  -e JANITOR_DATABASE_URI_FILE=/run/secrets/proxima_janitor_uri \
  control-plane python tools/delete_run.py --tenant amirova-test --run <uuid> --dry-run
```
`delete_run.py` идёт в контейнере `control-plane` (образ несёт `tools/` и `psycopg`; хостовый `python3` 3.12 без `psycopg`, а `sudo -u '#1010'` не читает репозиторий `0750`). URI janitor'а compose пока не монтирует (комментарий TODO Story 1.12/AD-11 в `infra/compose.yaml`) - отсюда `-v` и `-e`; файл `proxima_janitor_uri` создан provision'ом в разделе 1.4 (`1010:1010 0600`, иначе инструмент откажет «unsafe permissions»). Сначала всегда `--dry-run`: он печатает счётчики транзитивного замыкания. Удаление входного прогона снимает и всё, что на нём построено - так и задумано (AD-3). Убедившись в объёме, повторить без `--dry-run`.

Вернуть витрину на фикстуры - **только если в этом релизе она переключалась** (в 1.14 не переключается: `WEBAPP_DATA_MODE=fixtures` с раздела 1.1, overlay не поднимался, `proxima-webapp-staging` на `127.0.0.1:3000` как был). Если переключалась в 2.6:
```bash
sudo sed -i 's/^WEBAPP_DATA_MODE=.*/WEBAPP_DATA_MODE=fixtures/' /srv/proxima-ai/repo/.env
cd /srv/proxima-ai/repo && sudo docker compose -f infra/compose.yaml -f infra/webapp.staging.compose.yaml up -d webapp
```
`sed` находит переменную, потому что раздел 1.1 её добавил; в `.env` от 14.08 её не было, и старая команда меняла пустоту.

Вернуть код и окружение:
```bash
sudo git -C /srv/proxima-ai/repo checkout -- infra/jobs.env
sudo git -C /srv/proxima-ai/repo checkout v2026.09.0-baseline
sudo cp -a /var/backups/proxima/repo.env-v2026.09.0-baseline /srv/proxima-ai/repo/.env
sudo git -C /srv/proxima-ai/repo log --oneline -1
```
Сначала снять правку `infra/jobs.env` (в `fd95fcb` файла нет, и `checkout` с локальным изменением откажет), потом тег, потом старый `.env` из копии раздела 1.1. Ожидается `fd95fcb …`. Переименованные токены, роли базы, `/srv/proxima-ai/raw` и `proxima-psql-owner` остаются: старому контуру они не мешают, а следующей попытке релиза нужны.

**Миграции не откатываются.** Они additive-only: новые таблицы остаются пустыми и никому не мешают. Попытка откатить миграцию - нарушение AD-14 и способ потерять данные.

## 8. Наблюдение и запись

Три утра подряд (CAP-1) проверять, что прогон завершился SUCCEEDED и `last_full_day` вчерашний:
```bash
printf '%s\n' "SELECT set_config('proxima.tenant_id','amirova-test',false);
SELECT kind, status, finished_at FROM collector_runs
  WHERE tenant_id='amirova-test' ORDER BY finished_at DESC LIMIT 5;
SELECT last_full_day, stale FROM data_status_current WHERE tenant_id='amirova-test';" \
| sudo docker exec -i proxima-ai-postgres-1 sh -c 'psql -U "$(cat /run/secrets/postgres_user)" -d proxima -v ON_ERROR_STOP=1 -tA'
```

Ход релиза фиксируется в `docs/operations/releases/2026-09-15-m01.md` (AC Story 1.14; каталога на 08.09 нет, создаётся вместе с журналом), релиз - в `CHANGELOG.md` в корне репозитория: тег, дата, что вошло, ссылка на этот runbook.

## Репетиция на VPS (D35, не деплой)

Зачем: код коллектора и control-plane из `main` ни разу не прогонялся end-to-end на артефактах 31.08, а боевой контур (схема 6, таймеров нет) до 15.09 не трогается. По D35 (Mike, 08.09) разделы 2-4 этого runbook прогоняются на этом же VPS в **одноразовом compose-проекте** `proxima-rehearsal`; единственное исключение - живой хвост: 2 read-вызова WB (`supplier/orders`, `supplier/sales`) на statistics-токене. Слово «деплой» для репетиции не требуется, но `tail` без явного `--live` не запускается. Инструменты: `infra/compose.rehearsal.yaml` (override к `infra/compose.yaml`) и `tools/rehearsal_run.sh`; оба в `main` после мержа ветки `feat/rehearsal-stack`, боевой `compose.yaml` не меняются.

**Гарантии изоляции** (проверены `docker compose … config` на compose 2.40.3; `!override` для `ports` поддерживается с 2.24.4):

| Что | Боевой контур | Репетиция |
|---|---|---|
| Проект / контейнер postgres | `proxima-ai` / `proxima-ai-postgres-1` | `proxima-rehearsal` / `proxima-rehearsal-postgres-1` |
| Порты postgres | `127.0.0.1:5432` + bridge docker0 `:5432` | только `127.0.0.1:5434` (`ports: !override` - список заменён, а не дописан) |
| Сеть | `proxima-ai-private` | `proxima-rehearsal-private` |
| Том | `proxima-ai_postgres-data` | `proxima-rehearsal_postgres-data` (свежий, удаляется `down -v`) |
| Секреты / raw | `/etc/proxima-ai/secrets`, `/srv/proxima-ai/raw` | `<root>/secrets`, `<root>/raw` (`1010:1010`, `0700`/`0600`) |
| Образы | `proxima-ai-*` | `proxima-rehearsal-*` |
| Перезапуск после ребута | `unless-stopped` | `restart: "no"` |
| Сеть WB у collector | по умолчанию запрещена (AD-4) | `WB_ALLOW_LIVE_NETWORK=${PROXIMA_REHEARSAL_LIVE:-0}` - `1` только в `tail --live` на один запуск |

`<root>` - `/home/proxima-admin/orca/rehearsal` (вне git-дерева: CAS требует raw-каталог вне репозитория; скрипт отказывает на `--root` внутри чекаута и внутри `/srv/proxima-ai*`, `/etc/proxima-ai*`). Из боевого контура читается один файл - statistics-токен, копируется `install` от root в `<root>/secrets/amirova-test_wb_statistics_token`; значение в shell не попадает. Analytics-токен - пустой placeholder (compose требует файл, воронка в репетиции не идёт). Боевая база не открывается ни одной командой: все SQL идут в `proxima-rehearsal-postgres-1`.

Проверка, что боевой контур не изменился (до и после, вывод должен совпасть):
```bash
sudo docker ps --format '{{.Names}}\t{{.Status}}\t{{.Ports}}' | grep proxima-ai
sudo docker compose ls
```
Ожидается `proxima-ai-postgres-1  Up … (healthy)  127.0.0.1:5432->5432/tcp` (аптайм не сбрасывается) и в `compose ls` - `proxima-ai running(1)` рядом с `proxima-rehearsal` на время репетиции.

**Что отличается от релиза 15.09** (ожидания скрипта под это подстроены):

- Свежий том: `infra/compose.yaml` монтирует `db/migrations` в `/docker-entrypoint-initdb.d`, и postgres применяет все миграции при первом старте. Команда раздела 2 `apply-migrations` всё равно выполняется (проверяет owner-секреты, allowlist `jobs.env`, checksum ledger) и отвечает `migrations: already current`; в бою будет список `007…018`. Скрипт затем проверяет `schema_migrations` = `18|18` (число и номер последнего файла в `db/migrations`).
- `provision-runtime-roles.sh` оба прогона идут после миграций - `WARNING … memberships deferred` не появляется ни разу (в бою - в первом прогоне). `--psql` - обёртка `<root>/bin/psql-owner` (форма раздела 1.4, контейнер репетиции). Пароли ролей и URI-файлы (`postgresql://<роль>:<пароль>@postgres:5432/proxima`) создаёт `init`, provision их переиспользует - второй прогон ничего не меняет.
- Строку тенанта `amirova-test` вставляет скрипт (в бою она есть, миграции её не создают).
- `PROXIMA_GIT_SHA` передаётся в задания явно (`run -e`), чтобы в `collector_runs` был виден коммит репетиции.
- Логи шагов - `<root>/logs/*.log` (provision печатает только имена файлов, задания - JSON-шаги; секретов там нет).

**Команды.** Запускать под `proxima-admin` из чекаута с этими файлами (скрипт сам зовёт `sudo -n`; под `sudo bash …` сломается `$HOME` для артефактов - тогда `--artifacts-dir /home/proxima-admin/signal-inputs/fixtures/wb-api/statistics`). Перед каждым шагом можно посмотреть команды: тот же вызов с `--dry-run` (ничего не создаёт и не запускает).

```bash
cd ~/orca/night-wt/rehearsal   # или /srv/proxima-ai/repo после мержа и checkout релизного тега
ROOT=/home/proxima-admin/orca/rehearsal
bash tools/rehearsal_run.sh init --root "$ROOT" --statistics-token-src /etc/proxima-ai/secrets/wb_statistics_token
```
`init` делает `<root>/{secrets,raw,bin,logs,.env}`; `ls -la <root>/secrets` в конце показывает 14 файлов `1010:1010 0600` (`postgres_user`, `postgres_password`, по `<роль>_password` и `<роль>_uri` для пяти ролей, два токена). Имя токена-источника - как на сервере на 08.09 (`wb_statistics_token`); после раздела 1.2 файл называется `amirova-test_wb_statistics_token`. Повторный `init` на существующем `<root>/.env` отказывает.

```bash
bash tools/rehearsal_run.sh up --root "$ROOT"
```
Сборка трёх образов (сеть: `npm ci`, `uv sync`), `up -d --wait postgres`, `apply-migrations` (`already current`), `schema_migrations: 18|18`, два прогона provision с итоговой строкой `ok (5 login roles, database proxima_test, URI files under <root>/secrets; no secret value printed)` и без `WARNING`.

```bash
bash tools/rehearsal_run.sh backfill --root "$ROOT"
```
`sha256sum` пары 31.08 (ожидаются `d2f1dc95…` sales и `0c0318ff…` orders, иначе стоп), при отсутствии `node_modules/.bin/tsx` - `npm ci` из раздела 3, два `cas_import.ts` от root в `<root>/raw` (в JSON-ответе `content_sha256` сверяется с ожидаемым), `chown -R 1010:1010`, вставка тенанта, затем `collector npm run backfill -- --tenant amirova-test --source artifact:…`. Ожидается `backfill committed` с `run_day: 2026-08-31`.

```bash
bash tools/rehearsal_run.sh tail --live --root "$ROOT"
```
**Единственный шаг с живым WB** - 2 read-вызова, исключение D35. `PROXIMA_REHEARSAL_LIVE=1` ставится только на этот `docker compose run`; `collect --tenant amirova-test --date-from 2026-08-27 --statistics-token-file /run/secrets/amirova-test_wb_statistics_token`. Ожидается `"date_from": "2026-08-27", "source": "flag"`, затем `aggregate` и последняя строка с `kind: collect`. Без `--live` скрипт отказывает. Если токен не read-only или даёт больше одной категории - `TOKEN_SCOPE_INVALID` (`services/collector/src/business-signal/secrets.ts:59`): это и есть находка репетиции, а не повод править код.

```bash
bash tools/rehearsal_run.sh steps --root "$ROOT"
bash tools/rehearsal_run.sh check --root "$ROOT"
```
`steps` - `proxima_control_plane.norm run` и `proxima_control_plane.brief run` (модули `tools/morning_run.sh`). `check` печатает ledger (`schema_migrations`, `collector_runs`, `data_status_current`, `norm_daily_current`, `brief_current`) и таблицу гейта §4: W10 против `docs/state/API-FACTS.md` (`649|700860.50`), дни 24-26.08 против пары 31.08 (`55|6|62146.87`, `40|7|29247.90`, `28|4|44956.00`) и дни 27-30.08 против счёта по `stg_wb_orders_latest` (правило Mike 08.09); любое расхождение - exit 1, решение - Mike, не «починить цифру». `all --live --root "$ROOT"` = `up → backfill → tail → steps → check` одной командой; `init` и `down` всегда отдельно.

**Витрина на данных репетиции** (по желанию, после `steps`). Тот же проект с третьим `-f` - overlay `infra/webapp.staging.compose.yaml`; переменные уже в `<root>/.env`: `WEBAPP_DATA_MODE=postgres`, `WEBAPP_TENANT_ID=amirova-test`, `PROXIMA_WEBAPP_PORT=3434` (боевой `proxima-webapp-staging` на 3000 не трогается). URI приходит файлом `/run/secrets/proxima_webapp_uri` (env `WEBAPP_DATA_DATABASE_URI_FILE`, `services/webapp/src/lib/data/postgres-provider.ts:37`): роль `proxima_webapp`, член `proxima_webapp_readonly`, хост `postgres:5432` внутри сети репетиции - файл создан `init`, роль - provision в `up`.
```bash
sudo docker compose --env-file "$ROOT/.env" -p proxima-rehearsal \
  -f infra/compose.yaml -f infra/compose.rehearsal.yaml -f infra/webapp.staging.compose.yaml \
  up -d --build webapp
ssh -N -L 3434:127.0.0.1:3434 proxima   # с машины Mike; затем http://127.0.0.1:3434/brief
```
Хостовый порт `5434` нужен только для клиента с хоста (psql на хосте нет): URI `postgresql://proxima_webapp:<пароль из <root>/secrets/proxima_webapp_password>@127.0.0.1:5434/proxima` - пароль читать `sudo -n cat`, в файл `0600` своего пользователя, не в чат и не в лог.

**Откат / уборка.** Репетиция ничего не меняет в боевом контуре, откатывать нечего; убрать стенд:
```bash
bash tools/rehearsal_run.sh down --root "$ROOT"      # down -v --remove-orphans (webapp тоже), том удалён
sudo rm -rf "$ROOT"                                    # секреты, raw, логи - скрипт это не делает сам
sudo docker image rm $(sudo docker image ls -q 'proxima-rehearsal-*')
sudo docker ps --format '{{.Names}}\t{{.Status}}' | grep proxima-ai
```
Последняя команда - та же проверка, что в начале: `proxima-ai-postgres-1` с прежним аптаймом. Два WB-вызова отмене не подлежат (read-only, на стороне WB ничего не записано). Результат репетиции (сошлись ли W10/W35, статусы прогонов, что упало) записывается в `docs/state/RELEASE-READINESS-1.14.md` и `docs/agent-system/HANDOFF.md`; найденные расхождения - единицы в очередь, не правки на сервере.

## Октябрь - не условие релиза

Ниже то, что накопилось на сервере и мешает порядку, но релиз M-01 не задерживает. Делать после гейта 30.09.

- Вывести `~/proxima-webapp-staging` и ручной контейнер веб-морды - их заменяет compose с overlay.
- Удалить пустые базы `proxima_dev`.
- Убрать `.env.task` из рабочей зоны.
- Включить `make test-db-refresh` в регулярный цикл.
- Установить `infra/backup/*` как юниты, а не запускать руками. Факт 08.09: серверный `/usr/local/bin/proxima-pg-backup.sh` (sha256 `d29feb24…`, 29.08) отстал от `infra/backup/proxima-pg-backup.sh` (`fa591531…`): репозиторная версия дополнительно архивирует `PROXIMA_RAW_DIR`, но под `set -u` требует эту переменную в окружении, а `/etc/cron.d/proxima-pg-backup` её не задаёт - при установке добавить в cron-файл строку `PROXIMA_RAW_DIR=/srv/proxima-ai/raw`.
- Перенести `proxima-psql-owner` (раздел 1.4) в `infra/bootstrap/` или заменить его штатным способом вызова `provision-runtime-roles.sh` на VPS.

## Сверка 08.09.2026

Что расходилось с `main` (`f45243e`) и с сервером, и что сделано. Evidence - read-only команды 08.09 (`sudo -n`, значения секретов не читались) и файлы `main`.

1. **§0, §4, §7, §8 - psql.** Было `sudo docker compose -f …/compose.yaml exec -T postgres psql -U postgres …`. На сервере compose падал без `PROXIMA_SECRETS_DIR` (`error while interpolating secrets.postgres_user.file`), а роли `postgres` в базе нет (`pg_roles` → суперпользователь один, имя в `postgres_user`). Стало: ledger - `sudo proxima-psql-readonly` (проверено: `1..6`); таблицы лестницы - `docker exec -i proxima-ai-postgres-1 sh -c 'psql -U "$(cat /run/secrets/postgres_user)" …'` с SQL на stdin (форма `psqlp` из WORKS-TODAY; проверено `SELECT 1; SELECT 2;` → `1`, `2`).
2. **§2 - номер схемы.** Было «007…016», «ожидается `16`». В `main` `db/migrations/` заканчивается `018_nm_daily.sql` (Story 4.0, PR #95, 08.09). Стало `18|18` с оговоркой «последняя миграция релизного тега» и проверкой `ls … | tail -1` в §0.
3. **§3 - `--date-from`.** Было `2026-08-28`, AC Story 1.13 (`epics.md:335`) - `2026-08-27`. Стало `2026-08-27` с объяснением, почему лишний день перекрытия безвреден.
4. **§3 - `cas_import.ts`.** Было `sudo -u \#1010 npx tsx tools/cas_import.ts`: uid 1010 на хосте нет (`getent passwd 1010` → exit 2), репозиторий `drwxr-x--- proxima-admin`, `~/signal-inputs` `0700`, `services/collector/node_modules` в чекауте нет, `tools/` в образ коллектора не копируется. Стало: `npm ci --workspace @proxima/collector --include-workspace-root` под `proxima-admin`, импорт от `root` с `PROXIMA_RAW_DIR=/srv/proxima-ai/raw`, затем `chown -R 1010:1010`; предпосылки прав записаны.
5. **§1 - `.env`/`jobs.env`; §7 - `sed`.** `.env` сервера (14.08.2026) - 12 имён, без `PROXIMA_SECRETS_DIR`, `WEBAPP_DATA_MODE`, `WEBAPP_TENANT_ID`, `COMPOSE_FILE`; `jobs.env` ждёт `PROXIMA_SECRETS_DIR`/`PROXIMA_RAW_DIR`. Добавлен шаг 1.1 с копией старого `.env`; `sed` в §7 теперь меняет существующую переменную и помечен условным (в 1.14 витрина не переключается); возврат `.env` и `jobs.env` в §7 описан.
6. **Форма вызова заданий.** Было `collector backfill …`/`collector collect …`. Dockerfile коллектора без ENTRYPOINT, PR #90: `npm run <job> -- …`. Заодно `apply-migrations` переведён с хостового `make` на `control-plane-admin` (AC 1.13, спайн Conventions, `images.yml:94`): хостовая форма требует `uv sync` под `root` и owner-секретов вне контейнера (AD-15).
7. **§5 - drop-in PA-13.** Drop-in ставился к юниту, которого на хосте нет (`ls /etc/systemd/system/ | grep proxima` → только `host-monitor`, `tg-bot`), а снятие делало `systemctl restart` oneshot-юнита, то есть запускало воронку. Стало: `proxima-funnel-v3@.service`/`.timer` устанавливаются без `enable`, drop-in ставится к ним, снятие - `rm` + `daemon-reload` + `systemctl cat | grep -c` → `0`; `proxima-funnel-csv@` явно не ставится (FR9).
8. **§4 - эталоны W10/W35.** Числа стояли только в runbook, `epics.md:29` и `SPEC.md:33`; в `API-FACTS.md` их не было (`grep W10` → пусто), хотя AC 1.14 сверяет «с API-FACTS». Добавлен раздел в `API-FACTS.md` с источником и датой (30.08.2026), границами ISO-недель и `UNKNOWN` про день 30.08; §4 ссылается на него, SQL дан для обеих недель.
9. **§1 - provision.** Было `sudo bash provision-runtime-roles.sh` без аргументов - скрипт отказывает (`--psql must point to an executable psql`, `--secrets-dir is required`), `psql` на хосте нет. Стало: обёртка `proxima-psql-owner` (в `main` нет, помечена), `--host postgres` (URI-файлы для контейнеров; `127.0.0.1` внутри контейнера - trust, `postgres` - только по паролю, проверено), `--admin-user` из `postgres_user`; два прогона - до и после миграций (членства и `GRANT DELETE` появляются только после 011).
10. **§1 - owner-секреты.** `postgres_user`/`postgres_password` на сервере `-rw-r----- root:proxima-monitor`; контракт compose/CI - `1010:1010 0600`, `read_secret(private_only)` отказывает `0640`. Добавлен `chown`/`chmod`.
11. **Compose без `-f` из `/srv/proxima-ai/repo`.** Так его зовут `morning_run.sh`, `restore_check.sh`, `funnel_v3_run.sh` и юниты; на сервере из этого каталога - `no configuration file provided: not found`. Решение без кода - `COMPOSE_FILE=infra/compose.yaml` в `.env` (проверено на копии `infra/` в scratch-каталоге: `config --services` → 4 сервиса).
12. **§7 - `delete_run.py`.** Было `sudo -u \#1010 python3 …` (нет uid, нет `psycopg` в хостовом python 3.12). Стало: контейнер `control-plane` с `-v` janitor-URI и `-e JANITOR_DATABASE_URI_FILE`.
13. **§5 - контракт монтирования.** `collector` получает tenant-prefixed WB-токены через compose `secrets:` и `${PROXIMA_RAW_DIR}` как bind-volume; runners передают контейнерные пути. Ручные `-v` из §3 убраны; в §5 осталась проверочная команда перед включением таймера.
14. **Октябрь - бэкап.** Серверный `proxima-pg-backup.sh` отстал от репозиторного (sha256 `d29feb24…` против `fa591531…`), cron не задаёт `PROXIMA_RAW_DIR` - записано в пункт «установить `infra/backup/*`».
15. **§3, §5 - живая сеть WB.** AD-4 делает транспорт fail-closed: `services/collector/src/wb/transport.ts` отвечает `WB_NETWORK_FORBIDDEN` без `WB_ALLOW_LIVE_NETWORK=1`, а `collect`/`funnel-v3` берут `networkTransport()` жёстко. Ни `infra/jobs.env`, ни `infra/compose.yaml`, ни runners, ни юниты, ни команда живого хвоста в §3 флаг не задавали - первый реальный `collect` на сервере падал бы на первом HTTP-вызове, и ничто это не ловило. Стало: `WB_ALLOW_LIVE_NETWORK: "1"` в `environment:` сервиса `collector` в `infra/compose.yaml` - только он ходит в WB; `jobs.env` не подходит: его читают все три job-сервиса, а `read_env_file()` в `tools/wb_async_report.py` отвергает ключи вне `SAFE_ENV_KEYS`, и `apply-migrations`/`FUNNEL_CSV_DOWNLOAD` упали бы на незнакомом ключе. В §3 добавлена проверка `compose config | grep -c` перед хвостом, в §5 - оговорка про юниты; гейт `tools/verify_live_network.py` (`make live-network`, входит в `make verify`) держит флаг только в compose - не в env-файлах, не в юнитах, не в тестах, и проверяет, что сам seam в `transport.ts` на месте.
16. **§4 - правило гейта W35 (08.09, ~13:40 UTC, решение Mike после репетиции D35).** Сумма W35 = 225 / 263 089 ₽ снята со снимка 30.08 05:59 UTC с неполным днём 30.08; после пары 31.08 и живого хвоста стенд дал 228 / 282 836.08 при сошедшемся до копейки W10 (649 / 700 860.50 - прежнее `700860.00` в §4 было округлением), и по построению иначе быть не могло. Стало: W10 - сумма недели `649|700860.50`; W35 - по дням: 24-26.08 равны паре 31.08 (`55|6|62146.87`, `40|7|29247.90`, `28|4|44956.00`), 27-30.08 равны счёту по `stg_wb_orders_latest` за московский день с `isCancel` не-true / true; `tools/rehearsal_run.sh check` реализует то же (на стенде 08.09 - все PASS). Ширина окна перезаписи - открытый вопрос Story 6.1/6.3 (`API-FACTS.md`), не условие релиза.
