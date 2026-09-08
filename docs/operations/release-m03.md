# Runbook релиза 2.6 (M-03): сводка приходит каждое утро - ЧЕРНОВИК

> **ЧЕРНОВИК, не исполнять до сверки с `main` перед 22.09.** Написан 08-09.09.2026 против `main` `08c94cc` (миграции 001-018, PR #125) до релиза 1.14, то есть до первого запуска конвейера на боевом сервере. Все ожидания ниже - предсказания по коду и по репетиционному стенду, а не наблюдения на боевом контуре. Перед 22.09 сверить с `main`, с фактическим состоянием сервера после 1.14 и с журналом `docs/operations/releases/2026-09-15-m01.md`; чек-лист сверки - в конце файла.

Дата релиза - вт 22.09.2026 (D33 в незамерженном PR #89, на который ссылается D35; AC Story 2.6 - «не позже 23.09.2026 `[ожидает календаря Mike]`», иначе семь утр не помещаются до 30.09, CP-7). Исполняет Claude - сессия оркестратора на VPS `proxima` (135.106.186.210) под `proxima-admin` - после явного «деплой» от Mike в чате (D7). Что делает релиз: переключает витрину `/brief` с фикстур на Postgres (`WEBAPP_DATA_MODE=postgres`), после чего Mike каждое утро открывает `/brief` и видит вчерашние заказы и выручку против нормы.

**Разделы идут строго по порядку.** Сначала данные (сводка за вчера в `brief_current`), потом витрина: экран, переключённый до первого успешного `brief`, покажет «Сводка ещё не считается» - это не отказ, но и не приёмка релиза.

Формы доступа - те же три, что в `docs/operations/release-m01.md` («Три формы доступа, которые повторяются ниже»): `sudo proxima-psql-readonly` для ledger миграций, `docker exec -i proxima-ai-postgres-1 sh -c 'psql …'` с SQL на stdin для таблиц лестницы, compose из `/srv/proxima-ai/repo` без `-f`. Здесь добавляется четвёртая:

- **Compose с явными `-f`** - только для витрины: `sudo docker compose -f infra/compose.yaml -f infra/webapp.staging.compose.yaml …` из `/srv/proxima-ai/repo`. Явные `-f` перекрывают `COMPOSE_FILE=infra/compose.yaml` из `.env` (§1.1 runbook 1.14), поэтому overlay приходится называть вместе с базовым файлом. В бою это **два** `-f`; три было на репетиции 08.09, потому что между ними стоял `infra/compose.rehearsal.yaml`. Имя проекта не меняется: оно приходит из `name: proxima-ai` в `infra/compose.yaml`.

## 0. Предусловия

Ни один пункт не пропускается: 2.6 - это переключение источника данных на боевом экране, и всё, что ниже, проверяет, что источнику есть чем отвечать.

**1. Релиз 1.14 прошёл и держится.** Три утра подряд SUCCEEDED (CAP-1) и свежий статус данных - выборка §8 runbook 1.14:

```bash
printf '%s\n' "SELECT set_config('proxima.tenant_id','amirova-test',false);
SELECT kind, status, finished_at FROM collector_runs
  WHERE tenant_id='amirova-test' ORDER BY finished_at DESC LIMIT 6;
SELECT last_full_day, stale FROM data_status_current WHERE tenant_id='amirova-test';" \
| sudo docker exec -i proxima-ai-postgres-1 sh -c 'psql -U "$(cat /run/secrets/postgres_user)" -d proxima -v ON_ERROR_STOP=1 -tA'
```
Ожидается: прогоны последних утр - `SUCCEEDED`, `last_full_day` = вчерашняя дата по Москве, `stale = f`. Факт трёх утр - в журнале `docs/operations/releases/2026-09-15-m01.md` («Наблюдение три утра»). `stale = t` или прогон `FAILED` - 2.6 не начинается: сначала чинится сбор.

**2. Story 6.1 (эталоны) и CP-13 (теневой пересчёт шага 7).** AC Story 2.6: теневой пересчёт сводки - отклонение и статусы - выполнен на синтетике, эталон лежит в `verification/golden/`. На 08.09 каталога `verification/` в репозитории нет, `tools/verify_shadow.py` нет, `docs/state/SHADOW-RECONCILIATION.md` пуст, блокер B1 в `docs/state/RELEASE-READINESS-1.14.md` открыт (срок Владислава - пт 11.09 по D33/D35). Статус на 22.09 - `UNKNOWN`. Правило AC 2.6 жёсткое: **релиз не выпускается, пока расхождение теневого пересчёта или сверки с кабинетом не закрыто**; снять блокировку может только Mike записью в `DECISIONS.md` (D26).

**3. Ротация analytics-токена (PA-13) - обязательна до 2.6.** D32/D35: боевой analytics-токен пока read-write, и его ежедневно использует неизвестный потребитель вне VPS (OQ-10). После ротации на read-only снимается временный drop-in, поставленный в §5 runbook 1.14:

```bash
sudo rm -f /etc/systemd/system/proxima-funnel-v3@.service.d/10-analytics-read-write.conf
sudo systemctl daemon-reload
systemctl cat proxima-funnel-v3@amirova-test.service | grep -c ALLOW_ANALYTICS_READ_WRITE
```
Ожидается `0`. `systemctl restart` здесь не делать: юнит `Type=oneshot`, `restart` неактивного oneshot запускает воронку. Ротация выполнена / не выполнена на 22.09 - `UNKNOWN`.

**4. Секрет `proxima_webapp_uri` читается контейнером витрины.** Образ webapp работает под uid 1001 (`services/webapp/Dockerfile`), а не 1010, как задания; `provision-runtime-roles.sh` ставит владельца на каждом прогоне (решение Mike 08.09, addendum к D35; блокер B9):

```bash
sudo stat -c '%A %u:%g %n' /etc/proxima-ai/secrets/proxima_webapp_uri /etc/proxima-ai/secrets/proxima_webapp_password
```
Ожидается `-rw------- 1001:1001` для обоих файлов. Другой владелец - перезапустить `provision-runtime-roles.sh` формой §1.4 runbook 1.14 (он идемпотентен и переустанавливает владельцев); значение файла не выводить. С владельцем `1010:1010` витрина в postgres-режиме отвечает «файл `WEBAPP_DATA_DATABASE_URI_FILE` не читается» - так это и нашлось на репетиции 08.09.

**5. Роль и гранты витрины.** Роль `proxima_webapp` (член `proxima_webapp_readonly`) создаёт `provision-runtime-roles.sh` в §1.4 runbook 1.14; гранты приходят миграциями: `data_status_current`, `fact_cabinet_daily`, `fact_cabinet_daily_current`, `tenants` - `013_fact_cabinet_daily.sql`; `norm_daily`, `norm_daily_current` - `014_norm_daily.sql`; `brief_daily`, `brief_current` - `015_brief_daily.sql`; `collector_runs` - `011_run_ledger.sql`. На `fact_nm_daily` гранта нет намеренно (`018_nm_daily.sql`, AD-9). RLS отдаёт строки только при `set_config('proxima.tenant_id', …)` в той же сессии - провайдер ставит GUC первым statement каждого соединения.

**6. Полоса метрик берёт цифры из фактов - готово.** PR #123 (`feat/webapp-metrics-postgres`, в `main` 08.09, единица C3 по D36): в postgres-режиме карточки `orders-day`, `revenue-day`, `freshness` считаются из `fact_cabinet_daily_current` и `data_status_current`, карточки `signals` и `oos-risks` скрыты (значение `null` не занимает место), `FxBadge` остаётся только в fixtures-режиме. До #123 `getMetrics()` отдавал `NOT_IMPLEMENTED`, и в postgres-режиме падала каждая страница (блокер B10). Бюджет чтений - не больше двух `SELECT` на полосу (AD-9).

**7. Тексты `/brief` для нештатных состояний - готово.** PR #124 (`fix/webapp-brief-wording-states`, единица C4): `blocked` → «Данных за день нет»; сводка есть, но день уже не последний полный → «Сводка за DD.MM, данные уже за DD.MM»; сбор свежий, сводки ещё нет → «Сводка ещё не считается».

**8. Журнал релиза и `CHANGELOG.md` - готово.** PR #120 (единица G1): каталог `docs/operations/releases/` с `TEMPLATE.md`, `README.md` и заготовкой `2026-09-15-m01.md`; `CHANGELOG.md` в корне по Keep a Changelog 1.1. Журнал 2.6 - §6 ниже.

**9. Схема базы.** Релиз 1.14 накатывает 007-018 и ждёт `18|18`. Несёт ли релизный тег 2.6 новые миграции - `UNKNOWN` до появления тега; если несёт, перед §1 выполняются шаги §2 runbook 1.14 без изменений (`apply-migrations` через `control-plane-admin`, второй прогон `provision-runtime-roles.sh`, пересборка образов) - здесь они не дублируются.

```bash
printf 'SELECT count(*), max(version) FROM schema_migrations;\n' | sudo proxima-psql-readonly
ls /srv/proxima-ai/repo/db/migrations/ | tail -1
```
Ожидается: число и номер последней миграции релизного тега 2.6 совпадают (после 1.14 без новых миграций - `18|18` и `018_nm_daily.sql`).

**10. Порт 3000 занят ручным контейнером.** На 08.09 `127.0.0.1:3000` держит `proxima-webapp-staging` - контейнер, запущенный `docker run` без compose, `restart: unless-stopped`, образ `bae976c` из ветки PA-49 (26.08), фикстуры, auth выключен (`docs/state/INVENTORY.md` №4 и таблица портов; `docs/state/WORKS-TODAY.md` WT-05/WT-06). Overlay публикует `127.0.0.1:${PROXIMA_WEBAPP_PORT:-3000}:3000` - на том же порту. Решение - §1 ниже; какой вариант выбирает Mike, на 08.09 `UNKNOWN`.

**11. Тег, релиз-заметка, слово «деплой».** Тег 2.6 - `UNKNOWN`: форма `v2026.09.NN-2` записана в AC Story 1.14 и в §0 runbook 1.14 только для первого релиза, для 2.6 форма в репозитории не зафиксирована. Baseline отката - тег релиза 1.14 (`UNKNOWN` до 15.09). Слово «деплой» - в чате в день релиза (D7).

**Чего этот черновик не покрывает** (входит в релиз 2.6, но пишется отдельно):

- **Шаг воронки.** `proxima-funnel-v3@.{service,timer}` устанавливаются в §5 runbook 1.14 **без** `enable`; включение едет тегом 2.6 (D33; Stories 3.1/3.4). Команда включения, первый ручной прогон `funnel_v3` и проверка `fact_funnel_daily_current` - в этом файле не написаны.
- **Сверка с кабинетом WB.** Процедура и допуски - `docs/state/CABINET-RECONCILIATION.md` (эталонный экран и фильтр - `UNKNOWN`, заполняются первой строкой); ведёт Владислав, приёмка Mike. AC 2.6: сверяется день, закрытый ≥ 3 суток назад; допуск `[ASSUMPTION]` ±1 заказ и ±0.5 % выручки; расхождение больше допуска = гейт не пройден.
- **Сверка нормы с расчётом из артефакта «Ряд продаж Амировой»** (AC 2.6) и гейт теневого пересчёта (Story 6.1/6.2).
- **Миграции, provision, пересборка образов** - формы §2 runbook 1.14, не дублируются.

## 1. Что меняется в `.env` и в compose

Изменение ровно одно: режим данных витрины. Всё остальное в `.env` поставлено релизом 1.14 (§1.1 runbook 1.14: `COMPOSE_FILE`, `PROXIMA_SECRETS_DIR`, `WEBAPP_DATA_MODE=fixtures`, `WEBAPP_TENANT_ID=amirova-test`).

**Сначала копия.** Отдельная от копии 1.14, чтобы откат 2.6 не возвращал контур к состоянию до 1.14:

```bash
sudo cp -a /srv/proxima-ai/repo/.env /var/backups/proxima/repo.env-before-2.6
sudo grep -n '^WEBAPP_\|^COMPOSE_FILE\|^PROXIMA_SECRETS_DIR\|^PROXIMA_WEBAPP_PORT' /srv/proxima-ai/repo/.env
```
Ожидается: `WEBAPP_DATA_MODE=fixtures`, `WEBAPP_TENANT_ID=amirova-test`, `COMPOSE_FILE=infra/compose.yaml`, `PROXIMA_SECRETS_DIR=/etc/proxima-ai/secrets`; строки `PROXIMA_WEBAPP_PORT` нет (в `.env` её не добавлял ни один шаг 1.14, в `infra/local.env.example` её тоже нет). Нет `WEBAPP_DATA_MODE` - §1.1 runbook 1.14 не выполнялся, остановиться: `sed` ниже менять нечего.

**Порт витрины - решение до переключения.** Два варианта, выбирает Mike:

*Вариант А - вывести ручной контейнер* (он же пункт «Октябрь» runbook 1.14: «Вывести `~/proxima-webapp-staging` и ручной контейнер веб-морды - их заменяет compose с overlay»). Порт 3000 и алиас `proxima-app` у Mike сохраняются:
```bash
sudo docker stop proxima-webapp-staging
sudo docker update --restart=no proxima-webapp-staging
sudo docker ps --format '{{.Names}}\t{{.Ports}}' | grep -c 3000
```
Ожидается `0`. Контейнер не удаляется: он же - точка возврата, если compose-витрина не поднимется (§5).

*Вариант Б - другой порт*, ручной контейнер не трогается:
```bash
printf 'PROXIMA_WEBAPP_PORT=3001\n' | sudo tee -a /srv/proxima-ai/repo/.env >/dev/null
```
Ожидается: переменная в `.env`; дальше во всех командах §3 вместо 3000 подставляется выбранный порт. Значение `3001` здесь - пример, не решение; занятость порта проверить заранее (`sudo ss -lntp | grep :3001`).

**Переключение режима:**

```bash
sudo sed -i 's/^WEBAPP_DATA_MODE=.*/WEBAPP_DATA_MODE=postgres/' /srv/proxima-ai/repo/.env
sudo grep -n '^WEBAPP_DATA_MODE=' /srv/proxima-ai/repo/.env
```
Ожидается одна строка `WEBAPP_DATA_MODE=postgres`. Значение читает `resolveDataMode()` (`services/webapp/src/lib/data/provider.ts`) и оно fail-closed: любое другое значение - ошибка старта, а не тихий откат на фикстуры.

**Проверка рендера compose до `up`** (ничего не запускает):

```bash
cd /srv/proxima-ai/repo
sudo docker compose -f infra/compose.yaml -f infra/webapp.staging.compose.yaml config \
  | grep -n 'WEBAPP_DATA_MODE\|WEBAPP_TENANT_ID\|WEBAPP_DATA_DATABASE_URI_FILE\|WEBAPP_REQUIRE_AUTH\|proxima_webapp_uri\|published'
```
Ожидается: `WEBAPP_DATA_MODE: postgres`, `WEBAPP_TENANT_ID: amirova-test`, `WEBAPP_DATA_DATABASE_URI_FILE: /run/secrets/proxima_webapp_uri`, `WEBAPP_REQUIRE_AUTH: "false"`, секрет `proxima_webapp_uri` с файлом `/etc/proxima-ai/secrets/proxima_webapp_uri`, published-порт `3000` (или выбранный в варианте Б) на `127.0.0.1`. Ошибка интерполяции `PROXIMA_SECRETS_DIR` или `WEBAPP_TENANT_ID` - `.env` не тот, вернуться на шаг выше.

Что здесь **не** меняется: `infra/compose.yaml` (боевые задания и postgres), `infra/jobs.env`, `infra/webapp.staging.compose.yaml` (overlay tracked, правки на сервере не нужны), юниты systemd.

## 2. Сводка за вчера должна уже быть в базе

Витрина ничего не считает - она читает `brief_current`. Считает control-plane, и с релиза 1.14 оба шага уже стоят в утренней цепочке: `tools/morning_run.sh` выполняет `collect → norm → brief` строго по порядку, каждый шаг - свой прогон, стоп на первой ошибке (AD-6, CR от 03.09). Поэтому «включение шагов в `morning_run.sh`» из When Story 2.6 к 22.09, скорее всего, уже сделано - это проверяется, а не выполняется.

```bash
grep -n 'run_collect$\|run_norm$\|run_brief$' /srv/proxima-ai/repo/tools/morning_run.sh | tail -3
```
Ожидается три строки вызовов в конце файла - `run_collect`, `run_norm`, `run_brief`. Шагов нет - значит на сервере старый тег; вернуться к §0 п. 9.

**Есть ли сводка за вчера:**

```bash
printf '%s\n' "SELECT set_config('proxima.tenant_id','amirova-test',false);
SELECT brief_day, status FROM brief_current WHERE tenant_id='amirova-test';
SELECT metric, status, window_days, sample_days FROM norm_daily_current WHERE tenant_id='amirova-test';" \
| sudo docker exec -i proxima-ai-postgres-1 sh -c 'psql -U "$(cat /run/secrets/postgres_user)" -d proxima -v ON_ERROR_STOP=1 -tA'
```
Ожидается: одна строка `<вчера>|ok` из `brief_current` и две строки нормы (`orders`, `revenue`) со `status = ok` и `window_days = 14`. Варианты и что они значат:

- `insufficient` - окно нормы неполное; на экране будет «Норма копится: N/14 дней» вместо цифр. Приёмка релиза (цифры на `/brief`) не проходит - разбираться до переключения.
- `blocked` - нет версии факта за `evaluation_day`; на экране «Данных за день нет». Смотреть `collector_runs.notes` последнего `brief`.
- Пусто - сводка ещё ни разу не считалась; выполнить ручной прогон ниже.

**Ручной прогон `norm` + `brief`** (только если строки нет или она за старый день; формы - те же, что зовёт `morning_run.sh`):

```bash
cd /srv/proxima-ai/repo
sudo docker compose --profile jobs run --rm control-plane \
  python -m proxima_control_plane.norm run --tenant amirova-test
sudo docker compose --profile jobs run --rm control-plane \
  python -m proxima_control_plane.brief run --tenant amirova-test
```
Ожидается по строке итога на шаг: `norm` - `evaluation_day=<вчера> sample_days=14/14 status=ok`; `brief` - `brief_day=<вчера> status=ok` с заказами против нормы и числом сигналов. Порядок обязателен: `brief` читает норму. Провенанс: без `PROXIMA_GIT_SHA`/`PROXIMA_IMAGE_ID` в окружении прогон запишет в `collector_runs` `NULL` (пустые значения нормализуются в SQL, C1/D36) - для разового ручного прогона это допустимо, утренние прогоны их проставляют сами (`tools/morning_run.sh`). Затем повторить выборку выше: `brief_current` = `<вчера>|ok`.

## 3. Переключение витрины

```bash
cd /srv/proxima-ai/repo
sudo docker compose -f infra/compose.yaml -f infra/webapp.staging.compose.yaml up -d --build webapp
sudo docker compose -f infra/compose.yaml -f infra/webapp.staging.compose.yaml ps webapp
```
Ожидается сборка образа webapp (сеть: `npm ci` внутри сборки) и контейнер `proxima-ai-webapp-1` в состоянии `Up`, порт `127.0.0.1:3000->3000/tcp` (или выбранный в §1). Порт занят - вернуться к §1, решение по порту не выполнено.

**Проверка с сервера** (форма WT-40 из `docs/state/WORKS-TODAY.md`):

```bash
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:3000/brief
curl -s http://127.0.0.1:3000/brief | grep -o 'Данные до [^<]*'
curl -s http://127.0.0.1:3000/brief | grep -c 'Сбор не проходил больше суток'
```
Ожидается `200`; одна строка `Данные до <вчера>, обновлено <сегодня hh:mm>`; `0`. Ответ 500 - смотреть `sudo docker logs proxima-ai-webapp-1`: сообщение про `WEBAPP_DATA_DATABASE_URI_FILE` означает права секрета (§0 п. 4), про `WEBAPP_TENANT_ID` - переменную в `.env` (§1).

**Проверка с машины Mike** - через туннель:

```bash
ssh -o ExitOnForwardFailure=yes -N -L 13000:127.0.0.1:3000 proxima   # затем http://127.0.0.1:13000/brief
```
Локальный порт - `13000`, а не `3000`: на маке Mike порт 3000 занят локальным процессом, и форвард на 3000 работает неустойчиво (`WORKS-TODAY.md` NW-6, форма WT-19). Алиас `proxima-app` из ADR-0005 (`-L 3000:localhost:3000`) оставлен для старой ручной витрины.

### Что ожидается на экране

**Экран гибридный, и это задумано.** По конструкции Story 2.5 postgres-провайдер отдаёт живыми только сводку, аномалии и полосу метрик; редакционная часть брифа (`getBrief()`) в postgres-режиме по-прежнему приходит из фикстур - настоящие тексты появятся с Epic 5. Проверено на репетиционном стенде 08.09.2026 17:05 UTC после мержа #123 (стенд `proxima-rehearsal`, витрина на `:3434`, режим `postgres`). **Демо-дайджест на боевом экране 22.09 - не баг**, и разбирать его как инцидент в день релиза не нужно.

Настоящие данные (пометки «FX» нет):

| Элемент экрана | Откуда | Что должно быть видно |
|---|---|---|
| Блок «Вчера против нормы» | `brief_current.payload` | Заголовок `DD.MM: вчера против нормы`, строки «Заказы N против нормы X `±Y,Y %`» и «Выручка … против нормы …»; цвет отклонения по знаку |
| Строка статуса данных | `data_status_current` | `Данные до DD.MM, обновлено DD.MM hh:mm` (время московское) |
| Блок «Аномалии» | `payload.signals[]` того же брифа | Строки по SKU и категории без пометки demo; при подавленных цифрах список пуст |
| Полоса метрик, карточка «Заказы / день» | `fact_cabinet_daily_current` | Значение за `last_full_day` и дельта к среднему имеющихся дней `[день−7, день−1]`; спарклайн на 30 календарных дней |
| Полоса метрик, карточка «Выручка / день» | там же | То же, деньги округляются только на границе UI |
| Полоса метрик, карточка «Свежесть данных» | `data_status_current.collected_at`, `stale` | Время по Москве, зелёный при `stale = false`, красный при `stale = true` |

Остаётся фикстурами и **сохраняет пометку «FX»** (по замыслу Story 2.5; настоящее - Epic 5):

- «Дайджест дня» - демо-пункты; в режиме «сводки ещё нет» к ним добавляется строка «Сводка ещё не считается: ждём первый утренний прогон»;
- вердикт-строка в шапке («N критичных / M внимания» либо «Критичных нет») и блок «Критичные сигналы» под ней;
- подпись свитчера кабинета - «Пилотный кабинет (fixtures)», список из одного элемента;
- плашка unreleased на всех экранах (DEC-006) - остаётся до отдельного решения.

Скрыто в postgres-режиме: карточки «Сигналы» и «OOS-риски» (источника нет - D35; в fixtures обе видны). Если полоса метрик исчезла целиком вместе со свитчером кабинета - значит ни одна карточка не получила значения, то есть `data_status_current` пуст или без `last_full_day`; это указывает на проблему со сбором, а не с витриной.

Строка-предупреждение вместо цифр (любая из них = приёмка релиза не пройдена, разбираться по §2):

| Текст на экране | Что означает |
|---|---|
| `Норма копится: N/14 дней` | норма ещё не набрала окно (`status = insufficient`) |
| `Данных за день нет` | `status = blocked`: нет версии факта за день сводки |
| `Сводка за DD.MM, данные уже за DD.MM` | сбор ушёл вперёд, сводка за старый день (fail-closed AD-9) |
| `Сводка ещё не считается` | сбор свежий, строки в `brief_current` нет |
| `Сбор не проходил больше суток` | `stale = true` или статуса данных нет вовсе |

**Приёмка Mike:** открыть `/brief`, увидеть вчерашние заказы и выручку против нормы и сверить их с кабинетом WB по процедуре `docs/state/CABINET-RECONCILIATION.md`. Расхождение больше допуска - гейт не пройден (§0, «Чего этот черновик не покрывает»).

## 4. Наблюдение семь утр

Окно наблюдения - **23-29.09.2026** по D33 (семь утр после релиза 22.09). AC Story 2.6 называет 24-30.09 (окно после деплоя 23.09) - расхождение зависит от того, какую дату деплоя утвердит Mike; какое окно считать зачётным на 22.09 - `UNKNOWN`, вопрос в конце файла. Зачёт - по `collector_runs`, а не по доставке алерта (CAP-5).

Каждое утро - одна выборка:

```bash
printf '%s\n' "SELECT set_config('proxima.tenant_id','amirova-test',false);
SELECT kind, status, finished_at FROM collector_runs
  WHERE tenant_id='amirova-test' ORDER BY finished_at DESC LIMIT 6;
SELECT last_full_day, stale FROM data_status_current WHERE tenant_id='amirova-test';
SELECT brief_day, status FROM brief_current WHERE tenant_id='amirova-test';" \
| sudo docker exec -i proxima-ai-postgres-1 sh -c 'psql -U "$(cat /run/secrets/postgres_user)" -d proxima -v ON_ERROR_STOP=1 -tA'
```
Ожидается: шесть строк ledger = два последних утра, сегодняшние три - `collect|SUCCEEDED`, `norm|SUCCEEDED`, `brief|SUCCEEDED`; `last_full_day` = вчера по Москве, `stale = f`; `brief_current` = `<вчера>|ok`, то есть `brief_day` совпадает с `last_full_day` - именно этого равенства требует правило показа цифр (AD-9). Любое `FAILED`, `stale = t` или расхождение `brief_day` с `last_full_day` - строка отклонения в журнале релиза и разбор в тот же день.

Кто что заполняет каждое утро: исполнитель релиза - строку в `docs/operations/releases/2026-09-22-m03.md`; Владислав - строку журнала сверки `docs/state/CABINET-RECONCILIATION.md`; Mike - открывает `/brief` и сверяет цифры с кабинетом.

Сводка «вчера» показывается с пометкой «предварительно» до 14 суток - поздние отмены WB (решение 5б1, AC 2.6). На 08.09 такой пометки в UI нет: `UNKNOWN`, чем она реализуется к 22.09.

## 5. Откат

Порядок обратный переключению. У релиза 2.6 три глубины отката - выбирается самая мелкая, которая закрывает проблему.

**Глубина 1 - режим «только статус».** Витрина остаётся на Postgres, но сводка убирается: экран показывает строку «Данные до …» и «Сводка ещё не считается» (режим Story 1.11), цифр нет. Нужен, когда сводка посчиталась неверно, а сбор в порядке. Прогон `brief` удаляется целиком по `run_id` (AD-3):

```bash
printf '%s\n' "SELECT set_config('proxima.tenant_id','amirova-test',false);
SELECT run_id, kind, status, started_at FROM collector_runs
  WHERE tenant_id='amirova-test' ORDER BY started_at DESC LIMIT 20;" \
| sudo docker exec -i proxima-ai-postgres-1 sh -c 'psql -U "$(cat /run/secrets/postgres_user)" -d proxima -v ON_ERROR_STOP=1 -tA'

cd /srv/proxima-ai/repo
sudo docker compose --profile jobs run --rm \
  -v /etc/proxima-ai/secrets/proxima_janitor_uri:/run/secrets/proxima_janitor_uri:ro \
  -e JANITOR_DATABASE_URI_FILE=/run/secrets/proxima_janitor_uri \
  control-plane python tools/delete_run.py --tenant amirova-test --run <uuid прогона brief> --dry-run
```
Сначала всегда `--dry-run`: он печатает счётчики транзитивного замыкания. Ожидается замыкание из одного прогона - на `brief` ничего не построено. **Не удалять прогон `norm`**: `brief` записан его потребителем (`collector_run_inputs`), и удаление `norm` унесёт сводку вместе с собой, а удаление `collect` или `backfill` - весь ряд. Убедившись в объёме, повторить без `--dry-run`. Форма вызова - §7 runbook 1.14 (janitor-URI compose пока не монтирует, отсюда `-v` и `-e`).

**Глубина 2 - витрина обратно на фикстуры.** Форма §7 runbook 1.14:

```bash
sudo sed -i 's/^WEBAPP_DATA_MODE=.*/WEBAPP_DATA_MODE=fixtures/' /srv/proxima-ai/repo/.env
cd /srv/proxima-ai/repo && sudo docker compose -f infra/compose.yaml -f infra/webapp.staging.compose.yaml up -d webapp
curl -s http://127.0.0.1:3000/brief | grep -o 'fixture-[a-z0-9-]*' | sort -u | wc -l
```
Ожидается: контейнер поднялся, счётчик фикстурных идентификаторов больше нуля (в postgres-режиме он тоже не нулевой - редакционная часть фикстурная, см. §3; надёжный признак фикстур - пометка «FX» на полосе метрик, которой в postgres-режиме нет). Если в §1 выбирался вариант А, вернуть ручной контейнер можно вместо compose-витрины:

```bash
sudo docker compose -f infra/compose.yaml -f infra/webapp.staging.compose.yaml stop webapp
sudo docker update --restart=unless-stopped proxima-webapp-staging
sudo docker start proxima-webapp-staging
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:3000/brief
```
Ожидается `200` - экран 1.14 на фикстурах, как был до релиза.

**Глубина 3 - вернуть код на тег 1.14.**

```bash
sudo git -C /srv/proxima-ai/repo checkout <тег релиза 1.14>
sudo cp -a /var/backups/proxima/repo.env-before-2.6 /srv/proxima-ai/repo/.env
sudo git -C /srv/proxima-ai/repo log --oneline -1
```
Тег 1.14 - `UNKNOWN` до 15.09. Копия `.env` - из §1. Утренние таймеры при этом не снимаются: они относятся к 1.14 и должны работать дальше; их снятие - откат 1.14 (§7 runbook 1.14), а не 2.6.

**Миграции не откатываются.** Additive-only; попытка откатить - нарушение AD-14 и способ потерять данные.

## 6. Запись

Ход релиза - в журнал `docs/operations/releases/2026-09-22-m03.md`. Файла на 08.09 нет; он создаётся копией `docs/operations/releases/TEMPLATE.md` заранее, до 22.09, и заполняется по ходу выполнения, а не по памяти после (`docs/operations/releases/README.md`). Формат имени - `YYYY-MM-DD-<release>.md`, то есть `2026-09-22-m03.md` при деплое 22.09; при переносе даты имя файла меняется вместе с ней. Шаблон рассчитан на 1.14 (блокеры B1-B10, шаги §0-§6, гейт цифр W10/W35, три утра) - для 2.6 таблицы заменяются на предусловия §0, шаги §1-§4 и семь утр этого файла.

Строку в `README.md` каталога релизов (таблица «Файлы») добавляет тот же исполнитель.

`CHANGELOG.md` в корне: при релизе исполнитель переносит накопленное из `## [Unreleased]` в раздел с тегом 2.6 и датой; ссылка на этот runbook и на журнал релиза - там же. Тег - `UNKNOWN` (§0 п. 11).

`docs/state/WORKS-TODAY.md`: после 2.6 становятся применимыми пункты, помеченные `NOT APPLICABLE` до переключения витрины - WT-36 (`data_status_current` свежий), WT-37 (норма и сводка за вчера), WT-40 (`/brief` в postgres-режиме показывает строку статуса и не показывает предупреждение); ожидание WT-06 меняется - фикстурных идентификаторов на экране становится меньше. Базу регрессии прогнать целиком и дописать результат.

Отдельный документ готовности для 2.6 (аналог `docs/state/RELEASE-READINESS-1.14.md`) - `UNKNOWN`: нужен ли он, решается вместе с планом на 2.6.

## Список `UNKNOWN` в этом черновике

| # | Что неизвестно | Кто закрывает / где |
|---|---|---|
| 1 | Релизный тег 2.6 и его форма; baseline-тег отката (тег 1.14) | Mike / исполнитель 1.14, §0 п. 11, §5 |
| 2 | Несёт ли тег 2.6 новые миграции сверх 018 | состояние `main` перед 22.09, §0 п. 9 |
| 3 | Статус Story 6.1 (`verification/golden/`) и CP-13 на 22.09 | Владислав, B1 в `RELEASE-READINESS-1.14.md`, §0 п. 2 |
| 4 | Выполнена ли ротация analytics-токена PA-13 на read-only | Mike, §0 п. 3 |
| 5 | Вариант решения по порту 3000 (вывести ручной контейнер или задать `PROXIMA_WEBAPP_PORT`) | Mike, §1 |
| 6 | Зачётное окно семи утр: 23-29.09 (D33) или 24-30.09 (AC Story 2.6) | Mike, §4 |
| 7 | Чем реализуется пометка «предварительно» до 14 суток (решение 5б1) | код витрины / Epic 5, §4 |
| 8 | Эталонный экран кабинета WB и фильтр для сверки | Владислав, `docs/state/CABINET-RECONCILIATION.md` |
| 9 | Нужен ли отдельный документ готовности к 2.6 | Mike, §6 |
| 10 | Фактические цифры дня релиза (заказы, выручка, норма, отклонение) | день релиза, журнал `2026-09-22-m03.md` |
| 11 | Версии образов и sha чекаута на 22.09 | день релиза, журнал |

## Открытые вопросы

1. **Ручной контейнер `proxima-webapp-staging` и compose-витрина конфликтуют по порту 3000.** Пункт «Октябрь» runbook 1.14 предлагает вывести ручной контейнер, но 2.6 наступает раньше октября. Нужно решение Mike до 22.09 (§1).
2. **Форма релизного тега 2.6 нигде не зафиксирована.** Для 1.14 форма `v2026.09.NN-2` записана в AC Story 1.14; для 2.6 аналогичной записи нет ни в `epics.md`, ни в `DECISIONS.md`.
3. **Окно семи утр в D33 и в AC Story 2.6 не совпадает** (23-29.09 против 24-30.09) - зависит от даты деплоя; закрывается вместе с датой.
4. **`/brief` остаётся гибридным экраном.** Дайджест, вердикт и «Критичные сигналы» - фикстуры с пометкой «FX», настоящие приходят с Epic 5, который заморожен по D35 до трёх утр SUCCEEDED. Считать ли релиз 2.6 принятым с фикстурной редакционной частью - вопрос Mike (по AC Story 2.6 - да: приёмка сформулирована как «открывает `/brief` и сверяет вчерашние заказы и выручку с кабинетом»).
5. **Пункт 1 §6 `RELEASE-READINESS-1.14.md`** (противоречивая пара текстов при «статус есть, сводки нет») закрыт текстами PR #124 - проверить на боевом экране в первое же утро после переключения, отдельного гейта на это нет.
6. **Шаг воронки едет тем же тегом** (D33), но в этом черновике не описан - нужна отдельная единица до 22.09.

## Сверить с `main` перед 22.09

Черновик писался до релиза 1.14. Перед исполнением перепроверить:

- `infra/webapp.staging.compose.yaml` - переменные, имя секрета, порт (менялся ли overlay);
- `services/webapp/src/lib/data/postgres-provider.ts` - что читает провайдер и какие карточки полосы метрик заполняются;
- `services/webapp/src/components/brief/brief-summary.tsx` - тексты предупреждений §3 (правились в #124);
- `tools/morning_run.sh` - состав и порядок шагов утренней цепочки;
- `docs/operations/release-m01.md` - формы доступа, §5 (юниты, drop-in PA-13), §7 (откат);
- `docs/operations/releases/2026-09-15-m01.md` - что фактически произошло 15.09 и какие отклонения записаны;
- `docs/state/RELEASE-READINESS-1.14.md` - статусы B1, B5, B6 на день релиза;
- `db/migrations/` - номер последней миграции релизного тега.
