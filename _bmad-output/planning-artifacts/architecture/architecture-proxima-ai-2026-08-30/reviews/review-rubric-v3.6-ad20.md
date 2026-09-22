# Reviewer Gate - AD-20, линза verified-current + rubric walker (update v3.5 → v3.6, 09.09.2026)

Режим: read-only субагент. Каждое конкретное утверждение первой редакции AD-20 проверено файлом репозитория, а не по памяти. Рендер mermaid не выполнялся (сеть запрещена; спайн рендерится не `make architecture` - тот берёт `docs/architecture/*.mmd`); две новые строки erDiagram синтаксически повторяют существующие.

**Вердикт первой редакции:** форма гейтов сверена и верна, но три committed-утверждения репозиторием не подтверждаются и три наследованных AD оставлены дословно противоречащими. После правок автора (v3.6) вердикт снят.

## Ось 1 - verified-current: что сверено по репозиторию

| Утверждение AD-20 | Источник проверки | Итог |
|---|---|---|
| `019` - следующий свободный номер | `db/migrations/` = 001..018; `tools/verify_migrations.py` строит `expected` и валит «migration order gap» | подтверждено; по AD-14 формулировка изменена на «целевой номер» |
| Имена ролей не сталкиваются | 009, 011, `provision-runtime-roles.sh`, `provision-analyst-role.sh`, `provision-postgres-diagnostics.sh` | подтверждено: ни `proxima_ui_writer`, ни `proxima_webapp_writer` нигде не встречаются |
| `CREATE ROLE proxima_ui_writer NOLOGIN` - единственная проходящая форма | `verify_migrations.py` `CREATE_ROLE_ALLOWED_FORM` | подтверждено дословно |
| `FOR INSERT` невозможен: гейт требует `USING`, PostgreSQL принимает у `FOR INSERT` только `WITH CHECK` | `verify_migrations.py` `CREATE_POLICY_ALLOWED_FORM` | подтверждено, ловушка реальна |
| Двухаргументный `current_setting(…, true)` обязателен | `verify_migrations.py` `TENANT_GUARD` | подтверждено |
| `GRANT DELETE` в ledger запрещён, DELETE доберёт bootstrap | `verify_migrations.py` (только SELECT/INSERT/UPDATE/USAGE); `provision-runtime-roles.sh` `\gexec`-цикл по колонке `run_id` | подтверждено, `decision_records` подхватится автоматически |
| Имена env и файлов секретов свободны | 0 вхождений `WEBAPP_WRITE_DATABASE_URI_FILE`, `WEBAPP_ACTOR`, `proxima_webapp_writer_uri` | подтверждено |
| `signal_id` = `scn001-<день>-<уровень>-<ключ>` | `detector/signals.py`, уровни `sku`/`subject`, ключ - `nm_id` либо `subject_slug()` | подтверждено дословно |
| `services/webapp/Dockerfile` работает под uid 1001 | `useradd --system --uid 1001 … webapp` + `USER webapp` | подтверждено |
| `test_provision_runtime_roles.py` связывает uid образов с правилом chown | тест сверяет uid обоих job-образов и webapp-образа и запрещает глоб `proxima_webapp_*` | подтверждено; явная строка chown обязательна |
| `delete_run.py` не меняется | три явных DELETE, остальное CASCADE | подтверждено |
| `pg-roundtrip` SKIP'ает без PG16 | `tools/pg_local_roundtrip.sh` | подтверждено; **но в CI PG16 есть** (`.github/workflows/verify.yml` ставит `postgresql-16`), поэтому скобка AD-19 «в CI `pg-roundtrip` = SKIP» устарела - чужой AD, autofix не делался |
| `proxima_webapp_readonly` прочитает `orphaned` через `LEFT JOIN collector_runs` под `security_invoker` | 011 даёт этой роли `GRANT SELECT` и политику `FOR SELECT` на `collector_runs` | подтверждено; в правило добавлена явная фраза |
| Новых технологий нет | Stack-таблица; `crypto.randomUUID()` - встроенный Node 22 | подтверждено на уровне таблицы, но см. Н-2 |
| `payload` валиден по неизменной `decision-record.schema.json` v1 | схема, оба примера, сгенерированный тип | **опровергнуто по составу полей** (Н-1) |
| Валидация Ajv в webapp | `ajv` не в `services/webapp/package.json`; `src/tests/brief-fixtures.test.ts` фиксирует «без Ajv - в webapp его нет, а новые зависимости запрещены»; `contracts/*.json` не попадают в образ | **опровергнуто** (Н-2) |
| `*.db.test.ts` как носитель RLS-матрицы | все файлы - в `services/collector/tests/`, `test:db` - скрипт workspace коллектора; AD-12 называет команду поимённо | уточнено (Н-5) |
| D35 / D36 | `DECISIONS.md` D35 addendum (uid 1001), D36-C3 («бюджет не больше 2 SELECT на полосу»), D36 «Не в очереди: Story 4.4 и Epic 5» | ссылки точные; статус AD-20 как предложения заморозке D35 не противоречит |
| `docs/agent-system/DECISIONS.md` | DEC-001, DEC-002, DEC-005, DEC-006 | конфликтов нет |

## Ось 2 - rubric walker (good-spine checklist)

- **Точки расхождения для уровня ниже.** Для Story 5.3 закрыты: грейн, логический ключ, append-only без `UPDATE`, разделитель `run_id IS NULL`, отсутствие синтетического прогона, `source_run_id` без FK с разобранными тремя альтернативами, `orphaned` как вычисляемое поле, два пула, ответ после `COMMIT`, генерация `record_id` на стороне handler. Для CM-19/CM-1 якорь стоит в Deferred - две единицы не разведут ни роль, ни пул, ни шаблон.
- **Каждое Prevents против исполняемого пункта.** Из четырнадцати Prevents исполняемы одиннадцать в первой редакции; три висели (исход правкой строки - форма payload не задана; третий SELECT - предотвращён на словах и разрешён в том же абзаце; `orphaned` - зависит от роли и от несуществующего FK). После правок исполняемы все, кроме «write-эндпоинт наружу», который остаётся текстовым условием релиза без автоматического гейта.
- **Ратификация brownfield.** Ратифицировано: шаблон грантов и политик 011/018, self-checksum, «одна миграция - таблица + view + индексы + гранты + RLS + политики», `security_invoker`, пул с `set_config(…, false)` первым statement, `verify_*.py` по образцу `verify_wb_client.py`, целевой номер с перенумерованием второй ветки. Не ратифицировано в первой редакции: форма FK на `tenants`, workspace `*.db.test.ts`, суффикс DSN, правило «в webapp Ajv нет» - всё исправлено.
- **Молчащие измерения.** Data shape - закрыто; roles/security - закрыто после четырёх политик; testing/gates - закрыто после привязки к `pg_local_roundtrip.sh` и workspace коллектора; contracts - закрыто после Н-1/Н-2; **operations/deploy** молчал целиком (только файл секрета и имя env) - закрыто перечислением overlay, `/run/secrets/`, runbook и строки-отчёта provision.
- **Наследованные AD.** Ослаблены в первой редакции: AD-9 (третий SELECT при «читатель не меняется»), AD-10 (payload не валиден по неизменной v1, Python-валидатор не назван), AD-14 (номер как факт вместо целевого). Не ослаблены: AD-1, AD-2, AD-3 (механика верна; требуется однострочное исключение для `run_id NULL`), AD-4, AD-11 (кроме полноты политик), AD-12, AD-13, AD-15, AD-17, AD-18 (`api/auth` не тронут, новый маршрут `api/decisions` вне заморозки), AD-19.

## Находки

| # | Находка | Уровень | Исход |
|---|---|---|---|
| Н-1 | `payload` против живой схемы v1: `additionalProperties:false`; `required` включает `actual` и `delta`; `horizon_days` - поле `$defs/measurement`, не корневое; при `actual:null` условие схемы запрещает `outcome`; строка-исхода из одних `actual`/`delta`/`outcome` провалит `required` | critical | autofix: форма обоих payload'ов записана явно, `horizon_days` - внутри `expected`, исход = копия payload решения с тремя заполненными полями, `actor` исхода = автор решения |
| Н-2 | «Валидация - Ajv»: `ajv` нет в webapp, тест фиксирует запрет новых зависимостей, `contracts/*.json` нет в образе | critical | autofix: структурная проверка по схеме (образец `brief-fixtures.test.ts`) в handler; полная `jsonschema`-валидация - Python-путь AD-10 и `make contracts` |
| Н-3 | Политики только двум ролям из четырёх: `proxima_webapp_readonly` увидит 0 строк, `proxima_job_norm` не запишет исход | high | autofix: четыре политики перечислены |
| Н-4 | AD-3 («все новые таблицы: `run_id NOT NULL … CASCADE`»), AD-9 («ровно два SELECT»), AD-16 («рёбра только как на диаграмме» - ребра webapp→PG на запись нет) оставлены дословно противоречащими | high | не autofix (чужие AD, до D-записи не правятся): AD-20 перечисляет три однострочные правки как условие своего принятия |
| Н-5 | Гейт не приземлён: workspace `*.db.test.ts`, имя DSN, `pg_local_roundtrip.sh`, make-таргет и его место в `verify:` не названы | high | autofix: названы `services/collector/tests/decision-records.db.test.ts`, `PROXIMA_TEST_DSN_WEBAPP_WRITER`, шаг provision/harness и таргет `decision-records` |
| Н-6 | Расхождение с литерой историй: Given 5.0 требует `kind = decision`, Given 5.3 - «записи помечаются `orphaned`, не удаляются» (строки-исхода исчезают по CASCADE) | medium | не autofix: оба расхождения названы в правиле и вынесены в вопросы Mike |
| Н-7 | Форма FK на `tenants` не совпадает с живыми миграциями (`REFERENCES tenants(tenant_id) ON DELETE RESTRICT`) | medium | autofix |
| Н-8 | Операции и деплой молчат: второй `secrets:`-элемент и вторая env в staging-overlay, закрытый список env витрины в runbook 2.6, дословно закреплённая строка-отчёт provision, `PROXIMA_*` для webapp | medium | autofix: носители перечислены, `PROXIMA_*` переведён из `[ASSUMPTION]` в клаузу правила |
| Н-9 | Что отдаёт `_current` после сверки и по чему считаются SM-4/SM-9 | medium | autofix: `_current` - решение + подклеенный исход + `status`; счётчики - по истории таблицы |
| Н-10 | `WEBAPP_ACTOR` без формы и без fail-closed, в отличие от `WEBAPP_TENANT_ID` | low | autofix: валидация при старте, пустое значение роняет процесс |
| Н-11 | Половина гейт-строки достижима только с PG16 (в CI есть, в зоне OpenHands нет) | low | autofix: записано явно |
| Н-12 | AD-11 говорит «все четыре NOLOGIN-роли создаются в 011», `proxima_ui_writer` - пятая и в 019 | low | autofix: клауза «набор ролей открыт, новая роль заводится в миграции своей первой таблицы» |
| Н-13 | Скобка AD-19 «в CI `pg-roundtrip` = SKIP» устарела (CI ставит `postgresql-16`) | low | не autofix: чужой AD, правится вместе со следующей ревизией AD-19 - в вопросы Mike |

## Что осталось Mike

1. Отмена `kind = 'decision'` из Given Story 5.0 и правка `epics.md` 5.0/5.3 при записи D.
2. Сужение первого consequence FR-16 и Given 5.3.
3. Три однострочные правки AD-3 / AD-9 / AD-16 как условие принятия AD-20.
4. Устаревшая скобка AD-19 про CI (`pg-roundtrip` в CI не SKIP).
