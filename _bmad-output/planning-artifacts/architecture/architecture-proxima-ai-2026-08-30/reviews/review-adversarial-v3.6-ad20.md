# Reviewer Gate - AD-20, линза adversarial (update v3.5 → v3.6, 09.09.2026)

Режим: adversarial lens, read-only субагент. Атака построена как две единицы уровнем ниже - Story 5.3 «запись решения» и будущая CM-19 «ручной ввод»: каждая соблюдает первую редакцию AD-20 дословно. Фактические claim'ы сверены с рабочим деревом `night-wt/m3`. Спайн линза не правила; правки внёс автор (см. «Исход»).

**Вердикт первой редакции:** не пригодна как основание для Story 5.3 - 4 дыры critical, 5 high, 8 medium/low. После правок автора (v3.6, ниже) вердикт снят.

## Атака: две единицы, соблюдающие AD дословно, но несовместимые

| # | Дыра | Уровень | Исход |
|---|---|---|---|
| 1 | `decision_records_current` = `DISTINCT ON (tenant_id, signal_id) ORDER BY recorded_at DESC` смешивает решение человека (`run_id IS NULL`) и исход сверки прогона `brief` (`run_id NOT NULL`) в одном логическом ключе: через `horizon_days` исход становится «текущим» и прячет решение, а экран Story 5.3 («≤ 1 SELECT из `_current`») показывает исход вместо «кто/когда/принял» | critical | autofix: view переписан - одна строка на сигнал, решение берётся `WHERE run_id IS NULL`, исход подклеивается `LEFT JOIN` только если он новее решения |
| 2 | Статус «открыто» и SM-9 стирают друг друга: единственный разделитель `run_id IS NULL` делает «открыто» немонотонным - новая отметка человека после сверки возвращает запись в «открыто» и выбрасывает исход из view | critical | autofix: `status` вычисляется как «исход новее текущего решения?»; SM-4/SM-9 считаются по истории таблицы, не по `_current` |
| 3 | `horizon_days` и `snapshot_id` не существуют как корневые поля `decision-record` v1 (`additionalProperties: false`; `horizon_days` живёт в `$defs/measurement`, `snapshot_id` - поле `signal.schema.json`), а AD объявлял схему неизменной - валидатор рубил бы каждый INSERT | critical | autofix: `horizon_days` назван полем `expected`/`actual`; `snapshot_id` из правила убран, провенанс несут колонки `source_run_id`/`brief_day` |
| 4 | `required` контракта включает `decision, actor, decided_at, reason, expected`, значит строка-исхода обязана повторить пять полей решения; AD не задавал ни источника копии, ни валидатора для писателя-джоба | critical | autofix: payload исхода = payload решения с заполненными `actual`/`delta`/`outcome`, источник - `decision_records_current`, валидатор - Python `jsonschema` (путь AD-10) |
| 5 | `provision-runtime-roles.sh` матчит группы по жёсткому `IN (...)` из пяти имён: членство в новой группе не выдаётся никогда, скрипт печатает `ok`, а `INSERT` падает `permission denied` | high | autofix: список `IN (...)` и остальные точки ручного перечисления скрипта названы в правиле поимённо |
| 6 | Гейт недостижим: `pg_local_roundtrip.sh` экспортирует ровно пять DSN, `TEST_SQL` не даёт писателю `CONNECT` к `proxima_test`, а `*.db.test.ts` - конвенция только workspace коллектора | high | autofix: назван шаг `pg_local_roundtrip.sh`, имя `PROXIMA_TEST_DSN_WEBAPP_WRITER` по правилу «LOGIN-пользователь → суффикс», файл теста и `CONNECT` к тестовой базе |
| 7 | AD-9 дословно говорит «ровно два SELECT», AD-20 одновременно утверждал «читатель не меняется» и «читатель читает решения» | high | не autofix (чужой AD): AD-20 перечисляет три однострочные правки AD-3/AD-9/AD-16, которые вступают в силу вместе с его принятием - вопрос Mike |
| 8 | CM-19 не может исполнить AD-20: `signal_id`, `brief_day`, `source_run_id` - `NOT NULL` и заточены под сигнал; константный `signal_id` схлопывает все ручные вводы в одну строку `_current` | high | autofix: правило сузилось до решений по сигналам, ручной ввод - своя таблица в той же группе и том же пуле (Deferred) |
| 9 | «Общий урок из 011» применён к несуществующей колонке-состоянию и пропущен на реально свободном `signal_id` (`text` без CHECK и без FK) | high | autofix: `CHECK (signal_id ~ '^[a-z0-9][a-z0-9-]{1,127}$')`; рост `decision` = `decision-record` v2 по AD-10 |
| 10 | `DEFAULT CURRENT_TIMESTAMP` - время начала транзакции: все строки-исходы одного прогона получают одинаковый `recorded_at`, а ничью разрешает случайный `record_id` | high | autofix: `DEFAULT clock_timestamp()`; после разделения view ничья возможна только внутри одного прогона, где на сигнал приходится одна строка |
| 11 | «Идемпотентность обеспечивает `_current`» - это last-write-wins: повтор POST после таймаута неотличим от «человек передумал» и завышает SM-9, хотя `ON CONFLICT (record_id) DO NOTHING` гейт проходит и требует только INSERT | medium-high | autofix: `record_id` - ключ идемпотентности формы, `ON CONFLICT (record_id) DO NOTHING` |
| 12 | Гейт «`postgres-writer.ts` импортируется только из `src/app/api/`» непроверяем текстовым сканером: барель `src/lib/data/index.ts` существует, реэкспорт прошёл бы любой grep | medium-high | autofix: писатель переехал в `src/app/api/decisions/writer.ts` - проверка стала проверкой пути, а не графа импортов |
| 13 | Политики выданы двум ролям из четырёх: под RLS `proxima_webapp_readonly` увидит 0 строк, `proxima_job_norm` не запишет исход | medium | autofix: перечислены все четыре политики |
| 14 | `[ASSUMPTION]` про `environment:` сервиса `webapp` указывает в `infra/compose.yaml`, где сервиса `webapp` нет; не сказано и про `secrets:` overlay и про путь `/run/secrets/` внутри контейнера | medium | autofix: назван `infra/webapp.staging.compose.yaml`, пара «хостовой путь → `/run/secrets/<имя>`» и `runbook` |
| 15 | Динамический `GRANT DELETE ... WHERE attname = 'run_id'` даёт janitor'у DELETE на всю таблицу, включая строки человека: append-only держится на отсутствии кода, а не на привилегиях | medium | autofix: записано как «конвенция + RLS-тест», по образцу AD-11 для `UPDATE collector_runs` |
| 16 | «`delete_run.py` не меняется» ⇒ `--dry-run` не показывает, сколько строк-исходов уйдёт по CASCADE | medium | autofix: оговорено явно, счётчик CASCADE-таблиц - в Deferred |
| 17 | Номер `019` подан как факт, хотя AD-14 требует «целевой номер» с перенумерованием второй мержащейся ветки | medium | autofix: формулировка AD-19 |
| 18 | `WEBAPP_DATA_MODE` не упомянут: в staging-overlay режим по умолчанию `fixtures`, а POST безусловно открывает пул - решение по несуществующему сигналу | medium | autofix: POST отвечает 403 и форма скрыта вне `WEBAPP_DATA_MODE=postgres` |
| 19 | `orphaned` считается под RLS вызывающего: у роли без гранта на `collector_runs` и у `proxima_sandbox` (BYPASSRLS) результат разный | low-medium | autofix: определено, что `orphaned` осмыслен только под ролью с грантом на `collector_runs`, db-тест бежит под ней |
| 20 | DDL расходится с домовым образцом: `REFERENCES tenants` без `ON DELETE RESTRICT`; `metric.unit` - свободная строка, `RUB`/`rub`/`₽` разойдутся между 5.3 и сверкой | low | autofix: форма FK из 011; словарь `metric.name`/`unit` - в вопросы Mike вместе с OQ-3 |

## Что проверено и подтверждено (атака не прошла)

- **Миграцию гейт пропустит.** `CREATE ROLE … NOLOGIN`, четыре `GRANT` (включая грант на view), политика `FOR ALL … USING … WITH CHECK` с двухаргументным `current_setting('proxima.tenant_id', true)`, `CREATE VIEW … WITH (security_invoker = true) AS …` (тело - `.*` под DOTALL, `DISTINCT ON` и `LEFT JOIN` проходят), `ON DELETE CASCADE`/`SET NULL` внутри `CREATE TABLE`, нумерация без пропусков, индексы без `CONCURRENTLY`.
- **PostgreSQL-семантика верна:** `FOR INSERT` принимает только `WITH CHECK` (отсюда `FOR ALL` в шаблоне и недостижимость `USING` без SELECT/UPDATE/DELETE-гранта); `INSERT … RETURNING` требует SELECT-привилегии; RI-действия обходят RLS; `ON CONFLICT DO NOTHING` требует только INSERT.
- **`collector_runs.kind` из 011 действительно незакрываем аддитивно** - отказ от синтетического прогона обоснован фактом, а не вкусом.
- **Claim'ы про `delete_run.py` подтверждены:** строки с `run_id IS NULL` под CASCADE не матчатся и переживают откат, строки с `run_id NOT NULL` исчезают, кода менять не нужно.
- **Chown-глобы подтверждены:** job-глобы не задевают `proxima_webapp_writer_*`, а `test_provision_runtime_roles.py` прямо запрещает лечить это глобом `proxima_webapp_*` - явная строка обязательна.
- **Два пула не противоречат `postgres-provider.ts`:** читатель владеет собственным ленивым `Pool` с `set_config(…, false)` на `connect`.

## Что осталось Mike

1. Отмена `kind = 'decision'` из Given Story 5.0 (главный вопрос) и правка `epics.md` 5.0/5.3 при записи D.
2. Сужение первого consequence FR-16 и Given 5.3: строки-исходы обратимы по `run_id`, решения человека - нет.
3. Три однострочные правки AD-3 / AD-9 / AD-16, вступающие в силу вместе с принятием AD-20.
4. Словарь `metric.name` / `unit` для решений (вместе с OQ-3).
