# Интерфейсы — pmm20-scn001-core

## Границы, решённые в спецификации

(копия раздела «Границы и швы» spec.md; сюда не добавлять новых решений)

| Модуль | Владеет | Выставляет | Прячет |
|---|---|---|---|
| `metrics` | канонические типы входа: `DailyMetrics`, `MetricBundle`, агрегация кабинетной панели | `MetricBundle.build(per_sku_rows, maturity_min_days)` | нормализацию Decimal, сортировку |
| `baseline` | сезонный индекс и Expected | `weekday_index(series)`, `expected(series, d, window)`, `history_status(series, d)` | скользящие окна, порог зрелости 21/28 |
| `decomposition` | Шепли | `decompose(u0,cvr0,aov0, u1,cvr1,aov1) -> Contributions` | 6 порядков, zero-collapse ветки |
| `signal` | триггер, ₽-фильтр, дедуп, `DetectorResult` | `detect(bundle, config, threshold_source, dedup_state, evaluation_date) -> Scn001RunResult`, `canonical_hash(obj)` | пороговую логику, сортировку, fingerprint |
| `config` | `Scn001Config` + `ThresholdSource` protocol | `GlobalThresholdSource(config)`, `default_config()` | чтение env |
| `loader` | реестр колонок, парсинг payload | `parse_payload_row(payload) -> DailyMetrics`, `load_bundle(db, d, window) -> MetricBundle` | SQL-резолв task_id, psycopg |

Швы тестов: `detect()` — единственный публичный шов ядра; `parse_payload_row` — шов loader'а. SQL-слой — не шов unit-тестов (накрывается smoke R16).

## Из таска 01 — ядро детектора

- `detect(bundle, config, threshold_source=None, dedup_state=(), *, evaluation_date) -> Scn001RunResult` — единственный шов ядра; evaluation_date обязателен (keyword-only), wall-clock живёт только в `clock.py: default_evaluation_date(now=None)` (вчера Europe/Moscow)
- `MetricBundle.build(rows, maturity_min_days=21, maturity_window_days=28)`, `.panel_daily()`, `.metric_series(sku, field)`; `DailyMetrics(sku, date, orders, open_card, orders_sum_rub, buyouts)`
- `weekday_index/expected/history_status(series, d, window)`; `decompose(u0,cvr0,aov0,u1,cvr1,aov1) -> Contributions(total(), dominant())`; collapse-ветка при нулевой базе даёт точную сумму
- `Scn001RunResult(evaluation_date, snapshot_id, signals, blocked, counters, dedup_state, trust_marking, run_fingerprint)`; `Scn001Signal` (delta_7/14/28, revenue_delta_orders MoneyDelta(value, method="revenue"), contributions, dominant_factor, factors_baseline/actual, source_refs, context, panel_size/excluded_count); `BlockedEntry(reason, level, key, detail)`; `RunCounters(candidates, filtered_by_rub, filtered_by_rank, dedup_suppressed, blocked_by_reason)`
- Конвенции: revenue_delta/contributions — loss-positive (плюс = потеря); snapshot_id = hash({evaluation_date, метрики панели, определение панели}) без excluded; dedup: снятие при recovered `>=` порога или cooldown от last_seen_date (обновляется при повторных срабатываниях)
- Тесты: `cd services/control-plane && uv run --extra test pytest tests/ -q` (21 passed); один файл: `uv run --extra test pytest tests/detectors/test_scn001_signal.py -q`

## Правила проекта (для исполнителей)

- Python 3.14 строго через `uv` (не системный 3.9). Пакет: `services/control-plane` (uv project).
- Деньги и метрики — только `Decimal`. Канонический JSON: `json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)` → sha256. snapshot_id считается от входного бандла, run_fingerprint — от Scn001RunResult.
- Типы ядра — frozen dataclasses. **Никаких новых зависимостей**: pydantic в control-plane не добавлять (его пин приедет с PA-41 W1); stdlib + существующие deps.
- В коде детектора ноль LLM-импортов и ноль сетевых вызовов; ядро (`metrics/baseline/decomposition/signal/config`) не знает про БД. `loader` — единственный, кто касается psycopg/`DATABASE_URI`.
- `contracts/` не трогать (PMM-29, bot lane); TS-типы в `services/collector/src/contracts/` не генерировать и не править.
- Имена WB-колонок в реестре loader'а помечать комментарием «verify via smoke (R16)» — до smoke это UNKNOWN.
- Все исходящие поля несут `trust_marking="unreleased"`; фикстуры помечены SYNTH-* (обезличенные значения, никаких реальных цен/ID кабинетов).
- Канонический гейт: `make verify` из корня репо. Быстрые тесты ядра: `uv run pytest` внутри `services/control-plane`. Коммитить может только оркестратор.
- Недостающая зависимость или недоступная инфраструктура возвращается как `BLOCKED` с кодом, не молча и не самодеятельной установкой.
- Что не трогать: sibling-worktree (Опрос-v2.2, torgstat-collector), `.env`, секреты; ветка этого рана — единственное место коммитов.

## Из таска 02 — loader

- `parse_payload_row(payload, column_registry=COLUMN_MAP) -> DailyMetrics` — чистая функция, fail-closed: отсутствующая колонка / нечисловое / NaN-Infinity → `PayloadParseError` с именем колонки
- `load_bundle(db, d, window=28) -> tuple[MetricBundle, tuple[str, ...]]` — резолвит DOWNLOADED task'и (winners по (row_date, nm_id), sorted+unique), возвращает бандл + резолвнутые task_ids; SQL фильтрует NULL row_date/nm_id (+ Python-гард)
- `attach_source_refs(result, source_refs) -> Scn001RunResult` — заполняет source_refs и пересчитывает run_fingerprint правилом detect()
- `db_from_env(uri=None)` — ленивый psycopg, DATABASE_URI по имени; `COLUMN_MAP` — имена WB-колонок UNKNOWN до smoke R16
- `smoke.py` — read-only, одна строка payload, сверка PRESENT/MISSING; без DATABASE_URI → UNKNOWN, exit 0; в make verify не входит
