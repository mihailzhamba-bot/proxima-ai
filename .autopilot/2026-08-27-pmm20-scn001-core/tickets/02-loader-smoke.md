# 02 — Loader staging-данных + smoke + verify-гейт

**Требования:** R09, R11 (source_refs=task_id), R16, R18
**Blocked by:** 01
**Зона:** `services/control-plane/src/proxima_control_plane/detectors/scn001/` (`loader.py`, `smoke.py`) + `services/control-plane/tests/` (тесты loader'а)
**Волна:** 2
**Status:** ready

## Что должно заработать

Тонкий loader: из staging PostgreSQL (`stg_wb_nm_report_rows`) резолвит последние DOWNLOADED task_id, покрывающие окно [D−28, D], парсит payload jsonb по реестру колонок (fail-closed на отсутствующую), строит канонический бандл с заполненными source_refs (task_id) — готовый вход для `detect()` из T01. Отдельный read-only smoke-скрипт сверяет реестр колонок с одной реальной строкой payload; без туннеля/`DATABASE_URI` печатает UNKNOWN и завершается успешно.

## Из брифа, дословно

> «отдельный loader (резолв последних DOWNLOADED task_id за период, парсинг payload jsonb по реестру маппинга, fail-closed на отсутствующую колонку)»
> «точные имена колонок - верифицировать по реальному payload через туннель до кодинга, маппинг в одном реестре с fail-closed»
> «read-only smoke против staging через туннель (если поднят): взять одну реальную строку payload, сверить реестр маппинга колонок с фактическими ключами WB-отчёта; туннель не поднят - фиксируем UNKNOWN»
> «source_refs на task_id → воспроизводимость»

## Разделы спецификации

История 10, 16; Решения: «Loader», «Smoke»; Границы: `loader`.

## Критерии приёмки

- [ ] `parse_payload_row(payload)` — чистая функция: валидная строка → `DailyMetrics`; отсутствующая колонка → явная ошибка с именем колонки (fail-closed); нечисловое значение → явная ошибка, не NaN
- [ ] Реестр колонок — один dict (`COLUMN_MAP`), имена помечены «verify via smoke (R16)»; тесты гоняют парсер на SYNTH-payload с теми же ключами
- [ ] Резолвер task_id: SQL выбирает DOWNLOADED task'и, покрывающие окно, без дублей дней; пересекающиеся task'и детерминированно резолвятся (последний downloaded_at, tie-break по task_id)
- [ ] Интеграционный тест ядра с loader'ом (на SYNTH-строках + fake-соединении, без реальной БД): payload-строки → бандл → `detect()` → сигнал с заполненными source_refs
- [ ] `smoke.py`: с `DATABASE_URI` — печатает сверку ключей реестра против реальной строки (read-only, одна строка); без — печатает UNKNOWN и exit 0; в `make verify` не входит
- [ ] `make verify` зелёный на полном диффе рана (R18)
