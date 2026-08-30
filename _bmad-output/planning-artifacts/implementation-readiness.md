# Implementation Readiness - epics.md (30.08.2026)

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
