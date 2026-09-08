# Runbook первого релиза M-01

Обновлено 04.09.2026. Исполняет Mike на VPS `proxima` (135.106.186.210) под `proxima-admin`. Каждая команда — копипаста, под каждой сказано, что должно появиться в ответ. Если ответ другой — не импровизировать, а идти в раздел 7 «Откат».

**Разделы идут строго по порядку.** Порядок — не стилистика: бэкфилл до первого `collect`, включение таймеров после SUCCEEDED бэкфилла. Нарушение порядка ломает ряд, а не просто задерживает релиз.

Перед первой командой: план отката (раздел 7) прочитан, тег `v2026.09.0-baseline` из раздела 0 создан. Без него откатываться некуда.

## 0. Оживить чекаут на сервере

На 04.09 боевой чекаут `/srv/proxima-ai/repo` стоит на `fd95fcb` в detached HEAD, дерево чистое, **remote пуст** — `git pull` там невозможен физически.

```bash
sudo git -C /srv/proxima-ai/repo log --oneline -1
```
Ожидается `fd95fcb Revert "fix: enforce READ-only Analytics token…"`. Другой коммит — значит на сервер уже кто-то ходил; остановиться и разобраться.

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
```
Релизный тег ставится на `main` перед релизом и записывается здесь же в `CHANGELOG.md` (раздел 8). Ожидается его коммит.

**Проверить, что применено в боевой базе:**
```bash
sudo docker compose -f /srv/proxima-ai/repo/infra/compose.yaml exec -T postgres \
  psql -U postgres -d proxima -c "SELECT version, name FROM schema_migrations ORDER BY version"
```
Ожидается ряд **001–006**. Всё, что выше — 007…016 — применяется в разделе 2. Если там уже есть 007+, миграции применяли вручную: остановиться, это меняет план.

## 1. Подготовка: токены и роли

Токены переименовываются под схему `<tenant>_wb_<category>_token` и отдаются пользователю контейнеров `1010`.

```bash
sudo ls -la /etc/proxima-ai/secrets/
```
Ожидаются файлы токенов WB. **Значения не выводить** — только `ls`.

```bash
cd /etc/proxima-ai/secrets
sudo mv wb_statistics_token amirova-test_wb_statistics_token
sudo mv wb_analytics_token  amirova-test_wb_analytics_token
sudo mv wb_finance_token    amirova-test_wb_finance_token
sudo chown 1010:1010 amirova-test_wb_*_token
sudo chmod 0600 amirova-test_wb_*_token
sudo ls -la /etc/proxima-ai/secrets/amirova-test_wb_*
```
Ожидается три файла, владелец `1010:1010`, права `-rw-------`.

> **Открытый вопрос перед этим шагом.** По OQ-10 analytics-токен боевого кабинета ежедневно использует неизвестный потребитель вне VPS, и решение о ротации на read-only (PA-13) не принято. Переименование токен не ротирует. Если ротация делается — она делается здесь, до релиза, иначе релиз стартует на скомпрометированном ключе.

```bash
sudo bash /srv/proxima-ai/repo/infra/bootstrap/provision-runtime-roles.sh
```
Ожидается строка вида `provision-runtime-roles: ok (5 login roles, database proxima_test, URI files under /etc/proxima-ai/secrets; no secret value printed)`. Скрипт идемпотентен: повторный запуск даёт ту же строку.

## 2. Деплой без таймеров

Таймеры на этом шаге **не включаются**. Сначала данные, потом расписание.

```bash
cd /srv/proxima-ai/repo
sudo docker compose -f infra/compose.yaml --profile jobs build
```
Ожидается сборка образов `collector`, `control-plane`, `control-plane-admin` без ошибок.

```bash
sudo make -C /srv/proxima-ai/repo apply-migrations ENV_FILE=/srv/proxima-ai/repo/.env
```
Ожидается применение миграций 007…016 и итоговая строка о применённых версиях. Проверить:
```bash
sudo docker compose -f infra/compose.yaml exec -T postgres \
  psql -U postgres -d proxima -c "SELECT max(version) FROM schema_migrations"
```
Ожидается `16`.

```bash
sudo docker compose -f infra/compose.yaml up -d postgres
```
Пересоздание контейнера с bridge-портом занимает около десяти секунд — база в это время недоступна, это ожидаемо.

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
Не совпало — **остановиться**: сверять цифры релиза будет не с чем.

> Берётся пара от **31.08**, а не от 30.08: `docs/state/API-FACTS.md` говорит, что бэкфилл берёт самую свежую пару, и снимок 31.08 снят именно как страховка непрерывности ряда. В тексте истории 1.14 упоминается пара 30.08 — это расхождение формулировок, факт в `API-FACTS.md`.

**Импорт в CAS:**
```bash
cd /srv/proxima-ai/repo
sudo -u \#1010 npx tsx tools/cas_import.ts \
  ~/signal-inputs/fixtures/wb-api/statistics/supplier-sales/20260831T155341Z__dateFrom-2023-01-01_flag-0.json \
  --retrieved-at 2026-08-31T15:53:41Z --source official_wb_statistics
```
Повторить для `supplier-orders`. Каждый вызов печатает `content_sha256` — он должен совпасть со сверенным выше.

**Бэкфилл из артефактов:**
```bash
sudo docker compose -f infra/compose.yaml --profile jobs run --rm collector \
  backfill --tenant amirova-test \
  --source artifact:d2f1dc9581ad1f1ab67d1f7ac874b1fa93109915a06d3b09505d960e0b65ec96,0c0318ff835d59e263a32cd1f565d8f899e28173e4eacc942c414756214daa40
```
`run_day` берётся из манифеста CAS и будет `2026-08-31`; версии пишутся по `2026-08-30` включительно. Ожидается SUCCEEDED и число дней в логе прогона.

**Живой хвост с перекрытием:**
```bash
sudo docker compose -f infra/compose.yaml --profile jobs run --rm collector \
  collect --tenant amirova-test --date-from 2026-08-28 \
  --statistics-token-file /run/secrets/amirova-test_wb_statistics_token
```
Три дня перекрытия с бэкфиллом — это самолечение, а не дубль: наблюдения идемпотентны.

## 4. Проверка цифр

```bash
sudo docker compose -f infra/compose.yaml exec -T postgres psql -U postgres -d proxima -c "
  SELECT set_config('proxima.tenant_id','amirova-test',false);
  SELECT sum(orders_count) AS orders, sum(revenue_rub) AS revenue
  FROM fact_cabinet_daily_current
  WHERE tenant_id='amirova-test' AND calendar_day BETWEEN '2026-03-02' AND '2026-03-08'"
```
Ожидается **649 заказов и 700 860 ₽** — это W10, эталон из фикстур 30.08.

Та же выборка по W35 должна дать **225 заказов и 263 089 ₽**.

Расхождение — **гейт не пройден**. Не «почти сходится»: цифры либо равны эталону, либо релиз останавливается.

```bash
sudo docker compose -f infra/compose.yaml exec -T postgres psql -U postgres -d proxima -c "
  SELECT set_config('proxima.tenant_id','amirova-test',false);
  SELECT last_full_day, collected_at, stale FROM data_status_current WHERE tenant_id='amirova-test'"
```
Ожидается `last_full_day` = вчерашняя дата по Москве, `stale = false`.

Затем прогнать `docs/state/WORKS-TODAY.md` целиком и дописать в него результат этого релиза.

Строка статуса на `/brief` проверяется в релизе 2.6, не здесь.

## 5. Включение таймеров

Только после SUCCEEDED бэкфилла и сошедшихся цифр.

```bash
sudo install -m 0644 /srv/proxima-ai/repo/infra/systemd/proxima-morning@.service /etc/systemd/system/
sudo install -m 0644 /srv/proxima-ai/repo/infra/systemd/proxima-morning@.timer /etc/systemd/system/
sudo install -m 0644 /srv/proxima-ai/repo/infra/systemd/proxima-restore-check@.service /etc/systemd/system/
sudo install -m 0644 /srv/proxima-ai/repo/infra/systemd/proxima-restore-check@.timer /etc/systemd/system/
sudo install -m 0644 /srv/proxima-ai/repo/infra/systemd/proxima-alert@.service /etc/systemd/system/
sudo install -d -m 0755 /etc/systemd/system/proxima-funnel-v3@.service.d
sudo install -m 0644 /srv/proxima-ai/repo/infra/systemd/proxima-funnel-v3@.service.d/10-analytics-read-write.conf \
  /etc/systemd/system/proxima-funnel-v3@.service.d/10-analytics-read-write.conf
sudo systemctl daemon-reload
sudo systemctl enable --now proxima-morning@amirova-test.timer
sudo systemctl enable --now proxima-restore-check@amirova-test.timer
systemctl list-timers 'proxima*' --all --no-pager
```
Ожидается три таймера: `proxima-morning@`, `proxima-restore-check@` и уже работавший `proxima-host-monitor`. Утренний срабатывает в 05:30 МСК и гоняет цепочку `collect → norm → brief` строго по порядку со стопом на первой ошибке; воронка в цепочку не входит — она отдельным юнитом после сводки (AD-6, CR от 03.09).

Drop-in `10-analytics-read-write.conf` — временное исключение PA-13 для текущего
read-write analytics-токена. После ротации на read-only снять исключение:

```bash
sudo rm /etc/systemd/system/proxima-funnel-v3@.service.d/10-analytics-read-write.conf
sudo systemctl daemon-reload
sudo systemctl restart proxima-funnel-v3@amirova-test.service
```

Сам `proxima-funnel-v3@.service` при установке и снятии исключения не менять.

## 6. Проверка алерта

Сторож, о котором никто не узнал, сторожем не является.

```bash
sudo systemctl start proxima-alert@test.service
```
Ожидается сообщение в Telegram-канале монитора в течение минуты. Не пришло — разбираться здесь, а не после релиза: `TimeoutStartSec` утреннего юнита несёт крайний срок 06:30, и без работающего алерта его превышение останется незамеченным.

Проверить, что ретрай на месте:
```bash
grep -n "retry" /srv/proxima-ai/repo/tools/proxima_alert.sh
```
Ожидается `--retry 3 --retry-delay 5` (задача PA-65) в комментарии и строки конфига curl `retry = 3`, `retry-delay = 5`. Ретрайит сам curl внутри одного вызова: транспортные ошибки (включая таймаут `max-time = 20`) и ответы HTTP 408/429/5xx повторяются (до 3 попыток, пауза 5 с); остальные 4xx (например, 401 с неверным токеном, 404) — нет: с `fail` скрипт падает с кодом 22 сразу. Отдельного пинга канала в скрипте нет — живость канала проверяется только этим тестовым сообщением: не пришло за минуту (3 попытки по `max-time` = максимум ~80 с) — чинить токен/чат здесь, до релиза.

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
sudo docker compose -f infra/compose.yaml exec -T postgres psql -U postgres -d proxima -c "
  SELECT set_config('proxima.tenant_id','amirova-test',false);
  SELECT run_id, kind, status, started_at FROM collector_runs
  WHERE tenant_id='amirova-test' ORDER BY started_at DESC LIMIT 20"

sudo -u \#1010 python3 /srv/proxima-ai/repo/tools/delete_run.py \
  --tenant amirova-test --run <uuid> --dry-run
```
Сначала всегда `--dry-run`: он печатает счётчики транзитивного замыкания. Удаление входного прогона снимает и всё, что на нём построено — так и задумано (AD-3). Убедившись в объёме, повторить без `--dry-run`.

Вернуть витрину на фикстуры:
```bash
sudo sed -i 's/^WEBAPP_DATA_MODE=.*/WEBAPP_DATA_MODE=fixtures/' /srv/proxima-ai/repo/.env
sudo docker compose -f infra/webapp.compose.yaml up -d
```

Вернуть код:
```bash
sudo git -C /srv/proxima-ai/repo checkout v2026.09.0-baseline
```

**Миграции не откатываются.** Они additive-only: новые таблицы остаются пустыми и никому не мешают. Попытка откатить миграцию — нарушение AD-14 и способ потерять данные.

## 8. Наблюдение и запись

Три утра подряд (CAP-1) проверять, что прогон завершился SUCCEEDED и `last_full_day` вчерашний:
```bash
sudo docker compose -f infra/compose.yaml exec -T postgres psql -U postgres -d proxima -c "
  SELECT set_config('proxima.tenant_id','amirova-test',false);
  SELECT kind, status, finished_at FROM collector_runs
  WHERE tenant_id='amirova-test' ORDER BY finished_at DESC LIMIT 5"
```

Записать релиз в `CHANGELOG.md` в корне репозитория: тег, дата, что вошло, ссылка на этот runbook.

## Октябрь — не условие релиза

Ниже то, что накопилось на сервере и мешает порядку, но релиз M-01 не задерживает. Делать после гейта 30.09.

- Вывести `~/proxima-webapp-staging` и ручной контейнер веб-морды — их заменяет compose с overlay.
- Удалить пустые базы `proxima_dev`.
- Убрать `.env.task` из рабочей зоны.
- Включить `make test-db-refresh` в регулярный цикл.
- Установить `infra/backup/*` как юниты, а не запускать руками.
