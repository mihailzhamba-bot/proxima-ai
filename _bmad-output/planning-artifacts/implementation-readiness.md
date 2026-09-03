# Implementation Readiness - epics.md (30.08.2026)

# Проход 3 (30.08.2026) - спайн v3.3, E1 = 1.0-1.14 после перенумерации

Объект: `epics.md` (E1 = 15 историй 1.0-1.14: 1.3 разделена на 1.3/1.4, provision в 1.2, `cas_import.ts` + `--retrieved-at` в 1.5, RLS по грантам в 1.7, age в 1.12), `ARCHITECTURE-SPINE.md` v3.3. Узкий проход: закрытие N1, N2/N5, N4, N6, N7, H8 и размера 1.3; ссылки `Story 1.x`; решения вне спайна; старт 1.0/1.1. Проверено по коду: `services/collector/package.json:20`, `business-signal/raw-store.ts:92-114`, `tools/pg_local_roundtrip.sh:50-68`, `Makefile:4`, `docs/state/INVENTORY.md` №11.

## Вердикт прохода 3: PASS

- Все семь пунктов прохода 2 закрыты в epics.md и спайне; архитектурных решений вне спайна нет; 1.0 и 1.1 стартуют без вопросов к Mike.
- Остались только L: две устаревшие ссылки `Story 1.x` после перенумерации (строки 80 и 227), стилевые хвосты спайна (AD-1/6/11/13/15, Seed) и четыре локальных решения, которые исполнитель примет сам. Правки - 10 минут, ни один сеанс не блокируют.

## 1. Закрытие находок прохода 2

| # | Статус | Где / что осталось |
|---|---|---|
| N1 db-тесты | Закрыто | 1.2 + AD-12: `*.db.test.ts`, скрипт `test:db`, порядок «pytest `apply_migrations` → provision → `test:db`» (совпадает с `pg_local_roundtrip.sh:63-68`, `make test` идёт раньше `pg-roundtrip` в `Makefile:4`). Хвосты (L): `*.db.test.ts` матчится текущим glob `tests/**/*.test.ts` (`package.json:20`) - «`make test` их исключает» требует правки glob, способ не назван, самокорректируется на первом `make test`; `--test-concurrency=1` (N3) не записан ни в 1.2, ни в AD-12 - без него db-файлы 1.4-1.8 пойдут параллельно в одну БД |
| N2/N5 provision в harness | Закрыто | provision в 1.2 (LOGIN-роли, janitor + `GRANT DELETE`, `PROXIMA_TEST_DSN_<ROLE>`), AD-12 «`SET ROLE` не используется»; 1.4 под `PROXIMA_TEST_DSN_COLLECTOR`, 1.7 под `PROXIMA_TEST_DSN_JANITOR` - обе после 1.2. L: job читает `COLLECTOR_DATABASE_URI_FILE`, тесту дан DSN - тест сам пишет DSN во временный файл (одна строка, очевидно) |
| N4 `retrieved_at` | Закрыто | AD-2 + 1.5: `tools/cas_import.ts <file> --retrieved-at --source`, `backfill --source artifact:<sha_sales>,<sha_orders> [--retrieved-at]`, `run_day := mskDay(retrieved_at)`, сидирование harness тем же `cas_import.ts`; 1.0 и 1.13 ссылаются на него. L: «`retrieved_at` из манифеста» - манифест `raw-store.ts:110` лежит по `manifests/<run_id>/…`, по sha256 не найти; `cas_import.ts` обязан положить свой манифест, адресуемый sha256 (в AC 1.5 `backfill` идёт без флага, значит lookup нужен; раскладку исполнитель выберет сам) |
| N6 RLS-матрица | Закрыто | 1.7 + AD-12: ожидания из грантов AD-11, `permission denied` для ролей без гранта. L: последняя фраза AD-11 («под каждой ролью … из каждого view … = 0, без ошибки прав») не поправлена и противоречит AD-12; исполнитель 1.7 идёт по AD-12 |
| N7 restore-check | Закрыто | AD-17 + 1.12: `age -d -i /etc/proxima-ai/secrets/backup_age_key.txt \| gunzip \| psql proxima_test`, формат `pg_dump \| gzip \| age`. Сервером не подтверждено: INVENTORY №11 говорит только «age → S3»; существование identity-файла и шифрование локальной копии проверяет 1.0 [Claude] (`sudo test -f`, чтение снятого скрипта), иначе юнит 1.12 на сервере не запустится. OpenHands не блокирует |
| H8 ArtifactSink | Закрыто | AD-4 v3.3: собственный `recording-client.ts` поверх `raw-store.ts`/`fetchTransport`, `RecordedHttpClient` не трогается; 1.1 = интерфейс + in-memory, 1.3 = `WbArtifactSink` в БД. L: AR5 (epics:59) и AD-1 всё ещё говорят «поверх/через `RecordedHttpClient`» |
| Размер 1.3 | Закрыто | 1.3 = 011 + `recording-client.ts` + `WbArtifactSink` + `run-ledger.ts` + `log.ts` + тесты `pg_policies`/running-succeeded-failed ≈ 550-650, 5 областей; 1.4 = 012 + `collect.ts` + наблюдения + `_latest` + тесты ≈ 500-600. Обе влезают |

## 2. Ссылки `Story 1.x` вне заголовков (10 упоминаний)

| Строка | Ссылка | Вердикт |
|---|---|---|
| 80 (FR Coverage) | «бэкфилл истории (Story 1.3: артефакт 30.08 + живой хвост)» | **Битая**: бэкфилл = 1.5; 1.3 = реестр/приёмник |
| 136 (1.0) | вход для Story 1.5; `cas_import.ts` на VPS в Story 1.14 | Верно (1.5 бэкфилл; 1.14 исполняет runbook) |
| 151 (1.1) | `WbArtifactSink` и `recording-client.ts` в Story 1.3 | Верно |
| 195 (1.4) | `collect.ts` использует Story 1.3 | Верно, назад |
| 225 (1.6) | синтетические артефакты Story 1.5 | Верно, назад |
| 227 (1.6) | сверка W10/W35 на VPS в Story 1.13 | **Битая**: 1.13 = runbook (документ), VPS = 1.14 |
| 253 (1.8) | provision из Story 1.2 | Верно, назад |
| 295 (1.11) | живой экран в Story 1.14 | Верно |
| 305 (1.12) | `proxima-pg-backup.sh` из Story 1.0 | Верно, назад |
| 331 (1.14) | «Stories 1.0-1.12 смержены, …, runbook» | L: 1.13 назван словом «runbook»; точнее «1.0-1.13» |

Ссылок вперёд на несуществующие истории нет. Ссылки Epic 2/3 (2.1↔2.2, 2.3→2.6, 2.4→2.3, 2.5→2.6, 3.3→3.0, 2.1→5.1, 1.10→2.2) верны.

## 3. Решения вне спайна

Архитектурных нет. В 1.2 всё покрыто AD-12: временный каталог секретов = «пароли из временных файлов», `PROXIMA_TEST_DSN_<ROLE>`, `test:db`, `*.db.test.ts`, `BYPASSRLS` sandbox. Локальные, исполнитель примет сам: параметры provision «путь к `psql`, каталог секретов» (AD-11 знает только `docker compose exec postgres`); те же параметры для `test_db_refresh.sh` в harness (1.8; roundtrip-база называется `proxima`, `pg_local_roundtrip.sh:50` - `pg_dump proxima` сработает); правка glob `make test`; раскладка манифеста `cas_import.ts`; имена `src/wb/{artifact-sink,recording-client,run-ledger}.ts`, `log.ts`, `tools/cas_import.ts` отсутствуют в Structural Seed. Устаревшие фразы спайна из прохода 2 не поправлены: AD-6 «`collect --from 2026-03-01 --backfill`» (и AR11 epics:65), AD-13 «`set_config(…, true)` первым statement транзакции (3)» vs AD-3/1.3 (GUC на сессию), AD-15 и AR2 (epics:56) «`WEBAPP_DATA_DATABASE_URI` из секрета», AD-12 refresh «`GRANT SELECT`» vs «`GRANT ALL`» там же и в 1.8, Seed `016_brief_daily_roles`, шапка Epic 1 «спайн v3.2».

## 4. Старт 1.0 и 1.1

Оба стартуют без вопросов к Mike; допущения прохода 2 (раздел 4) в силе. 1.0 [Claude] дополнительно проверяет на сервере формат локального дампа и наличие `backup_age_key.txt` (N7) - read-only, нового решения не требует. 1.1: H8 снят AD-4, `artifact-sink.ts` в Given; блок «шаги 3-10» по-прежнему без пометки «[конвейер: Claude + Mike]» (N12, L).

## Что поправить (10 минут, не блокирует)

1. epics.md: строка 80 → Story 1.5; строка 227 → Story 1.14; строка 331 → «1.0-1.13»; шапка Epic 1 → v3.3; AR5 → «поверх `raw-store.ts`/`fetchTransport`»; AR11 → артефакт-режим + `collect --date-from`; в 1.2 Given - `--test-concurrency=1`; в 1.0 Then - проверка `backup_age_key.txt` и формата дампа.
2. Спайн (memlog, без новых AD): AD-1/AD-6/AD-11 (последняя фраза)/AD-13/AD-15 привести к AD-2/AD-3/AD-4/AD-12; Seed - `016` и файлы `src/wb/*`, `tools/cas_import.ts`.

---

# Проход 2 (30.08.2026) - спайн v3.2, epics E1-E3 после перереза

Объект: `epics.md` (E1 = 1.0-1.13, E2 = 2.1-2.6, E3 = 3.0-3.4; сентябрь = 25 единиц, 5 [Claude]), `ARCHITECTURE-SPINE.md` v3.2. Вопрос гейта тот же: сможет ли OpenHands (без токенов и сервера) реализовать истории, не придумывая незаписанных решений. Проверено по коду: `tools/pg_local_roundtrip.sh`, `services/collector/package.json`, `Makefile`, `.github/workflows/verify.yml`, `tools/verify_migrations.py`, `db/migrations/009`, `business-signal/{http,raw-store,types}.ts`, `cli/stockout-signal.ts`, `tools/wb_async_report.py`, `tools/tests/test_{wb_async_report_postgres,runtime_roles_schema}.py`, `tools/apply_migrations.py`, `infra/{compose.yaml,bootstrap/provision-postgres-diagnostics.sh}`, `.gitignore`, ветки `origin/mihailzhamba-bot/pmm29-contracts` и `origin/ai/pa-50`, `docs/state/{API-FACTS,INVENTORY}.md`, `SPEC.md`.

## Вердикт прохода 2: CONCERNS (узкий)

- 1.0 и 1.1 стартуют 01.09 без вопросов к Mike (раздел 4). Архитектурных пробелов уровня H не осталось: H1-H7 закрыты в спайне v3.2, H8 частично.
- Цепочку ломают два места в Story 1.6 (N5, N6) и одно в 1.4 (N4). Все три чинятся одним-двумя предложениями в epics.md и memlog спайна, новых AD не нужно. Story 1.3 не влезает в сеанс - делить.
- До выдачи OpenHands истории 1.3 и дальше - правки из раздела «Что сделать» (документы, ~1 час).

## 1. Статус находок прохода 1

| # | Статус | Где закрыто / что осталось |
|---|---|---|
| H1 harness | Закрыто | AD-12 v3.2 (harness в `pg_local_roundtrip.sh`, `PROXIMA_TEST_POSTGRES_DSN`, `SET ROLE`), Story 1.2 отдельной единицей. Остались локальные N1-N3 |
| H2 artifact-replay | Закрыто | AD-2 (импорт в CAS, два sha256, `run_day := mskDay(retrieved_at)`, хвост `collect --date-from run_day-3`), Stories 1.0/1.4/1.12 (runbook: `backfill --source artifact:…` + `collect --date-from 2026-08-27`). Осталось: N4 (`retrieved_at` не доезжает до `backfill`); AD-6 и AR2/AR11 в epics.md всё ещё пишут «`collect --from 2026-03-01 --backfill`» - устаревшая фраза (L) |
| H3 2.1 ↔ 2.2 | Закрыто | 2.1 = принять pmm29, 2.2 ссылается назад на `signal.schema.json`; diagnosis-валидатор отложен до 5.1. AD-10 без оговорки «в M-05» (L) |
| H4 sandbox | Закрыто | AD-12 `BYPASSRLS` + `GRANT ALL` в `proxima_test`; Story 1.7 |
| H5 1.10 на сервере | Закрыто | 1.10 → 1.11 (юниты, CI) + 1.12 (runbook); `proxima-pg-backup.sh` снимает 1.0 [Claude]; AD-17 определяет restore-check. Осталось N7 |
| H6 воронка PK / обёртка | Закрыто | AD-5: PK `(tenant_id, nm_id, calendar_day, source, canonical_sha256)` без `run_id`; два kind `funnel_csv_download`/`funnel_csv_promote`; строку фазы 1 создаёт сам скрипт. 3.1-3.3 согласованы |
| H7 имена секретов | Закрыто | Conventions «Конфигурация и секреты», правило (2) в шапке эпиков. AD-15 и AR2 в epics.md всё ещё говорят `WEBAPP_DATA_DATABASE_URI` без `_FILE` (L, Story 1.8 верна) |
| H8 ArtifactSink | Частично | AD-4 и 1.1 вводят `ArtifactSink`/`WbArtifactSink`. Но `RecordedHttpClient` (`http.ts:65-71`) принимает `runId + BusinessSignalRawStore + SignalRepository` (9 методов, `types.ts:96-106`), а `http.ts` под AD-18 read-only. «Поверх» = адаптер `SignalRepository { recordRawArtifact → sink.record; остальные 8 - throw }`. Одно предложение в AD-4 или в Given 1.1 |
| M1 GUC для autocommit | Закрыто | AD-3: `set_config(…, false)` первым statement соединения. AD-13 всё ещё говорит «`set_config(…, true)` первым statement транзакции (3)» - внутреннее противоречие (L) |
| M2 RLS-матрица vs гранты | **Нет** | AD-11 и 1.6 без изменений: «каждая роль × каждый view». См. N6 |
| M3 `FOR INSERT` + USING | Закрыто неявно | Шаблон AD-11 = `FOR SELECT\|ALL`; гейт `verify_migrations.py:46-50` требует `USING` всегда, PG для INSERT его не примет - шаблон обходит проблему |
| M4 provision без Docker | Частично | 1.7: «путь к `psql` параметром». `SECRETS_DIR` и пропуск `chown 1010` вне root не названы; генерация паролей - образец `provision-postgres-diagnostics.sh:5-34` (`secrets.token_urlsafe(48)`), исполнитель возьмёт |
| M5 restore-check | Закрыто | AD-17 отделяет проверку бэкапа от refresh. См. N7 |
| M6 гейт `CURRENT_DATE` | Частично | 1.5: «гейт: `CURRENT_DATE` в `db/` отсутствует» - файл не назван; кандидат один (`verify_migrations.py` + кейс в `tools/tests/test_verifiers.py`) |
| M7 `.env.task` | Закрыто | `infra/openhands/env.task.template` (проверено `git check-ignore`: не игнорируется) |
| M8 простой postgres | Закрыто | 1.12: «пересоздаёт контейнер postgres на ~10 с» |
| M9 3 / 7 утр | Закрыто | 1.13 «три утра подряд (CAP-1)», 2.6 «семь утр (CAP-5)», 1.12 «наблюдение 3 дня» |
| M10 owner-секреты | Закрыто | AD-15 + 1.8: сервис `control-plane-admin`; CI проверяет `config` на отсутствие owner-секретов у `collector` |
| M11 действие Mike в UI | Закрыто как решение | 1.10/2.5: `make verify` + vitest через мок `Pool`, живой экран в 1.13/2.6. Приемлемо по D7; см. N10 |
| M12 `record_fixture.ts` | Закрыто | 1.1; `tools/anonymize_fixture.py` в 1.0 |
| M13 NFR11 JSON-лог | Закрыто | Правило (3) шапки эпиков, Conventions «Логи», 1.3 `log.ts`, 2.3 `log.py` |
| M14 pa41 | Нет | Story 4.0 не появилась; октябрь, не блокирует |
| L1 seed `016_brief_daily_roles` | Нет | Structural Seed без изменений |
| L2 «до 2.1» | Закрыто | 1.9: «до Story 2.2» |
| L3 vps-contract `allowed_now=false` | Нет | не упомянут в 1.12/1.13 |
| L4 виртуальные часы в 3.1 | Нет | |
| L5 `text + CHECK` | Нет | самокорректируется на первом `make verify` |
| L6 `172.17.0.1:5432` из зоны | Нет | 1.12 «`env.task` в зону» без проверки достижимости (INVENTORY №69: D8 на хосте не реализован) |
| L7 два канона | Частично | AD-2: job'ы - CAS; пробы - `~/signal-inputs` |
| L8 деплой-шаг 1.1 | Нет | см. N12 |
| L9 `IN DATABASE` | Закрыто | AD-12 |

Итог: H - 7 закрыто, 1 частично; M - 10 закрыто, 2 частично, 2 нет (M2, M14); L - 3 закрыто, 1 частично, 5 нет.

## 2. Новые пробелы после перереза

| # | Где | Что | Правка |
|---|---|---|---|
| N1 | 1.2 | «Тег `db`» в `node:test` как механизм не существует. `package.json` гоняет `tsx --test tests/**/*.test.ts` в `make test` - до roundtrip и без DSN; любой `*.test.ts` под `tests/` попадёт и туда. Не записано: суффикс/каталог db-тестов, поведение без DSN в `make test`, порядок применения миграций (сейчас их применяет pytest на строке `pg_local_roundtrip.sh:65`, а 1.2 ставит TS-тесты *до* pytest) | Given 1.2: db-тесты = `tests/db/*.dbtest.ts` (не матчатся `*.test.ts`), скрипт `test:db` = `tsx --test --test-concurrency=1 tests/db/*.dbtest.ts`, без DSN - падает (roundtrip - единственный вызов); roundtrip перед `test:db` явно вызывает `apply_migrations.py --env-file $WORK/roundtrip.env` (файл уже есть, `:55-61`; проверка идемпотентности `:67-72` останется верной) |
| N2 | 1.2-1.6 | Как job (`collect.ts` по `COLLECTOR_DATABASE_URI_FILE`, `delete_run.py` по `JANITOR_DATABASE_URI_FILE`) в harness оказывается «под `SET ROLE`»: roundtrip даёт только superuser-DSN, URI-файлов нет, хука на `SET ROLE` в job нет. Под superuser RLS обходится - тесты «без GUC → 0» бессмысленны | Top-1: provision-скрипт (часть 1.7) перенести в 1.2 - harness после миграций запускает `provision-runtime-roles.sh` в локальном режиме, получает LOGIN-роли и URI-файлы в `$WORK/`, job'ы подключаются как в проде, `SET ROLE` не нужен вовсе (снимает и N5; одна строка memlog в AD-12). Запасной вариант: `PROXIMA_TEST_SET_ROLE` - job выполняет `SET ROLE` после подключения, если переменная задана (образец `test_runtime_roles_schema.py:155-170`) |
| N3 | 1.2, 1.6 | `node:test` запускает файлы параллельно в отдельных процессах; общая БД + сидирование `_current` для RLS-матрицы + `delete_run` в одном прогоне - порядок не задан | Один упорядоченный db-файл на историю, `--test-concurrency=1` (см. N1) |
| N4 | 1.4, 1.0 | `backfill --source artifact:<sha_sales>,<sha_orders>` получает только sha256. `retrieved_at` живёт в API-FACTS (1.0) и в манифесте CAS (`raw-store.ts:92-110`, путь по `run_id`, обратного индекса по sha256 нет). Откуда `run_day` и `wb_raw_artifacts.retrieved_at` - не записано. Чем 1.0 кладёт файлы в CAS и по какой раскладке (`objects/sha256/<hex[0:2]>/<hex>`, 0600, каталоги 0700 - `raw-store.ts:85,16-22`) - не сказано. Откуда в harness «синтетические артефакты с `retrieved_at`» - не сказано | AD-2 / Given 1.4: флаг `--retrieved-at <ISO>` обязателен в режиме `artifact` (из API-FACTS: sales 05:59:39Z, orders 06:00:41Z - один MSK-день, одного флага хватит); синтетика в harness = тест пишет два JSON в `$WORK/raw` через `BusinessSignalRawStore.persist` (переиспользование разрешено AD-18) и вызывает `backfill` с их sha256. В 1.0 назвать раскладку и владельца |
| N5 | 1.6 → 1.7 | **Порядок ломает 1.6**: `delete_run` под `proxima_run_janitor` требует `GRANT DELETE`, который по AD-3/AD-11 живёт только в bootstrap (гейт `verify_migrations.py:35-39` DELETE не пропускает), а bootstrap - Story 1.7, после 1.6 | Снимается N2 top-1 (provision в 1.2). Иначе - поменять 1.6 и 1.7 местами (1.7 зависит только от 1.5) |
| N6 | 1.6, AD-11 | = M2. AC «каждая роль × каждый view: с GUC > 0» невыполним: `proxima_webapp_readonly` и `proxima_job_norm` не имеют SELECT на `stg_wb_*_obs` → `stg_wb_*_latest` под ними = `permission denied`, не «> 0» (4 из 16 пар в Epic 1; в Epic 2 добавятся `norm_daily_current`/`brief_current` под collector). Исполнитель «починит» расширением грантов - не в ту сторону | AD-11 + 1.6: «матрица = пары роль × view, где у роли SELECT на все базовые таблицы view (по грантам AD-11); для остальных пар ожидается `permission denied`» |
| N7 | 1.11, AD-17, 1.0 | Restore-check: `pg_restore` неприменим - бэкап = `pg_dump … \| gzip` → `<date>-proxima.sql.gz` (INVENTORY №126, plain SQL), восстанавливать `gunzip \| psql -v ON_ERROR_STOP=1`. Если локальная копия тоже зашифрована age (`backup_age_recipient`), на сервере нужен identity-файл - путь не записан; без него юнит невыполним | 1.0 [Claude] фиксирует формат локального файла и путь age-identity (или «локальная копия не шифруется»); AD-17/1.11: `gunzip \| psql` вместо `pg_restore` |
| N8 | 1.5 ↔ 1.13 | `floor` режима `artifact` = «первый день артефакта» (01.03: `orders` с `2026-03-01T00:51:40`), а 1.13 ждёт «дни с 02.03.2026»; FR3 говорит «с 01.03». Полнота 01.03 в `flag=0` не доказана (API-FACTS:42: окно режет по дате; 28.02 есть в `flag=1`, но нет в `flag=0`) | Записать одно правило: `floor = первый день + 1` и в 1.5, и в 1.13 (консервативно, как для живого `--from`). W10/W35 не зависят: 01.03.2026 - воскресенье, ISO W09 |
| N9 | 3.2 | `wb_async_report.py` создаёт `collector_runs` под owner-URI без GUC: owner = superuser compose → RLS обходится, INSERT проходит; FK `tenant_id → tenants` при удалённом автосоздании (`:296`) даёт «нет tenant - ошибка». **Приемлемо.** Но AD-3 требует `set_config` на соединении для Python-job'ов, а в скрипте его нет (grep пуст) | В Given 3.2 одна строка: «`set_config('proxima.tenant_id', tenant, false)` первым statement после подключения (AD-3), хотя owner RLS не подчиняется» |
| N10 | 1.10 | «Одно действие = `make verify`» для UI-истории: приемлемо по D7 и симметрично 2.5. Риск: строка статуса впервые видна глазами в 1.13 на сервере; ошибка форматирования = релизный цикл. `DataProvider` из pa-50 (`provider.ts`: `getBrief`, `getMetrics`) метода статуса не имеет - 1.10 расширяет интерфейс и fixtures-provider (не сказано, но очевидно) | Не блокирует. Дёшево: в 1.10 «fixtures-provider отдаёт фикстурный статус; `npm run dev` показывает строку без БД» - тогда `bmad-qa-generate-e2e-tests` снимет экран до 1.13 |
| N11 | 2.1 | Ветка pmm29 = 26 файлов, среди них `.autopilot/{state.js,dashboard.html,README.md}`, `AGENTS.md`, служебные `spec/tickets` - переносить нельзя; `services/collector/src/contracts/*.ts` генерируются, не копируются. `diagnosis/` ветка не трогает - «пакет не трогается» выполнимо | В 2.1 назвать подмножество: `contracts/{signal,diagnosis,decision-record}.schema.json`, `contracts/examples/*`, `tests/product-contracts.test.ts`, `tools/verify_contracts.py`; типы - `make codegen` |
| N12 | 1.1 | Блок «When конвейер проходит шаги 3-10 … Then задокументированы в `docs/operations/releases/…`» читается как AC сеанса OpenHands, у которого нет ни сервера, ни права на тег | Пометить блок «[конвейер: Claude + Mike]»; сеанс отвечает за первый Given/When/Then |
| N13 | 1.8 | CI «`apply-migrations` внутри `control-plane-admin` против service-container PG16»: контейнер из `docker compose run` не видит GH service-container по имени `postgres` (`jobs.env`: `POSTGRES_HOST=postgres`); `secrets: file:` требует файлов-пустышек в CI | В CI поднимать compose-сервис `postgres` с пустышками секретов, не GH service. Локально, самокорректируется |
| N14 | SPEC:66 | «первая единица M-01 (расписание + бэкфилл) уходит в OpenHands не позже 08.09» - скобка устарела: первая единица = 1.0/1.1 (WB-клиент), расписание = 1.11 | L; править при следующем касании спеки |

Порядок 2.1 → 2.2: ссылок вперёд нет (2.2 `$ref` на `signal.schema.json` из 2.1; `types.ts` удаляется в 2.2, 1.9 ссылается на 2.2). Порядок 3.0 → 3.3: чисто.

## 3. Размер (ориентир ≤ ~5 областей, ≤ ~600 строк)

| История | Состав | Вердикт |
|---|---|---|
| 1.3 | 011 + 012 (~150), `collect.ts` + модель прогона (~250), `WbArtifactSink` в БД + писатель наблюдений (~150), `log.ts`, тесты idempotent/drift/`pg_policies` (~250) | **800-1000, 6 областей - не влезает.** Делить: 1.3a = 011 + модель прогона (RUNNING/SUCCEEDED/FAILED) + `WbArtifactSink` в `wb_raw_artifacts` + `log.ts` + тест `pg_policies`; 1.3b = 012 + наблюдения + `_latest` + idempotent replay + `WB_SCHEMA_DRIFT` |
| 1.4 | режим artifact + живой режим (пагинация, `--resume`, виртуальные часы) + чтение CAS + регистрация + тесты | 500-600, на грани; после N4 влезает |
| 1.5 | 013 + агрегатор + `data_status_current` + гейт + self-heal `dateFrom` + тест S1/S2 | 500-600, на грани |
| 2.2 | 3 схемы + примеры + codegen → webapp + удаление `types.ts` + импорты + `msk_day.py` | 500-700, 5 областей - на грани; `msk_day.py` → 2.3 снимает |
| 3.1 | 014 + `funnel-v3.ts` (активные nmId, пакеты, бюджет, окно) + `facts/funnel-daily.ts` + тесты + `morning_run.sh` | 500-600, на грани |
| остальные (1.1, 1.2, 1.6-1.12, 2.1, 2.3-2.5, 3.2, 3.3) | ≤ 500 | Влезают |

Сентябрь при делении 1.3: 25 → 26 единиц.

## 4. Первая единица 1.0 + 1.1

**1.0 [Claude] - стартует.** Есть: формула вердикта `flag=0`, пути и токен, CAS-импорт с sha256/`retrieved_at` в API-FACTS, `proxima-pg-backup.sh` в git, `anonymize_fixture.py` со спецификацией обезличивания, целевые каталоги фикстур, правки хука/CI/`PUPPETEER_SKIP_DOWNLOAD`, одно действие Mike. Допущения, которые Claude принимает сам и пишет в PR: раскладка CAS `objects/sha256/<hex[0:2]>/<hex>` 0600/0700 владелец 1010 (N4); окно фикстур `orders`/`sales` = две полные недели с эталонными суммами S1/S2 в `tests/fixtures/wb-api/README.md` (6 месяцев в 200 КБ не влезают); формат локального дампа и age-identity (N7).

**1.1 - стартует.** Есть: реестр 4 эндпоинтов с бюджетами, гейт `verify_wb_client.py` (область `src/wb/` + `src/jobs/` по AD-4), `ArtifactSink` in-memory, CLI-флаги токенов по образцу `stockout-signal.ts:28-33`, `record_fixture.ts`, тесты с граничными значениями, `FixtureTransport` и путь фикстур. Допущения: «поверх `RecordedHttpClient`» = адаптер `SignalRepository` с одним живым методом (H8); шаги 3-10 - конвейер, не сеанс (N12). Вопросов к Mike нет.

## Что сделать до выдачи 1.3+ (порядок)

1. `bmad-create-epics-and-stories` (epics.md): provision-скрипт из 1.7 в 1.2, harness без `SET ROLE` (N2/N5; либо swap 1.6 ↔ 1.7 + `PROXIMA_TEST_SET_ROLE`); в 1.6 матрица по грантам (N6); 1.3 → 1.3a/1.3b; в 1.2 Given - `tests/db/*.dbtest.ts`, `--test-concurrency=1`, явный `apply_migrations.py` перед `test:db` (N1, N3); в 1.4 - `--retrieved-at` и сидирование CAS через `BusinessSignalRawStore.persist` (N4); в 1.5/1.13 - `floor = первый день + 1` (N8); в 3.2 - `set_config` (N9); в 2.1 - подмножество файлов pmm29 (N11); в 1.1 - пометка «[конвейер]» (N12); в 1.11 - `gunzip | psql` (N7); в 1.0 - раскладка CAS, окно фикстур, формат дампа/age (раздел 4).
2. `bmad-architecture` (memlog, без новых AD): AD-11 - RLS-тест по грантам (N6); AD-12 - provision в harness вместо `SET ROLE` (N2); AD-2 - `--retrieved-at` (N4); AD-17 - `gunzip | psql` (N7); AD-4 - адаптер над `RecordedHttpClient` (H8); устаревшие фразы: AD-6 «`collect --from 2026-03-01 --backfill`», AD-13 «`set_config(…, true)` в транзакции», AD-15 «`WEBAPP_DATA_DATABASE_URI` из секрета», Seed `016_brief_daily_roles` (L1).
3. 1.0 и 1.1 выдавать сейчас, не дожидаясь п. 1-2.

---

# Проход 1 (30.08.2026) - исходный отчёт

Объект: `_bmad-output/planning-artifacts/epics.md` (5 эпиков, 28 историй; сентябрь = E1-E3, 22 единицы, 6 [Claude]). Эталоны: `SPEC.md` + `glossary.md`, `ARCHITECTURE-SPINE.md` v3.1 (AD-1..18, memlog), `DECISIONS.md` D1-D22, `docs/state/API-FACTS.md`, ревью нарезки v1 (`epics-review-2026-08-30.md`). Режим: read-only, скептик-исполнитель. Вопрос гейта один: сможет ли OpenHands (без токенов и сервера) реализовать истории, не придумывая решений, которых нигде не записано.

Проверено по коду репо (не по документам): `tools/verify_migrations.py`, `tools/pg_local_roundtrip.sh`, `Makefile`, `.github/workflows/verify.yml`, `.openhands/{hooks/verify-gate.sh,setup.sh}`, `.gitignore`, `db/migrations/001-010` (шаблон 009, колонки 003/005), `infra/{compose,webapp.compose}.yaml`, `infra/vps-contract.json` + `verify_vps_contract.py`, `verify_runtime_boundary.py`, `services/collector/src/business-signal/{http,raw-store,secrets,wb-client,types,repository,date-window}.ts`, `services/control-plane/pyproject.toml`, `diagnosis/{validator,models}.py` + `schema/diagnosis.draft.v1.json`, `tools/{apply_migrations,wb_async_report,verify_contracts}.py`, `tools/generate_contract_types.mjs`, ветки `origin/ai/pa-50` и `origin/mihailzhamba-bot/pmm29-contracts`, `docs/state/{INVENTORY,WEB-STATE,MIGRATION-GAPS,WORKS-TODAY}.md`, локальные `fixtures/wb-api/`.

## Вердикт: CONCERNS

- Критические C1-C6 из ревью v1 закрыты (раздел 0). Спайн v3.1 и нарезка в целом согласованы.
- Первые единицы 1.0 и 1.1 можно запускать 01-08.09 после трёх уточнений (раздел 6) - ни одно не требует переписывать спайн.
- Цепочка 1.2 → 1.6 и истории 2.1, 3.1, 3.2 в текущем виде заставят исполнителя принимать 8 незаписанных решений (H1-H8); три AC невыполнимы как записаны (1.6 «sandbox видит > 0», 2.1 «validator читает contracts/», 3.1 «повтор - 0 новых»). Это не FAIL плана, но FAIL этих трёх историй до правки.
- Что чинить и каким скиллом - в разделе «Находки». Порядок: сначала `bmad-architecture` (5 поправок спайна), потом `bmad-create-epics-and-stories` (перерез 1.2/1.10/2.1-2.2/3.2 и AC), `bmad-spec` только для окна приёмки CAP-1/CAP-5.

## 0. Критические правки ревью v1 - закрыты ли в текущем epics.md

| # | Суть | Статус в epics.md / спайне v3.1 |
|---|---|---|
| C1 | NOLOGIN-роли нужны в Epic 1, а создавались в 016 | Закрыто: 1.2 создаёт все 4 роли в 011; политики/гранты в миграции таблицы (1.4, 2.3, 2.4, 3.1); memlog v3.1 AD-11 |
| C2 | Пропуски нумерации миграций между E2/E3 | Закрыто правилом «целевые номера, вторая ветка перенумеровывает» (шапка Epic 1, AD-14); литералов N/N в AC нет |
| C3 | Janitor-политики только для 011/012 | Закрыто: каждая миграция с `run_id` называет janitor; тест `pg_policies` в 1.2 и 1.5 |
| C4 | `backfill.ts` без хозяина | Закрыто: Story 1.3 |
| C5 | AD-9 vs статус на /brief в M-01 | Закрыто: AD-9 «режим только статус», 1.9 ссылается на него |
| C6 | Живые вызовы внутри сеанса OpenHands | Закрыто: 1.0 и 3.0 [Claude]; memlog «живые вызовы и record_fixture - только Claude» |

Из существенных v1 остались открытыми: H8 (harness для DB-тестов и provision без Docker), M1 (no-op шаги в `morning_run.sh` - решено частично: шаги добавляются в своих эпиках), M4 (JSON-логи NFR11 - ни в одном AC), M7 (действие Mike в 1.9 требует локальной БД), M8 (CAP-1 «3 дня», CAP-5 «7 утр»), M10 (pa41 без истории).

## 1. Трассировка вперёд: артефакт → история

### CAP-1..8

| CAP | Истории | Пробел |
|---|---|---|
| CAP-1 ежедневный сбор | 1.2, 1.4, 1.10, 1.11 | Success «три дня подряд» - ни одна история не закрывает эпик по трём утрам (1.11 наблюдает одно) |
| CAP-2 бэкфилл | 1.3, 1.11 | Режим `--source artifact` не существует в спайне (H2) |
| CAP-3 статус данных | 1.4, 1.9, 1.11 | - |
| CAP-4 норма | 2.3, 2.6 | - |
| CAP-5 сводка | 2.4, 2.5, 2.6 | Success «7 предыдущих утр» - 2.6 наблюдает одно утро |
| CAP-6 воронка | 3.0-3.3 | - |
| CAP-7 аномалии | 4.1-4.3 (контуры) | Заявлено как контуры, ок |
| CAP-8 план действий | 5.1-5.3 (контуры) | Ок |

### Constraints спеки (13)

| Constraint | История | Пробел |
|---|---|---|
| Только READ-эндпоинты из реестра | 1.1 | - |
| Канал = `/brief` | 1.9, 2.5 | - |
| Без auth, заморозки | 1.8/1.9/2.5 («auth-зона не изменена») | Заморозка `services/control-plane/src/proxima/` ничем не проверяется (AD-18) - низко |
| Тесты на фикстурах; новый ответ = фикстура (канон `~/signal-inputs` + S3) | 1.0, 3.0 | Два «канона» полных ответов: `~/signal-inputs/fixtures` (ручные пробы, D5/D15) и CAS `PROXIMA_RAW_DIR` (job'ы, AD-1/AD-17). Не конфликт, но исполнителю 1.3 надо знать, откуда читать артефакт 30.08 (H2) |
| Обратимость `run_id` | 1.2, 1.5 | - |
| Multi-tenant RLS | 1.2, 1.4, 2.3, 2.4, 3.1 | - |
| Норма = медиана 14 | 2.3 | - |
| Переиспользовать ветки: pmm-20, pa41, pmm29, pa-50 | 4.1, -, 2.2, 1.8 | **pa41 - сирота**: ни истории на мерж/перенумерацию, ни на писателя `fact_order_counts`, который нужен 4.1 для сверки. Октябрь, но constraint явный |
| Среды: `proxima_test`, сандбокс | 1.6 | AC невыполним под RLS (H4) |
| Сервер только чтение; «деплой»; секреты не покидают VPS | 1.1 (шаг 8), 1.11, 2.6, 3.3 | 1.10 требует файл с сервера (H5) |
| Единица работы = сеанс + PR + одно действие | все | Размер 1.2, 1.10, 2.1, 3.2 (раздел 5); действие Mike в 1.9/2.5 - не одно (M11) |
| Первая единица до 08.09 | 1.0/1.1 | Реалистично при старте 1.0 01.09 |
| `WORKS-TODAY.md` перед релизом | 1.1, 1.11, 2.6, 3.3 | - |

### AD-1..18

| AD | Истории | Пробел |
|---|---|---|
| AD-1 доказательство раньше факта | 1.2 | `RecordedHttpClient` требует `SignalRepository` business-signal (9 методов, пишет в `business_signal_raw_artifacts`) - адаптер в `wb_raw_artifacts` не записан (H8) |
| AD-2 наблюдения/версии | 1.2, 1.4 | Режим artifact-replay не описан (H2) |
| AD-3 три вида транзакций, delete_run | 1.2, 1.5; Python - 2.3/2.4 неявно | GUC для autocommit-шагов (1), (2), FAILED под RLS `WITH CHECK` не определён для TS (M1) |
| AD-4 один клиент, гейт, фикстуры | 1.0, 1.1 | `tools/record_fixture.ts` - **сирота** (нет ни в 1.0, ни в 1.1); имена env для путей токенов (M3) |
| AD-5 воронка | 3.1, 3.2 | PK с `run_id` против «повтор - 0 новых» (H6); владелец строки `collector_runs kind=funnel_csv` при двух фазах не назван (H6) |
| AD-6 расписание, образы | 1.7, 1.10 | Бэкфилл в AD-6 = живой `collect --from --backfill`; нарезка заменила на artifact-replay без правки AD (H2) |
| AD-7 время, stale | 1.1, 1.4, 2.1 | Гейт на `CURRENT_DATE` в `db/` - файл не назван (M6) |
| AD-8 норма | 2.3 | - |
| AD-9 сводка, provider | 1.9, 2.4, 2.5 | `WEBAPP_DATA_DATABASE_URI` «из секрета» - compose `secrets:` даёт файл, webapp читает env; конвенция `_FILE` не записана (M3) |
| AD-10 контракты | 2.1, 2.2 | Схема `diagnosis` в пакете и в pmm29 - разной формы; «копия удаляется» = переписать пакет (H3) |
| AD-11 роли | 1.2, 1.6 | RLS-тест «каждая роль × каждый view» противоречит собственной матрице грантов AD-11 (M2) |
| AD-12 среды, сандбокс | 1.6 | `proxima_sandbox` без политик видит 0 строк в RLS-таблицах (H4); provision через `docker compose exec` невыполним в roundtrip на маке (M4) |
| AD-13 tenant, секреты | 1.2, 1.11 | `.env WB_*_TOKEN_FILE` только для probe - тогда откуда пути токенов у `collect`? (M3) |
| AD-14 миграции | шапка Epic 1 | Structural Seed спайна всё ещё говорит `016_brief_daily_roles` - устарело после v3.1 (L1) |
| AD-15 канон, релиз | 1.1 (шаг 8), 1.7, 1.10, 1.11 | `compose up postgres` из нового чекаута пересоздаст контейнер (в main есть bridge-binding `172.17.0.1:5432`, в `/srv` нет) - простой БД в runbook не назван (M8) |
| AD-16 направление зависимостей | - (инвариант) | Гейта нет; допустимо |
| AD-17 наблюдаемость | 1.10 | JSON-строка на событие - **ни в одном AC** (NFR11 сирота); «проверка восстановления дампа» подменена refresh'ем из живой базы (M5) |
| AD-18 заморозки | 1.8, 1.9, 2.5 | - |

### NFR/AR без истории

NFR11 (JSON-лог), AR5 `tools/record_fixture.ts`, AR14 pa41, AR15 (не единица - чеклист Ворот 3, ок).

## 2. Трассировка назад: решения, которых нет ни в спайне, ни в DECISIONS

Каждая история E1-E3 ссылается на AD/D - формально да. Но в AC есть решения, принятые нарезкой. Исполнитель обязан их либо принять как данность (тогда они должны попасть в спайн), либо придумать своё. Список:

| Где | Решение в AC | Записано где-либо? | Что придумает исполнитель |
|---|---|---|---|
| 1.2 | `COLLECTOR_DATABASE_URI_FILE` | Нет. AD-11 задаёт файлы `/etc/proxima-ai/secrets/<user>_uri`, но не имена env | Имя переменной; как она попадает из compose `secrets:` (`/run/secrets/<name>`) |
| 1.1, 1.2 | пути токенов: тест «при незаданных `WB_*_TOKEN_FILE`» | Противоречит AD-13 («`.env WB_*_TOKEN_FILE` только для probe»); AD-13 говорит «`morning_run.sh` передаёт пути по шаблону», но не как | CLI-флаги (`--statistics-token-file`, как у `stockout-signal`) или env |
| 1.2 | адаптер `RecordedHttpClient` → `wb_raw_artifacts` | Нет. `http.ts:65-71` принимает `SignalRepository` с 9 методами; `recordRawArtifact` пишет в `business_signal_raw_artifacts` | Свой интерфейс `ArtifactSink`, либо копия `RecordedHttpClient` (что нарушит AD-4 «один клиент») |
| 1.2 | `kind`/`status` как `text + CHECK` | Нет (гейт запрещает `CREATE TYPE`, `verify_migrations.py:23`) | Узнает на первом `make verify` - самокорректируется, но стоит сеанса |
| 1.2 | `git_sha`/`image_id` из `PROXIMA_GIT_SHA`/`PROXIMA_IMAGE_ID` с fallback | Env-имена - AD-6; fallback при отсутствии (локальные тесты) - нет | NULL или `'local'` |
| 1.2-1.6, 3.1, 3.2 | «тест X зелёный в `make verify`» для TS-job против локальной БД | **Нет harness**: `pg_local_roundtrip.sh:63-65` гоняет только 2 pytest-файла с `PROXIMA_TEST_POSTGRES_DSN`; `make test` идёт до roundtrip без БД | Как TS-тесты получают DSN, где живут (`node:test` со skip без DSN + вызов из roundtrip?), как сидируются данные для `_current` (нужен `collect` на фикстурах до RLS-теста 1.5) - H1 |
| 1.3 | `--source artifact:<sha256>` | Нет. AD-6: бэкфилл = живой `collect --from 2026-03-01 --backfill` | Всё: см. H2 |
| 1.3 | режим artifact «читает из CAS ... зарегистрированный как `wb_raw_artifacts` прогона» | Кто регистрирует? Файлы 30.08 лежат в `~/signal-inputs/fixtures/` (0700 `proxima-admin`), не в CAS `PROXIMA_RAW_DIR`; контейнер `USER 1010` их не прочитает | Инструмент импорта файл → CAS + строка `wb_raw_artifacts`; или флаг `--source file:<path>` |
| 1.3 | один `<sha256>` | Артефактов два (orders 10.9 МБ, sales 8.8 МБ) | Формат флага |
| 1.3, 1.4, 1.10 | `run_day` для artifact-режима | Нет. AD-2 версионирует `[floor, run_day-1]` включая нулевые дни | Если `run_day` = день запуска (10.09), дни 31.08-09.09 получат версии с нулями и станут «полными»; хвост `--from <дата+1>` (1.10) с `floor = --from+1` никогда не переверсионирует 31.08, а 30.08 останется усечённым на ~18 часов. Data-дыра по построению - H2 |
| 1.4 | гейт на `CURRENT_DATE` | «проверяется гейтом» без файла | Правка `verify_migrations.py` + тест в `tools/tests/test_verifiers.py` |
| 1.5 | `delete_run.py` под janitor - откуда URI, где запускается | Нет (на хосте нет uv/psql по AD-6) | `JANITOR_DATABASE_URI_FILE` + `docker compose run control-plane` |
| 1.5 | FK `collector_run_inputs.input_run_id` - CASCADE или RESTRICT | Нет | Влияет на порядок удаления замыкания |
| 1.6 | provision «на локальном PG16 в `pg_local_roundtrip`» | AD-11: скрипт под superuser через `docker compose exec postgres`; на маке Docker нет (AGENTS.md); URI-файлы в `/etc` | Переключатель `PSQL=`/`SECRETS_DIR=`; какой пароль у LOGIN-ролей и кто его генерирует |
| 1.6 | «шаблон `.env.task`» в git | `.gitignore:3` `.env.*` - `.env.task.example` игнорируется (проверено `git check-ignore`) | Имя и место файла (`infra/openhands/env.task.template` не игнорируется) |
| 1.6 | `SELECT count(*) FROM fact_cabinet_daily_current` > 0 под `proxima_sandbox` | AD-12 даёт `GRANT SELECT`, но политик для `proxima_sandbox` нет ни в одной миграции → RLS default-deny → 0 строк | `BYPASSRLS`, членство в `proxima_webapp_readonly`, или свои политики - решение архитектурное, H4 |
| 1.7 | `docker compose config` overlay в CI при `secrets: file:` | Нет | Пустышки секретов в CI |
| 1.9, 2.5 | `WEBAPP_DATA_DATABASE_URI` из compose-секрета | AD-9/1.7 называют env; `secrets:` даёт файл | `WEBAPP_DATA_DATABASE_URI_FILE` + чтение в provider |
| 1.10 | `proxima-restore-check@.timer` (Пн 06:00, `test_db_refresh.sh`) | AD-17: «проверка восстановления дампа»; AD-12: refresh = `pg_dump proxima \| psql proxima_test` из живой базы. Это не проверка бэкапа (`/var/backups/proxima/*.sql.gz.age` + S3) | Что именно проверяет юнит; зачем `@` у не-tenant юнита |
| 1.10 | `infra/backup/proxima-pg-backup.sh` «снят с сервера как есть» | Файл только на сервере (`/usr/local/bin`, 0750 root, INVENTORY №126) - OpenHands его не достанет | Заглушка или отказ - H5 |
| 1.10 | `proxima-alert@.service` «Telegram монитора» | Секреты `telegram_bot_token`/`telegram_chat_id` названы только в `infra/monitoring/monitor.env.example`; скрипт отправки не назван | Переиспользовать `host_monitor.py:send_telegram` или новый скрипт |
| 2.1 | `signals[]` `$ref` на `signal.schema.json`, «который придёт в 2.2» | Ссылка вперёд; `make contracts` (jsonschema `Draft202012Validator`) упадёт на нерезолвимом `$ref` | Заглушка схемы или смена порядка - H3 |
| 2.1 | `diagnosis/validator.py` читает `contracts/`, копия удалена | AD-10. Но `contracts/diagnosis.schema.json` (pmm29) и `schema/diagnosis.draft.v1.json` разной формы (`primary_cause` строка vs объект `{hypothesis, source_refs}`; нет `scenario_id/trust/model/prompt_version/generated_at`, есть `reviewer`); на draft завязаны `models.py:9`, `service.py`, `adapters/mock.py`, 3 файла тестов, eval-датасет | Переписать пакет diagnosis (M-05) внутри «контрактной» истории сентября - H3 |
| 2.3, 2.4 | `NORM_DATABASE_URI_FILE`; модель прогона Python | Имя env - нет; модель - AD-3 «set_config на соединении» (достаточно) | Имя env |
| 2.4 | округление `deviation_pct` до 0.1 | Нет (следует из примера 34.5) | Правило округления в контракте `brief` |
| 3.1 | активные nmId = distinct из `stg_wb_orders_latest` за 30 дней | Нет в спайне/memlog | Принять как есть, но зафиксировать |
| 3.1 | «повтор - 0 новых» при PK `(…, source, run_id)` | Противоречит AD-5 (каждый прогон = новый `run_id` = новые строки) | Убрать `run_id` из PK или изменить AC - H6 |
| 3.2 | кто создаёт `collector_runs kind=funnel_csv` и переводит в SUCCEEDED при фазе 1 (Python, owner-URI) + фазе 2 (TS, collector) | Нет (`--collector-run-id` подразумевает, что строка уже есть) | Обёртка двух фаз, её язык и роль - H6 |
| 3.2 | `--period from..to` в `wb_async_report.py` | Только `latest-closed-week` (`wb_async_report.py:915`) | Парсинг и валидация периода; ок, локально |

Итого: 8 решений архитектурного уровня (H1-H8) и ~15 локальных. Локальные исполнитель примет сам без вреда; архитектурные - нет.

## 3. Зависимости

- Внутри Epic 1: порядок 1.0 → 1.1 → 1.2 → 1.3 → 1.4 → 1.5 → 1.6 → 1.7 → 1.8 → 1.9 → 1.10 → 1.11 - ссылок вперёд нет. Скрытая: 1.2 обещает job «не superuser» и 1.5 гоняет RLS-тест «под каждой ролью», но LOGIN-пользователи появляются в 1.6; в roundtrip есть только superuser `proxima_roundtrip` + NOLOGIN-роли 011 → harness должен использовать `SET ROLE` (нигде не сказано, часть H1).
- Внутри Epic 2: **2.1 → 2.2 ссылка вперёд** (H3): `$ref` на `signal.schema.json` и `diagnosis.schema.json` из pmm29. Правка: 2.2 (принять pmm29) первой, 2.1 второй; перенос `diagnosis/validator.py` на `contracts/` - в 5.1.
- Внутри Epic 3: 3.0 → 3.1 → 3.2 → 3.3 - чисто.
- E2 и E3 после E1: независимы по коду (перенумерация оговорена). Общая точка: оба правят `tools/morning_run.sh` (2.5 и 3.1) - конфликт мержа тривиален.
- E2 ← E1: 2.2 удаляет `services/webapp/src/lib/data/types.ts`, который появляется в 1.8 - зависимость есть, в тексте 2.2 не названа (1.8 говорит «временный до Story 2.1» - должно быть 2.2). Низко.
- [Claude] vs OpenHands: 1.0, 1.11, 2.6, 3.0, 3.3 отделены верно. Шаг «деплой» в 1.1 (восстановить `origin`, тег baseline, checkout) не помечен [Claude] явно - помечен только через D7. **1.10 - OpenHands-история, которой нужен сервер** (скрипт бэкапа, H5). 1.3 упоминает пути `~/signal-inputs/...` только как контекст, тест на синтетике - ок.
- Сандбокс OpenHands: гейт = CI (AD-12), ок. Но `172.17.0.1:5432` из rootless-docker зоны (INVENTORY №7: своя сеть, D8 на хосте не реализован) не проверен; для 1.0/1.1 не важно, для `.env.task` в 1.11 - проверить (L6).

## 4. Конфликты между артефактами

| # | Где | Суть | Вердикт |
|---|---|---|---|
| K1 | SPEC CAP-2 success «суммы W10/W35 в БД» vs 1.4 (синтетика в git) + 1.11 (сверка на VPS) | CAP-2 говорит про боевую БД; 1.11 это и проверяет. FR3 в epics.md сформулирован как «совпадают с фикстурами 30.08» - неточно, но не мешает | Уточнение, не конфликт |
| K2 | AD-9 vs 1.9 «режим только статус» | AD-9 v3.1 содержит режим дословно | Нет конфликта |
| K3 | AD-14 номера vs истории | AD-14 без номеров для E2/E3 + правило перенумерации; истории дают целевые 014/015 и 014. Но Structural Seed спайна: `db/migrations/ 011_run_ledger … 016_brief_daily_roles` - роли в 016 устарели после v3.1 | Стилистический, поправить seed |
| K4 | AD-6 «бэкфилл = живой collect» vs 1.3/1.10 artifact-replay | Спайн не знает режима; семантика `run_day`/`floor`/хвоста не определена → Data-дыра 30-31.08 и ложные нулевые дни | **Конфликт**, H2 |
| K5 | AD-5 PK `stg_wb_funnel_obs` с `run_id` vs 3.1 «повтор - 0 новых» | Взаимоисключающие | **Конфликт**, H6 |
| K6 | AD-12 (`GRANT SELECT` sandbox) vs 1.6 AC «> 0 строк» | RLS без политики = 0 строк | **Конфликт**, H4 |
| K7 | AD-17 «проверка восстановления дампа» vs 1.10 `proxima-restore-check@` = `test_db_refresh.sh` (AD-12) | Refresh из живой базы не проверяет ночной бэкап | **Конфликт**, M5 |
| K8 | AD-11 RLS-тест «каждая роль × каждый view» vs матрица грантов AD-11 | `proxima_webapp_readonly` не имеет SELECT на `stg_wb_*_obs` → `stg_wb_orders_latest` под ним = permission denied, не 0 | Внутренний конфликт AD-11, M2 |
| K9 | SPEC CAP-1 «3 дня», CAP-5 «7 утр» vs 1.11/2.6 «следующим утром» | Приёмка эпика не записана | Пробел спеки/нарезки, M9 |
| K10 | AD-13 «`.env WB_*_TOKEN_FILE` только для probe» vs 1.1 тест «при незаданных `WB_*_TOKEN_FILE`» | Механизм передачи путей токенов job'у не определён | M3 |
| K11 | `infra/vps-contract.json` `business_data_admission.allowed_now=false` (гейт `verify_vps_contract.py` требует false) vs M-01 грузит данные кабинета в боевую БД | Документ 13.08 vs реальность (данные уже лежат с 25.08) | Низко, L3 |
| K12 | 1.8 «`types.ts` временный до Story 2.1» vs удаление в 2.2 | Опечатка | L2 |
| K13 | Story 3.1 «21 наблюдение» при фикстуре 24-30.08 и правиле «день = run_day не версионируется» | Сходится только при виртуальных часах `run_day = 31.08`; в AC не сказано | L4 |

## 5. Размер (ориентир ≤ ~5 областей файлов, ≤ ~600 строк)

| История | Области | Оценка | Вердикт |
|---|---|---|---|
| 1.1 | `src/wb/` (4), тесты, `tools/verify_wb_client.py`, Makefile, `docs/operations/releases/` | ~550 | Влезает |
| 1.2 | 011, 012, `jobs/collect.ts`, адаптер артефактов, писатель наблюдений/ledger, CLI, **harness TS↔PG** (новый), тесты | 800-1000, 7 областей | **Не влезает**. Делить: 1.2a = 011 + harness (roundtrip запускает TS DB-тесты) + модель прогона (RUNNING/SUCCEEDED/FAILED, артефакт-адаптер) на фикстуре без наблюдений; 1.2b = 012 + наблюдения + идемпотентность |
| 1.3 | `jobs/backfill.ts`, artifact-режим, импорт в CAS, пагинация, тесты | 450-600 | На грани; после H2 - влезает |
| 1.4 | 013, `facts/cabinet-daily.ts`, self-heal `dateFrom` в collect, гейт `CURRENT_DATE`, тесты | 500-600 | На грани |
| 1.5 | `delete_run.py`, RLS-тест (матрица), сидирование данных | 400-500 | Влезает при готовом harness |
| 1.6 | provision (+локальный режим), refresh (+локальный режим), шаблон env, Makefile, тесты bash | 450-550, кросс-инструментально | Влезает, риск в harness (M4) |
| 1.7 | 2 Dockerfile, `.dockerignore`, compose, overlay, `jobs.env`, CI (2 job), pyproject/uv.lock, Makefile | ~400 | Влезает |
| 1.8 | cherry-pick 19 файлов + разрешение конфликтов | ~700 diff, импорт | Влезает |
| 1.9 | provider статус, `page.tsx`, vitest | ~300 | Влезает |
| 1.10 | 5 юнитов, alert-скрипт, `morning_run.sh`, backup-скрипт, runbook ~250 строк, CI (systemd-analyze, shellcheck) | 600-700, 6 областей | **Не влезает** + H5. Делить: 1.10a юниты + `morning_run.sh` + alert + CI; 1.10b runbook (+ backup-скрипт, если снят в 1.0) |
| 2.1 | 3 схемы + примеры, `generate_contract_types.mjs` → webapp, `diagnosis/validator.py` + удаление копии, `common/msk_day.py`, тесты | 600-800, 5 областей + H3 | **Не влезает**. Делить: 2.2 первой; 2.1a = 3 схемы + примеры + `make contracts`; 2.1b = codegen → webapp + удаление `types.ts` + импорты; `msk_day.py` - в 2.3; diagnosis - в 5.1 |
| 2.2 | 26 файлов импорта + удаление `types.ts` + импорты webapp | ~1100 diff, импорт | Влезает как ревью-единица |
| 2.3 | 014, `norm/` (4), тесты | ~500 | Влезает (pytest-harness есть) |
| 2.4 | 015, `brief/` (2-3), тесты | ~450 | Влезает |
| 2.5 | `getBrief()`, компоненты, `page.tsx`, `morning_run.sh`, vitest | ~400 | Влезает |
| 3.1 | 014, `jobs/funnel-v3.ts`, `facts/funnel-daily.ts`, тесты, `morning_run.sh` | 500-600 | На грани |
| 3.2 | `wb_async_report.py` (3 правки), `jobs/funnel-csv-promote.ts`, 2 юнита, обёртка двух фаз (владелец run-строки), тесты | 600-800, 6 областей | **Не влезает**. Делить: 3.2a промоушен TS + тест replay-after-delete; 3.2b `wb_async_report.py` + юниты + обёртка |

Сентябрь при таком делении: 22 → 26 единиц (1.2a/b, 1.10a/b, 2.1a/b, 3.2a/b).

## 6. Готовность первой единицы (1.0 и 1.1) к старту 01-08.09

### 1.0 [Claude] - готова с двумя уточнениями

Есть до путей: эндпоинты (API-FACTS, таблица B/C), токен `/etc/proxima-ai/secrets/wb_statistics_token` (D5b), каталог `~/signal-inputs/fixtures/wb-api/`, целевые каталоги фикстур, лимит 200 КБ, правки `.openhands/hooks/verify-gate.sh:4-7`, `.openhands/setup.sh`, `verify.yml:12` (`ubuntu-24.04` + PG16), действие Mike (зелёный CI с `pg-roundtrip: PASS`).

Не хватает:
1. Формула вердикта «flag=0 фильтрует по `lastChangeDate`»: например, «доля строк с `date < dateFrom` в ответе `orders?dateFrom=run_day-3&flag=0` > 0 → фильтр по `lastChangeDate`»; сослаться на API-FACTS:42, где уже есть свидетельство против гипотезы на границе окна. Без формулы два Claude-сеанса могут сделать разный вывод.
2. `tools/record_fixture.ts` (AD-4, AR5) - в 1.0 обезличивание описано как результат, инструмент не назван. Либо 1.0 пишет и коммитит инструмент, либо 1.1 (тогда 1.0 обезличивает вручную и это надо сказать).
3. Добавить в 1.0 две серверные заготовки для будущих OpenHands-историй: `scp` `proxima-pg-backup.sh` → `infra/backup/` (снимает H5 с 1.10) и `sha256sum` двух полных ответов 30.08 + копия в 1010-читаемое место или в CAS (снимает половину H2 с 1.3/1.11). Обе операции - чтение сервера, разрешены.

Реалистично: «сохранение распределения по дням» при ≤ 200 КБ на 6 месяцев (≈ 250 строк из 13 325) невозможно; фикстура для 1.4 (S1/S2 = две недели) и есть правильный объём - записать это явно.

### 1.1 - готова с одним уточнением

Есть: реестр 4 эндпоинтов с бюджетами и URL (API-FACTS), правила `verify_wb_client.py`, тесты 429/бюджета/`mskDay` с граничными значениями, `FixtureTransport` и путь фикстур (AD-4), 10 шагов конвейера с именами артефактов (`docs/operations/releases/2026-09-NN-m01-1.md`, тег `v2026.09.NN-1`, `CHANGELOG.md`), безопасный «деплой» (восстановить `origin` у `/srv/proxima-ai/repo`, тег `v2026.09.0-baseline` на `fd95fcb`, checkout; откат = checkout baseline). `/srv/proxima-ai/repo` чистый (INVENTORY №14), `~/.git-credentials` на сервере есть, egress к GitHub через прокси проверен (WT-10) - шаг выполним.

Не хватает:
1. Как `wb/client.ts` получает путь к токену и куда пишет артефакт до появления 011 (1.2): в 1.1 нужен интерфейс `ArtifactSink` (или явное «в 1.1 артефакты в память, `wb_raw_artifacts` - в 1.2») и механизм путей токенов (CLI-флаги по образцу `stockout-signal.ts` `--statistics-token-file`, не env `WB_*_TOKEN_FILE`, иначе конфликт с AD-13). Одно предложение в Given - и исполнитель не изобретает.

Побочно: checkout нового тега на `/srv/proxima-ai/repo` меняет `infra/compose.yaml` на диске (bridge-binding `172.17.0.1:5432` из main); контейнер не пересоздаётся до `compose up` - утверждение «код не исполняется» верно, но в релиз-заметке 1.1 это надо записать как известное отличие для 1.11.

## Находки по серьёзности

### High (исполнитель придумает архитектурное решение или AC невыполним)

| # | Где | Что | Правка | Скилл |
|---|---|---|---|---|
| H1 | 1.2, 1.3, 1.4, 1.5, 1.6, 3.1, 3.2 | Нет harness для TS-job тестов против PG в `make verify`: `pg_local_roundtrip.sh:63-65` запускает 2 pytest-файла; `make test` идёт без БД. Сидирование `_current` для RLS-теста 1.5 и «под ролью» без LOGIN-пользователей (1.6 позже) не определены | Записать в AD-12/консистентные конвенции: roundtrip экспортирует `PROXIMA_TEST_POSTGRES_DSN` и вызывает `npm --workspace @proxima/collector run test:pg` (node:test, skip без DSN); «под ролью» в тестах = `SET ROLE <nologin>`; сделать harness первым результатом 1.2a | bmad-architecture + bmad-create-epics-and-stories |
| H2 | 1.3, 1.4, 1.10, 1.11; AD-2/AD-6 | Artifact-replay бэкфилла не описан в спайне: (а) артефакты 30.08 лежат в `~/signal-inputs/` 0700, контейнер 1010 не прочитает, в CAS/`wb_raw_artifacts` их никто не регистрирует; (б) флаг принимает один sha256, артефактов два; (в) `run_day` для replay не определён → версии с нулями за 31.08-09.09 станут «полными», хвост `--from <дата+1>` с `floor=--from+1` не переверсионирует 31.08, 30.08 останется усечённым | AD-2/AD-6: режим `backfill --source artifact` = импорт файла в CAS + строка `wb_raw_artifacts` своим `run_id`; два артефакта; `run_day` := MSK-день `retrieved_at` артефакта; хвост живой `collect --date-from <retrieved_at-1>` (перекрытие безвредно по идемпотентности); 1.0 снимает sha256 и кладёт файлы в 1010-читаемое место | bmad-architecture, затем bmad-create-epics-and-stories |
| H3 | 2.1 ↔ 2.2; AD-10 | Ссылка вперёд (`$ref` на `signal.schema.json`, `diagnosis.schema.json` из pmm29); «копия схемы удаляется» невыполнимо: `contracts/diagnosis.schema.json` (pmm29) и `schema/diagnosis.draft.v1.json` разной формы, на draft завязаны `models.py`, `service.py`, `adapters/mock.py`, 3 теста, eval | Порядок 2.2 → 2.1; diagnosis-валидатор на `contracts/` - в 5.1 (там же выбор формы); AD-10 уточнить: «копия удаляется в M-05 после сведения схем» | bmad-create-epics-and-stories + bmad-architecture (одна строка memlog) |
| H4 | 1.6; AD-12 | `proxima_sandbox` получает `GRANT SELECT`, но ни одной RLS-политики → 0 строк из `fact_cabinet_daily_current`; AC «> 0» невыполним | Решение в AD-12: `proxima_sandbox` = член `proxima_webapp_readonly` (SELECT-политики уже есть) + `GRANT SELECT` на остальное; либо `BYPASSRLS` в `proxima_test` (проще, но сандбокс видит все tenant'ы - сейчас он один) | bmad-architecture |
| H5 | 1.10 | OpenHands-история требует файл с сервера (`proxima-pg-backup.sh`, только `/usr/local/bin`); плюс `proxima-restore-check@` подменяет «проверку восстановления дампа» refresh'ем из живой базы (K7) | Снятие скрипта → в 1.0 [Claude]; в AD-17 определить, что проверяет юнит (restore `.sql.gz.age` из `/var/backups/proxima` в `proxima_test` = и refresh, и проверка бэкапа одним действием) и убрать `@`, если юнит не per-tenant | bmad-create-epics-and-stories + bmad-architecture |
| H6 | 3.1, 3.2; AD-5 | PK `stg_wb_funnel_obs` с `run_id` исключает «повтор - 0 новых»; владелец строки `collector_runs kind=funnel_csv` при фазе 1 (Python, owner-URI) и фазе 2 (TS, collector) не назван - кто INSERT RUNNING, кто UPDATE SUCCEEDED, что при падении фазы 1 | AD-5: либо PK без `run_id` + `DO NOTHING` по `evidence_sha256` (как orders), либо AC «повтор = новая версия, `_current` не меняется»; обёртка `funnel_csv` = TS-шаг создаёт run, вызывает `wb_async_report.py --collector-run-id`, промоутит, закрывает run | bmad-architecture, затем 3.1/3.2 |
| H7 | 1.1, 1.2, 1.7, 1.9, 2.3; AD-13 | Имена env для путей секретов придуманы историями (`COLLECTOR_DATABASE_URI_FILE`, `NORM_DATABASE_URI_FILE`, `WEBAPP_DATA_DATABASE_URI` «из секрета», `WB_*_TOKEN_FILE` против AD-13) | Одна таблица в Consistency Conventions: `<ROLE>_DATABASE_URI_FILE=/run/secrets/<user>_uri`, `WEBAPP_DATA_DATABASE_URI_FILE`, токены job'ам - CLI-флаги `--<category>-token-file` (образец `cli/stockout-signal.ts`) | bmad-architecture |
| H8 | 1.1, 1.2; AD-1/AD-4 | «Поверх `RecordedHttpClient`»: конструктор требует `SignalRepository` (9 методов business-signal), `recordRawArtifact` пишет в `business_signal_raw_artifacts`; для `wb_raw_artifacts` нужен адаптер, в 1.1 таблицы ещё нет | AD-4: `wb/client.ts` принимает `ArtifactSink {record(RawArtifactRecord)}`; 1.1 - in-memory sink, 1.2 - PG-sink в `wb_raw_artifacts`. Пять строк в спайне | bmad-architecture |

### Medium

| # | Где | Что | Правка |
|---|---|---|---|
| M1 | 1.2; AD-3/AD-13 | Autocommit-шаги (1) RUNNING, (2) артефакты, FAILED идут под RLS `WITH CHECK`, а `set_config(…, true)` определён только для транзакции (3); AD-13 запрещает `set_config(…, true)` вне транзакции | AD-3: шаги (1), (2), FAILED - мини-транзакции с `set_config(…, true)` первым statement, либо session-level `set_config(…, false)` на соединении job'а (как Python) |
| M2 | 1.5; AD-11 | RLS-тест «каждая роль × каждый view» vs гранты: под `proxima_webapp_readonly` `stg_wb_orders_latest` даст permission denied | Матрица роль × view по грантам AD-11; тест падает на «denied» там, где грант есть, и на «> 0» там, где его нет |
| M3 | 1.2 | `FOR INSERT` политика: гейт требует `USING (...)` (`verify_migrations.py:46-50`), Postgres для INSERT принимает только `WITH CHECK` → «SELECT runs/INSERT runs+inputs» для norm не проходит либо гейт, либо БД | В 011: `GRANT SELECT, INSERT, UPDATE` + одна политика `FOR ALL` для norm на `collector_runs`/`collector_run_inputs` (видимость строк - политика, права - грант) |
| M4 | 1.6; AD-11/AD-12 | provision через `docker compose exec postgres` и URI-файлы в `/etc` невыполнимы в roundtrip на маке/CI | `PSQL=` и `SECRETS_DIR=` переключатели в скриптах; генерация паролей LOGIN-ролей (`secrets.token_urlsafe`, образец `provision-postgres-diagnostics.sh`) |
| M5 | 1.10; AD-17 vs AD-12 | См. H5/K7 | - |
| M6 | 1.4 | Гейт на `CURRENT_DATE` в `db/` без файла | `verify_migrations.py` + кейс в `tools/tests/test_verifiers.py:208` |
| M7 | 1.6 | «Шаблон `.env.task`» попадает под `.gitignore` `.env.*` | Имя `infra/openhands/env.task.template` (проверено: не игнорируется) |
| M8 | 1.10/1.11; AD-15 | `compose up -d postgres` из нового чекаута пересоздаст контейнер (новый port-binding `172.17.0.1:5432`), простой БД, WT-02/WT-13 меняют ожидания; `mv` токенов ломает WT-15 и `.env` probe | Runbook: явный шаг «пересоздание postgres, ожидаемый простой N с»; обновление WT-02/06/15 в 1.11 |
| M9 | SPEC CAP-1/CAP-5 vs 1.11/2.6 | Приёмка эпика по 3/7 утрам не записана | В шапке Epic 1/2: «эпик закрыт после N утр подряд с SUCCEEDED», без новой единицы (bmad-spec, если менять success) |
| M10 | 3.2; AD-15 | Сервис `control-plane` получает `POSTGRES_USER_FILE/PASSWORD_FILE` (superuser) через `jobs.env` для всех шагов; `norm`/`brief` не должны видеть owner-секрет | Два сервиса в compose (`control-plane` без owner-секретов, `control-plane-admin` для `apply-migrations` и фазы 1) или `secrets:` per-step |
| M11 | 1.9, 2.5 | «Одно действие Mike» = `run dev` + локальная БД с данными; roundtrip-кластер эфемерный | `make webapp-demo-postgres` (поднять PG16, прогнать collect/norm/brief на фикстурах, запустить dev) либо приёмка = `make verify` + снапшот vitest |
| M12 | 1.0/1.1; AD-4 | `tools/record_fixture.ts` - сирота | Назначить 1.0 или 1.1 |
| M13 | NFR11; AD-17 | JSON-строка на событие - ни в одном AC | Одна строка в AC 1.2 и 2.3 («каждое событие - JSON с `run_id/tenant_id/kind/step`, тест на формат») |
| M14 | AR14 pa41 | Нет истории на мерж/перенумерацию `pa41-full-w2-phase3` (писатель `fact_order_counts` нужен 4.1) | Контурная история 4.0 в Epic 4 |

### Low

| # | Где | Что |
|---|---|---|
| L1 | Спайн, Structural Seed | `016_brief_daily_roles` устарело после v3.1 (роли в 011) |
| L2 | 1.8 | «временный до Story 2.1» → 2.2 |
| L3 | `infra/vps-contract.json` | `business_data_admission.allowed_now=false` при M-01, грузящем данные кабинета; гейт держит false. Решить: обновить контракт и гейт в 1.11 или оставить как историю |
| L4 | 3.1 | 21 наблюдение сходится только при виртуальных часах `run_day = 31.08` - записать в AC |
| L5 | 1.2 | `kind`/`status` = `text + CHECK` (гейт запрещает `CREATE TYPE`); `git_sha`/`image_id` fallback для локальных тестов |
| L6 | AD-12, 1.11 | Достижимость `172.17.0.1:5432` из rootless-docker зоны OpenHands не проверена (INVENTORY №7: D8 на хосте не реализован) - проверить при первом деплое, до записи `.env.task` |
| L7 | SPEC constraint 4 vs AD-1 | Два «канона» полных ответов (`~/signal-inputs/fixtures` и CAS `PROXIMA_RAW_DIR`); зафиксировать: пробы - первое, job'ы - второе, оба в бэкап |
| L8 | 1.1 | Шаг «деплой» не помечен [Claude] внутри истории (следует из D7) - пометить |
| L9 | 1.6 | `ALTER ROLE … SET proxima.tenant_id` без `IN DATABASE proxima_test` (AD-12 с ним) - уточнить |

## Что сделать до Ворот 3 (порядок)

1. `bmad-architecture` (правки спайна в memlog, AD-ID стабильны): H2 (artifact-replay в AD-2/AD-6), H4 (sandbox в AD-12), H6 (PK/повтор и обёртка `funnel_csv` в AD-5), H7 + H8 (env-имена, `ArtifactSink` в AD-4/AD-13/Conventions), M1 (GUC для autocommit-шагов в AD-3), M2 (матрица RLS-теста в AD-11), M5 (что проверяет restore-check в AD-17), L1.
2. `bmad-create-epics-and-stories`: перерез 1.2 → 1.2a/1.2b (harness первым), 1.10 → 1.10a/1.10b, 2.2 перед 2.1 и 2.1 → 2.1a/2.1b (diagnosis в 5.1), 3.2 → 3.2a/3.2b; 1.0 получает три заготовки (формула flag=0, backup-скрипт, sha256 + копия артефактов); 1.1 получает `ArtifactSink` + CLI-флаги токенов; 1.6 - имя шаблона env и локальный режим provision; AC 1.5/3.1/1.4/1.2 по M2/M3/M6/L4/L5; NFR11 в AC (M13); контур 4.0 (M14).
3. `bmad-spec` только если Mike хочет менять success CAP-1/CAP-5; иначе - правило закрытия эпика в шапке эпиков (M9).
4. `bmad-correct-course` не нужен: спринт не начат.

После пунктов 1-2 единицы 1.0 и 1.1 уходят 01-08.09 без вопросов; 1.2a - первая, где проверится harness, и до неё OpenHands не должен получать 1.3-1.6.

---

# Проход 4 (02.09.2026) - PRD v2.1

Объект: `epics.md` (32 истории, без изменений с прохода 3) против ревизии PRD v2.1 (`prds/prd-PROXIMA-AI-2026-08-28/prd.md` + `addendum.md`, обновлён 02.09.2026), `SPEC.md` + `glossary.md` (final 30.08), `ARCHITECTURE-SPINE.md` v3.3. Статусы историй - `origin/main:_bmad-output/implementation-artifacts/sprint-status.yaml` @ `b2c3861` (9/22 сентябрьских done: 1.0-1.3, 1.9, 1.10, 1.12, 2.1, 2.2). Центральный вопрос гейта: сможет ли исполнитель реализовать эти эпики, не придумывая решений, которых нигде не записано. Проверено по коду и фактам: `contracts/` на `origin/main` (есть `brief`, `norm`, `cabinet-daily`, `client-passport`), `db/migrations/011_run_ledger.sql`, `docs/state/API-FACTS.md` (§Воронка v3, §Остатки), фикстура `services/collector/tests/fixtures/wb-api/statistics/orders/sample.json`.

## Вердикт прохода 4: CONCERNS

- Сентябрьский срез (1.4-1.8, 1.11, 1.13, 1.14, 2.3-2.6, 3.1) остаётся реализуемым: у каждой истории AC привязаны к AD, вывод прохода 3 в силе. Проходы 1-3 не пересматриваются.
- Ревизия v2.1 добавила требования, у которых нет носителя в нарезке, и оставила три расхождения между каноническими документами (SPEC/glossary против спайна и D23), которые PRD честно фиксирует как OQ-16/OQ-17, но которые на 02.09 не исправлены в самих канонах.
- Обратная трассировка чистая: истории без требования отсутствуют - 1.2, 1.8, 1.9, 1.13 сознательно уровня NFR/AR (примечание PRD §10.1), `sprint-status.yaml` покрывает ровно 32 истории `epics.md`, лишних ключей нет.
- Находки: **High 3, Medium 5, Low 6**. Ни одна не блокирует ближайшую единицу 1.4; H3, M1, M2, M5 касаются сентября, остальные - октября.

## 1. Трассировка PRD v2.1 → epics (вперёд)

| FR PRD | Ступень | Носитель в `epics.md` | Вердикт |
|---|---|---|---|
| FR-26, FR-6 | M-01 | 1.3 (done), 1.4, 1.6, 1.11, 1.12 (done) | Покрыт |
| FR-27 | M-01 | 1.5, запуск 1.14 | Покрыт; дата отсечки - UNKNOWN (L1) |
| FR-28 | M-01 | 1.6, 1.11, 1.10 (done) | Покрыт |
| FR-29 | M-01 | 1.7 | Покрыт |
| FR-30 | M-01b | 3.1 (сентябрь), 3.0, 3.2-3.4 (октябрь) | Покрыт по содержанию; срок старта без носителя (M5) |
| FR-31 | M-02 | 2.3 | Покрыт; расхождение формулировки нормы (M1) |
| FR-32, FR-7 | M-03 | 2.1, 2.2 (done), 2.4, 2.5, 2.6 | Покрыт; `[NOTE FOR PM]` FR-7 в AC 4.2 не внесён (L5) |
| FR-22 | M-01/M-03 | 1.12 (done), 1.14 | Покрыт частично: крайний срок 06:30 носителя не имеет (H3) |
| FR-1, FR-9, FR-34 | M-04 | 4.2 | Покрыт (контур) |
| FR-8 | M-04 | 4.1 | Покрыт (контур); грейн категории без источника (M3) |
| FR-25 | M-04 | 4.3 | Покрыт (контур); `scenario_code` есть в `signal.schema.json` |
| **FR-20, FR-21** | M-04 | **нет** | **Носителя нет (H1)** |
| FR-4, FR-12, FR-14 | M-05 | 5.2 | Покрыт (контур) |
| FR-15, FR-35 | M-05 | 5.1 | Покрыт (контур) |
| FR-5, FR-16, FR-18 | M-05 | 5.3 | Покрыт (контур); нужен новый AD (M4) |
| FR-2, FR-3, FR-10, FR-11, FR-13, FR-17, FR-19, FR-23, FR-24 | вне лестницы | не требуется (§4.E → CM-n) | Корректно |
| FR-36..FR-40 | M-06+ | не требуется (`[PROPOSED]`) | Корректно |
| UJ-5 / второй tenant | после M-03 | «единица без истории» (§13) | Вне трекинга (L2) |

Обратная сторона: историй, не привязанных ни к FR, ни к NFR/AR, нет.

## 2. Находки по серьёзности

### High

| # | Место | Что не записано / что расходится | Какой навык исправляет |
|---|---|---|---|
| H1 | PRD §4.C FR-20, FR-21; §10.1 строка M-04; §13; `epics.md` - **0 упоминаний** (`policy`, `паспорт`, `ориентир`, метаданные правил не встречаются нигде) | Policy Layer (значение + 5 полей метаданных: источник, дата, клиент/бизнес-модель, уровень применения, статус) и дисклеймер происхождения для внешних ориентиров стоят в объёме M-04 (PMM-41), но ни одна из 4.1-4.3 их не описывает. Исполнитель Epic 4 придумает и хранение правил, и текст дисклеймера. PRD признаёт это `[NOTE FOR PM]` и держит как OQ-17 | Решение Mike (OQ-17), затем `bmad-create-epics-and-stories` (отдельная единица в Epic 4) либо `bmad-prd` (перевод FR-20/21 в §12) |
| H2 | `SPEC.md` CAP-6 intent vs D23 / PRD §4.A FR-30; `epics.md:32` (FR9), `:86` (FR Coverage), `:104` (Epic List), `:424` (тело Epic 3) | CAP-6 intent канона: «async CSV с 01.09 **и** v3 ежедневно». D23 и PRD: сентябрь - только v3 (3.1), CSV - октябрь (3.0, 3.2-3.4). По правилу D17/D22 при расхождении побеждает SPEC, то есть канон до сих пор требует CSV с 01.09. `epics.md` несёт оба текста: строки 104 и 424 сохранили «с первой недели сентября … еженедельно из async CSV», FR9 и карта покрытия - без пометки «октябрь» | `bmad-spec` (сузить CAP-6 intent, OQ-16), затем `bmad-create-epics-and-stories` (снять устаревшие фразы Epic 3) |
| H3 | PRD §4.B FR-22 «сводка … не позже 06:30 МСК; превышение - алерт монитора (таймаут юнита, `OnFailure`)»; PRD §15 приписывает это AD-6, AD-17, `epics` AR3 | Ни AD-6 (спайн:75), ни AD-17 (спайн:159), ни AR3 (`epics.md:57`), ни AC Story 1.12 не содержат 06:30 и не содержат таймаута юнита; 06:30 в спайне и в нарезке - только понедельничный `proxima-funnel-csv@`. PRD сам пишет, что число задаёт он, а SPEC и спайн - нет (OQ-16). Естественный носитель Story 1.12 уже `done`: требование пришло после закрытия истории. Исполнитель 1.14/2.6, желающий обеспечить срок, выберет механизм сам (`TimeoutStartSec`? проверка в мониторе? порог алерта?) | `bmad-architecture` (AD-6/AD-17: срок и механизм), `bmad-spec` (OQ-16), затем пункт AC в 1.14 или новая единица; правки уже закрытой 1.12 - через `bmad-correct-course` |

### Medium

| # | Место | Что не записано / что расходится | Какой навык исправляет |
|---|---|---|---|
| M1 | `glossary.md` «Норма» vs AD-8 (спайн:87), D21, PRD §3.2, AC Story 2.3 (`epics.md:367`) | Глоссарий (companion SPEC, то есть канон): «медиана заказов за **14 последних полных дней**». AD-8 и Story 2.3: **фиксированное окно** `[evaluation_day-14, evaluation_day-1]`, медиана по имеющимся, `sample_days < 14` → `insufficient`. При пропусках это разные числа. PRD расхождение фиксирует (§3.2, OQ-16), но канон не поправлен, а 2.3 - вторая история в очереди сентября | `bmad-spec` (правка glossary и constraint SPEC) |
| M2 | AD-5 (спайн:69), AC Story 3.1 (`epics.md:445`) vs `API-FACTS.md` §Воронка v3 | Окно v3 в нарезке - `[run_day-7, run_day-1]`. Живым вызовом 30.08 подтверждён только `start = сегодня-6`; `start = сегодня-7` («8 дней») API-FACTS прямо помечает как **не бисектированный**, а отказ приходит как 400 `invalid start day: excess limit on days`. В harness на `FixtureTransport` это не проявится - только на боевом прогоне (3.4/1.14). Решения, какой старт брать, нет ни в спайне, ни в истории | `bmad-architecture` (граница окна в AD-5) либо один живой вызов по разрешению Mike с записью в `API-FACTS.md`, затем правка AC 3.1 |
| M3 | SPEC CAP-7 success, PRD FR-8, FR-25, Story 4.3 (`epics.md:519-529`), спайн Deferred (:317) | «Разрез по категории» требуется каноном, но грейна нет: Deferred называет `fact_order_counts` + `fact_funnel_daily`, ни в одной из этих таблиц (AD-2, AD-5) нет предмета/категории; `COLUMN_MAP` scn001 в AD-5 отбрасывает `product.subjectName` ответа v3. Поля `category`, `subject`, `brand`, `supplierArticle` есть только внутри `payload` наблюдений (проверено на фикстуре `statistics/orders/sample.json`). Исполнитель 4.1/4.3 сам решит: читать `payload->>`, завести измерение или добавить колонки - каждое решение стоит миграции | `bmad-architecture` (грейн категории в AD-2/AD-5 или новый AD), затем AC 4.1/4.3 |
| M4 | Story 5.3 (`epics.md:573`), PRD FR-5, FR-16, G-9, OQ-8; спайн Deferred (:317-323) | Первая запись из webapp в БД требует отдельного AD (роль, RLS `WITH CHECK`) - это записано в истории и в PRD как **условие**, но в очередь спайна (Deferred) не попало: у `bmad-architecture` нет записи, что этот AD нужно выпустить. AD-11 знает только `proxima_webapp_readonly` на SELECT | `bmad-architecture` (пункт в Deferred и затем сам AD до октября) |
| M5 | PRD §4.A FR-30, §13 строка M-01b, §14; `epics.md` NFR9 (:47); `sprint-status.yaml` | Требование «Story 3.1 уходит в работу не позже 08.09.2026» (иначе SM-7 «8 недель к 27.10» недостижима, день без съёма теряется навсегда) носителя в нарезке не имеет: NFR9 говорит только о первой единице M-01, а она закрыта 31.08. На 02.09 3.1 - `backlog` и стоит за 1.4 (`backlog`); до срока 6 дней | Не документный дефект: решение Mike о приоритете (§8.0 п. 1) + отражение в `docs/agent-system/TASKS.md` / `HANDOFF.md`; при сдвиге - `bmad-correct-course` |

### Low

| # | Место | Что |
|---|---|---|
| L1 | PRD FR-27, §8.0 п. 1; Stories 1.5, 1.14 | Дата отсечки бэкфилла по окну WB - `UNKNOWN`, ждёт Mike. Код не блокирует, блокирует приоритет |
| L2 | PRD §6.2, §13 «Второй tenant», UJ-5 | Октябрьская единица «без истории»: в `epics.md` её нет, значит и в `sprint-status.yaml` не появится; приёмка («сводка по двум tenant без изменения схемы») не отслеживается |
| L3 | PRD §4.0, OQ-13; AD-4 (спайн:63); `epics.md` NFR1 (:39) | `analytics/v1/stocks-report/{wb,seller}-warehouses` и `STOCK_HISTORY_DAILY_CSV` подтверждены живым вызовом 02.09, но не входят ни в реестр AD-4, ни в список запрещённых NFR1 - состояние «ни разрешено, ни запрещено» до нового AD. В сентябре-октябре ни одна история от них не зависит |
| L4 | SPEC Constraints («sales и reportDetail 1/мин») vs AD-4 и NFR1 (метод запрещён); PRD §4.0, OQ-14 | Канон перечисляет `reportDetailByPeriod` среди рабочих лимитов, спайн и нарезка его запрещают; статус метода (снят по зеркалу спецификации 15.07 vs 200 по замеру 30.08) не разрешён. Учтено в OQ-16 |
| L5 | PRD FR-7 `[NOTE FOR PM]`; AC Story 4.2 (`epics.md:506`) | «В M-04 `signals[]` не строятся при статусе, отличном от `ok`» - в AC 4.2 не внесено; AC говорят только «`brief.status` и правило показа цифр не меняются» |
| L6 | PRD §11.3 (OQ-11) | Три ML-утверждения помечены словом «инвариант» (исключение дней отсутствия товара, пороги на медиане и MAD, лестница моделей с backtest-гейтом), но AD по ML-контуру нет: инварианты уровня архитектуры живут только в PRD. Влияет на M-06+, ни одна история не зависит |

## 3. Конфликты между артефактами (сводка)

Все три названных расхождения PRD фиксирует явно и не «разрешает молча» - это правильное поведение, но на 02.09 канон не поправлен:

- CAP-6 intent (H2) - SPEC требует CSV с 01.09, план - октябрь.
- «Норма» (M1) - glossary «14 последних полных дней» против фиксированного окна AD-8.
- Окно v3 (M2) - `[run_day-7, run_day-1]` против единственной подтверждённой границы `сегодня-6`.

Плюс два уровнем ниже: L4 (`reportDetailByPeriod` в SPEC против запрета AD-4) и формулировка этапов воронки в CAP-6 («показы → корзина → заказ») против glossary («открытия, корзина, заказы, выкупы») и факта, что показов в v3 нет (`API-FACTS.md`) - обе входят в перечень правок SPEC OQ-16.

## 4. Что осталось UNKNOWN

Порог тревоги (OQ-7), срок сверки N и границы исхода «частично» (OQ-3), обязательность причины при «принял» (OQ-12), носитель FR-20/21 (OQ-17), дата отсечки бэкфилла (FR-27), точная граница окна v3 (`API-FACTS.md`), глубина async CSV назад (Story 3.0, OQ-10), порог расхождения и каденция quality-check «кабинетный ряд vs сумма nmId» (FR-8), статус `reportDetailByPeriod` и сроки миграции (OQ-14), формат загрузки остатков (OQ-13), ML-платформа (OQ-11), путь ручного ввода при read-only webapp (OQ-8), ПДн и провайдер языковой модели (OQ-15), пороги SM-8 и SM-9.

## 5. Порядок правок (предложение, не решение)

1. Решение Mike по OQ-17 (носитель FR-20/21) и по §8.0 п. 1 (отсечка бэкфилла, подтверждение старта 3.1) - без них H1 и M5 не закрываются.
2. `bmad-spec`: правки OQ-16 одним заходом - CAP-6 intent (H2), «Норма» в glossary (M1), слова этапов воронки, крайний срок 06:30 (H3), constraint по `reportDetailByPeriod` (L4).
3. `bmad-architecture`: срок и механизм 06:30 в AD-6/AD-17 (H3), граница окна v3 в AD-5 (M2), грейн категории (M3), пункт «AD записи из webapp» в Deferred (M4).
4. `bmad-create-epics-and-stories`: единица Policy Layer в Epic 4 (H1, если Mike выберет носителя), снятие устаревших фраз Epic 3 (H2), пункты AC по L5 и M3.
5. `bmad-correct-course` - только если правка 06:30 затрагивает закрытую Story 1.12 или если сдвигается срок 3.1.

Ни один из пунктов не блокирует выдачу Story 1.4 в работу.

# Проход 5 (02.09.2026) - PRD v2.2 + дельта epics

Объект: `epics.md` после дельты 02.09 (35 историй: новые 4.0, 4.4, 5.0; детальные AC Epic 4/5; раздел «PRD v2.2 → истории»; правки CP-1..CP-10) против PRD v2.2, `sprint-change-proposal-2026-09-02.md`, `SPEC.md` + `glossary.md`, `ARCHITECTURE-SPINE.md` v3.3, `sprint-status.yaml` (пересобран 02.09). Проверено по фактам: `sprint_plan.py validate` - `valid: true`, 0 problems; ключи `sprint-status.yaml` = 35 = число заголовков `### Story` в `epics.md` (сверка скриптом, 0 сирот в обе стороны); mtime `SPEC.md`, `glossary.md`, `ARCHITECTURE-SPINE.md` - без изменений 02.09; `DECISIONS.md` заканчивается D24 (31.08); `db/migrations/007_quality_lineage_facts.sql:49-63`; `infra/systemd/proxima-morning@.service`. Центральный вопрос гейта: сможет ли исполнитель реализовать эти эпики, не придумывая решений, которых нигде не записано.

## Вердикт прохода 5: CONCERNS

- Ближайшая очередь сентября (1.4 → 1.5 → 1.6 → 1.7) остаётся реализуемой: AC привязаны к AD, выводы проходов 3-4 в силе, ни одна находка её не блокирует.
- Дельта закрыла пять находок прохода 4 из четырнадцати и дала носителей октябрьским пробелам (4.0, 4.4, 5.0), но открыла новое противоречие в условиях Story 1.14 и не тронула канон (SPEC, glossary, спайн), поэтому три расхождения прохода 4 остаются в OQ-16 с блокирующей частью до 08.09.
- Трассировка вперёд чистая: все 40 FR PRD имеют строку в разделе «PRD v2.2 → истории» (25 с носителем, 9 отложены → CM-n, 5 `[PROPOSED]`, FR-33 зарезервирован); сирот-FR нет. Назад: 35 историй = 35 ключей трекинга, лишних ключей нет; 6 историй без строки FR - уровня NFR/AR (см. N10).
- Новые находки: **High 2, Medium 5, Low 4**. Обе High касаются сентябрьского релиза 1.14.

## 1. Статус находок прохода 4

| # | Было | Стало | Где проверено |
|---|---|---|---|
| H1 FR-20/FR-21 | Носителя нет | **Закрыта.** Решение 6а: FR-20/FR-21 → CM-20, носителя намеренно нет; записано в PRD §4.C (статус «отложено → CM-20»), §4.G, §12 (карточка CM-20), OQ-17 закрыт, строка в таблице «PRD v2.2 → истории» | PRD §4.C, §12; `epics.md` раздел трассировки |
| H2 CAP-6 против D23 | Канон требует CSV с 01.09 | **Переведена в OQ-16.** Сторона нарезки закрыта (CP-9: FR9 «(октябрь, D23)», Epic List, тело Epic 3, карта покрытия), но `SPEC.md` CAP-6 intent не менялся и по D17/D22 остаётся победителем при расхождении | mtime SPEC.md; `epics.md:32,86,104,431` |
| H3 крайний срок 06:30 | Носителя нет | **Частично.** Срок внесён в Then Story 1.14 (CP-2), но механизм («превышение видно как алерт») не записан ни в AD-6, ни в AD-17, ни в юните; и сам AC ссылается на `brief_current`, которого в M-01 нет - см. N2 | `epics.md` Story 1.14; `infra/systemd/proxima-morning@.service` |
| M1 «Норма» | glossary против AD-8 | **Открыта.** `glossary.md` не менялся: «медиана за 14 последних полных дней» против фиксированного окна `[eval-14, eval-1]` в AD-8 и AC Story 2.3; 2.3 - первая история Epic 2 в очереди | mtime glossary.md; `epics.md` Story 2.3 |
| M2 окно v3 | `[run_day-7…]` не подтверждён | **Закрыта на уровне истории.** CP-8: окно `[run_day-6, run_day-1]` - единственная подтверждённая граница, живой лимит фиксируется первым прогоном. Остаток - N8 (AD-5 и FR8 всё ещё «7 дней») | `epics.md` Story 3.1 |
| M3 грейн категории | Без источника | **Переведена в Story 4.0.** Грейн и способ получения категории записаны в Given 4.0, но AD остаётся «предложением», спайн Deferred не менялся, и грейн конфликтует с существующей таблицей - см. N5 | `epics.md` Story 4.0; спайн Deferred |
| M4 AD записи из webapp | Нет в очереди спайна | **Закрыта.** Story 5.0 - единица архитектуры с явным шагом «AD принят D-записью в `DECISIONS.md`; спайн обновлён»; Story 5.3 ссылается на него в Given | `epics.md` Stories 5.0, 5.3 |
| M5 срок 3.1 | Носителя нет | **Закрыта документально.** CP-8: «срок - в работу не позже 08.09.2026, в main до тега 2.6» в Given Story 3.1; исполнение (3.1 в `backlog` за 1.4) - приоритет Mike, не документный дефект | `epics.md` Story 3.1 |
| L1 дата отсечки бэкфилла | UNKNOWN | Открыта (PRD §8.0 п. 1) | PRD §8.0 |
| L2 второй tenant | Вне трекинга | Открыта, но записана: строка «UJ-5 второй tenant - единица без истории» в таблице трассировки | `epics.md` раздел трассировки |
| L3 остатки вне реестра | Ни разрешено, ни запрещено | Открыта (OQ-13, разведка 02.09 выполнена, AD нет) | PRD OQ-13 |
| L4 `reportDetailByPeriod` | SPEC против AD-4 | Открыта (OQ-16, неблокирующая часть) | PRD OQ-16 |
| L5 `[NOTE FOR PM]` FR-7 | Не внесён в AC | **Закрыта.** AC 4.1: «`signals[]` не строятся при `brief.status != ok` (PRD FR-7, `[NOTE FOR PM]` закрыт этим AC)»; AC 4.2: «`signals[]` пусто при `status != ok`» | `epics.md` Stories 4.1, 4.2 |
| L6 ML-инварианты без AD | Только в PRD | Открыта (OQ-11) | PRD §11.3 |

Итог: закрыто 5 (H1, M2, M4, M5, L5), частично/переведено 3 (H2, H3, M3), открыто 6 (M1, L1, L2, L3, L4, L6).

## 2. Новые находки по серьёзности

### High

| # | Место | Что не записано / что расходится | Какой навык исправляет |
|---|---|---|---|
| N1 | `epics.md` Story 1.14 Given; Story 1.13 Then шаг (4); CP-5, CP-6; PRD §6.1 | Given 1.14 остался «Stories 1.0-**1.13** смержены», но CP-5 увёл 1.8 в октябрь, а объём 1.11 перенёс в 2.5. При этом приёмка 1.14 («Mike открывает `/brief` и видит строку статуса с сегодняшним временем») и шаг (4) runbook 1.13 («строка статуса на `/brief`») требуют статус-части `postgres-provider.ts`, которая по CP-6 **исполняется в Story 2.5**, а очередь PRD §6.1 - `… 1.13 → 1.14 → 2.3 → 2.4 → (2.5 + 1.11) → 2.6`, то есть 2.5 идёт после релиза 1.14 (≤ 20.09) и уезжает тегом 2.6 (≤ 23.09). Нигде не записано, чем 1.14 принимается до 2.5 (fixtures-режим? отложенная приёмка? перенос части 1.11 в 1.14?) и что теперь значит «1.0-1.13 смержены» при 1.8 в октябре. Исполнитель релиза выберет сам | `bmad-correct-course` (Given и приёмка 1.14, шаг (4) runbook 1.13, порядок мержа), затем `bmad-create-epics-and-stories` при переносе объёма |
| N2 | `epics.md` Story 1.14 Then (CP-2); AD-6 (спайн:75), AD-17 (:159); `infra/systemd/proxima-morning@.service`; Story 2.4, 2.5 | AC 1.14: «утренний прогон завершается и `brief_current`/`data_status_current` обновлены не позже 06:30 МСК». В M-01 `brief_daily`/`brief_current` не существует - миграция `015` приходит в Story 2.4, а шаги `norm`/`brief` попадают в `morning_run.sh` в Story 2.5; в релизе 1.14 `morning_run.sh` содержит только `collect`. Механизма «превышение видно как алерт» тоже нет: `proxima-morning@.service` без `TimeoutStartSec`, `OnFailure` срабатывает на отказ, а не на опоздание; AD-6/AD-17 не менялись, CP-11 добавляет только ретрай алерта. H3 прохода 4 закрыта наполовину: число есть, носитель механизма - нет | `bmad-architecture` (срок и механизм в AD-6/AD-17), затем `bmad-correct-course` (разделить AC 1.14 и 2.6) |

### Medium

| # | Место | Что не записано / что расходится | Какой навык исправляет |
|---|---|---|---|
| N3 | `SPEC.md` CAP-6 intent и success, `glossary.md` «Норма», `ARCHITECTURE-SPINE.md` (не менялись 02.09); PRD OQ-16 | Дельта прошла только по `epics.md`, `prd.md` и `sprint-status.yaml`. В каноне остались: CAP-6 «async CSV с 01.09» (при расхождении по D17/D22 побеждает SPEC), «Норма - 14 последних полных дней» против фиксированного окна AD-8 и AC 2.3 (2.3 - следующая история Epic 2), CAP-6 success «8 недель к 27.10» против SM-7 ≈ 5 недель. OQ-16 держит это открытым с блокирующей частью «до 08.09», но на 02.09 исполнитель, читающий канон, построит другое | `bmad-spec` (CAP-6 intent и success, «Норма» в glossary, слова этапов воронки, constraint `reportDetailByPeriod`) |
| N4 | `DECISIONS.md` (последняя запись D24, 31.08); `epics.md` AC Stories 1.5, 1.11, 2.5, 2.6, 3.1, 4.2, 4.4, AR3, NFR9; Given Story 4.4 | Решения 02.09 (1, 2а, 3а, 4а, 5а, 5б1, 6а, 7а, K4) - источник доброго десятка AC - в корневой `DECISIONS.md` не записаны; живут в `sprint-change-proposal-2026-09-02.md`, PRD §8.0 и тексте историй. Исполнитель, который по контракту репозитория ищет решение в `DECISIONS.md`, «решения 5б1» там не найдёт. Отдельно: Given Story 4.4 требует записи «порог 30 %, источник - ретро-прогон 184 дней, дата» **в `DECISIONS.md` до релиза 2.6**, но носителя этой записи нет ни в историях, ни в CP-11 (там только разметка Владислава) | Решение Mike + D-записи в `DECISIONS.md`; отражение в `docs/agent-system/TASKS.md` / `HANDOFF.md` |
| N5 | `epics.md` Story 4.0 Given; `db/migrations/007_quality_lineage_facts.sql:49-63`; AD-2 (спайн:51), таблица спайна:34; AR1 (`epics.md:53`) | Story 4.0 требует `fact_order_counts` с грейном `(tenant_id, calendar_day, nm_id)`, `run_id` и RLS по шаблону 009. Таблица с этим именем **уже существует** в миграции `007` с ключом `(attempt_id, tenant_id, nm_id, calendar_day)` и FK на `fact_attempt_runs` замороженного business-signal среза (NFR8, AD-18); AD-2 и таблица спайна описывают её как «nmId из CSV, воронка, их сумма никогда не подменяет кабинетный ряд», а 4.0 делает её разрезом заказов с категорией из `subjectName` наблюдений. Не записано: новая таблица, ALTER или переименование (миграции additive-only), и какой номер (AR1 доходит до `016`). Плюс AD в 4.0 остаётся «предложением» - шага принятия, как в Story 5.0, в AC нет, спайн Deferred не менялся | `bmad-architecture` (AD: грейн, имя таблицы, отношение к `007` и к AD-2), затем правка AC 4.0 |
| N6 | `epics.md` Story 5.2 Given; PRD §12 карточка CM-15 | AC 5.2 берёт «справочник причин и чек-лист «что проверить» из эвристик менеджера (CM-15)» как вход для `alternatives`. CM-15 в реестре - «кандидат (как вход, не модуль)», в §4 не входит, артефакта в репо нет и производителя нет ни в одной истории. Исполнитель 5.2 напишет справочник сам | `bmad-create-epics-and-stories` (единица-вход) либо решение Mike о принятии CM-15 |
| N7 | `epics.md` Story 2.6 Given, AR3, Story 3.1 Then; CP-11; PRD OQ-16, §14 | «CR к AD-6 утверждён» - жёсткое предусловие Given Story 2.6 (сентябрь, ≤ 23.09) и условие отдельного юнита `proxima-funnel-v3@` в 3.1 и AR3. Носитель CR - только строка PA-задачи в CP-11 и пункт OQ-16; в `sprint-status.yaml` его нет, поэтому сентябрьская блокировка не видна в трекинге - в отличие от 4.0 и 5.0, которые для аналогичных AD сделали единицами. Риск «до CR принят» записан в PRD §14, но кто и когда выпускает CR - вне трекинга | `bmad-architecture` (выпустить CR к AD-6), отражение в `docs/agent-system/TASKS.md` |

### Low

| # | Место | Что |
|---|---|---|
| N8 | `epics.md` FR8 (`:32`), AD-5 (спайн:69), AD-4 (спайн:63) | Остаток M2: нарезка и спайн по-прежнему говорят «окно 7 дней», Story 3.1 после CP-8 - `[run_day-6, run_day-1]`. Расхождение внутри одного файла и между файлом и спайном; на реализацию влияет только через AD-5 |
| N9 | `epics.md` Story 4.2 Given, Story 4.4 Given | 4.2 читает `alert_threshold_pct` / `threshold_source` / `threshold_date` «из конфигурации control-plane», значение приходит из 4.4; отсутствие обработано (`null` = порог не применяется), но кто заводит саму конфигурацию (файл, формат, дефолт) - не сказано ни в 4.2, ни в 4.4 |
| N10 | `epics.md` раздел «PRD v2.2 → истории» | В таблице нет строк для шести историй - 1.0, 1.2, 1.8, 1.9, 1.10, 2.1 (уровень NFR/AR, подтверждено проходом 4 и PRD §10.1). Обратная сторона таблицы не помечена, поэтому «сирота или намеренно» из неё не читается |
| N11 | `epics.md` Story 4.1 When; PRD FR-8; `SPEC.md` CAP-6 success | 4.1 называет этап воронки только при ≥ 8 недель воронки; по SM-7 к 27.10 накопится ≈ 5 недель, то есть в M-04 этап всегда `UNKNOWN`. В PRD FR-8 это записано явно («до этого статус «этап UNKNOWN»»), в SPEC - нет: CAP-6 success по-прежнему обещает 8 недель к 27.10 (часть N3) |

## 3. Зависимости и конфликты (сводка)

- Цепочки Epic 4 и Epic 5 на будущие истории не ссылаются: 4.0 → 4.1 (`fact_order_counts_current`, ветка pa41) → 4.2 (`signals[]` из 4.1) → 4.3 (`signals[]` в `brief_current`) и 5.0 → 5.3 («AD из Story 5.0 принят») - все ссылки назад. Единственная ссылка вперёд - 4.2 на 4.4 за значением порога, и она обработана явным `null` (N9), поэтому 4.2 остаётся независимо завершаемой.
- Ссылки Epic 4/5 назад в сентябрь корректны: `contracts/{signal,diagnosis,decision-record}.schema.json` - Story 2.1 (done), `SignalRow` - каркас PA-49, `fact_funnel_daily_current` - Story 3.1, `brief_daily.payload` - Story 2.4.
- Скрытая зависимость вперёд - в Epic 1: 1.14 (и шаг (4) runbook 1.13) на Story 2.5 (N1). Это единственная зависимость, пересекающая границу релиза.
- Конфликты между артефактами на 02.09: три канонических (N3), один спайн-против-миграции (N5), один спайн-против-истории (N8). Все, кроме N5, уже перечислены в OQ-16.

## 4. Что осталось UNKNOWN

Дата отсечки бэкфилла по окну WB (FR-27, §8.0 п. 1); порог расхождения и каденция quality-check «кабинетный ряд против суммы nmId» (Story 4.0, OQ-7); ground-truth разметка ретро-тревог как вход 4.4; срок сверки N и границы «частично» (OQ-3); обязательность причины при «принял» (OQ-12); глубина async CSV назад (Story 3.0, OQ-10); статус `reportDetailByPeriod` (OQ-14); формат загрузки остатков (OQ-13); ML-платформа (OQ-11); ПДн и провайдер языковой модели (OQ-15); живой лимит v3 по заголовку ответа; две даты деплоя в календаре Mike (1.14 ≤ 20.09, 2.6 ≤ 23.09) - без них гейт 30.09 не планируется, а переносится.

## 5. Порядок правок (предложение, не решение)

1. N1 - раньше всего: 1.13 уже в очереди, а его шаг (4) и приёмка 1.14 опираются на код Story 2.5. Решение Mike о порядке (перенести часть 1.11 в 1.14 или принять 1.14 без строки статуса), затем `bmad-correct-course`.
2. N2 и N7 - `bmad-architecture` одним заходом: CR к AD-6, срок и механизм 06:30 в AD-6/AD-17.
3. N3 - `bmad-spec`: блокирующая часть OQ-16 (CAP-6 intent, «Норма» в glossary) до 08.09, остальное следом.
4. N4 - D-записи решений 02.09 в `DECISIONS.md`, включая порог 30 % как вход Story 4.4.
5. N5, N6, N9, N10, N11 - октябрьские, до старта Epic 4 после гейта 30.09.

Ни одна находка не блокирует выдачу Story 1.4, 1.5, 1.6, 1.7 в работу.
