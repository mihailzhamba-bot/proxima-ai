# 03 — Repair: находки кросс-модельного ревью codex (6 blockers / 3 warnings)

**Требования:** R04, R06, R07, R09, R11, R16, R18 (ремонт дефектов против спеки и AGENTS.md)
**Blocked by:** —
**Зона:** `services/control-plane/src/proxima_control_plane/detectors/scn001/` (все модули) + `services/control-plane/tests/detectors/` + один артефакт-транскрипт
**Волна:** 1
**Status:** ready

## Что должно заработать

Устранение дефектов, найденных независимым codex-ревью (полный текст вердикта у оркестратора). Каждый пункт = условие с тестом. Семантика спеки не меняется: tenant-фильтр, зрелость до дня D, dedup только для эмитированных сигналов, SourceRef на BLOCKED, конечность Decimal.

## Критерии приёмки

- [ ] **B2 tenant**: `load_bundle(db, d, window=28, *, tenant_id)` - SQL фильтрует `t.tenant_id = %s`; пустой/отсутствующий tenant_id → явная ошибка (fail-closed), не выборка всего. Сверить с `db/migrations/003` (обязательный tenant_id) и 009 (RLS `proxima.tenant_id`) - SQL-фильтр обязателен независимо от RLS-роли соединения. Тест: две SYNTH-выгрузки разных tenant → бандл только своего; без tenant → ошибка
- [ ] **B3 зрелость**: `MetricBundle.build` считает историю только по дням СТРОГО ДО даты оценки D (D не входит ни в окно зрелости, ни в baseline-ряд). Контрпример из ревью закрыт тестом: 20 дней истории + день D → SKU НЕ в панели, BLOCKED INSUFFICIENT_HISTORY, кабинетный сигнал не искажён
- [ ] **B4 dedup**: dedup-записи создаются ТОЛЬКО для эмитированных сигналов (после ₽-фильтра и top-N). Контрпример закрыт тестом: прогон, где все кандидаты отфильтрованы → 0 сигналов И 0 новых dedup-записей; повторный прогон со значимыми сигналами их не подавляет
- [ ] **B5 SourceRef**: `BlockedEntry` несёт source_refs; `attach_source_refs` заполняет и signals, и blocked. Тест: после attach у каждой BLOCKED-записи есть task_id
- [ ] **W1 конечность**: `to_decimal` в metrics.py отклоняет non-finite Decimal (NaN/Infinity) с явной ошибкой - тот же guard, что в loader. Тест: Decimal("NaN") на входе MetricBundle.build → ошибка, не InvalidOperation глубже по стеку
- [ ] **W2 smoke exit-коды**: UNKNOWN без DATABASE_URI → exit 0 (как в брифе); MISMATCH → exit 2 с перечнем расхождений; DB/SQL-ошибка → exit 3 с именем ошибки (без значений переменных окружения). Тесты на три ветки
- [ ] **W3 флейк**: тест clock.py - ассерты только на инъекционных кейсах now; живой now() не сравнивается с вторым живым now()
- [ ] **B6/R16 транскрипт**: артефакт прогона smoke против реального payload сохранён в репо (`.autopilot/2026-08-27-pmm20-scn001-core/evidence-r16-smoke.md`): дата, task_id, row_number, статус каждой колонки PRESENT, список внесистемных ключей, строка "REGISTRY STATUS OK". Комментарий в loader.py:23-27 ссылается на файл
- [ ] Весь suite зелёный: `cd services/control-plane && uv run --extra test pytest tests/ -q`; `bash scripts/agent/verify` PASS (нормальная оболочка, не sandbox)

## Вердикт кросс-модельного ревью codex

- Раунд 1 (весь ран): 6 blockers / 3 warnings → этот таск
- Раунд 2 (фикс): 8/9 addressed + 2 новых blocker (smoke DB_ERROR vs UNKNOWN, maturity fallback) + 1 warning (interfaces stale, закрыт оркестратором)
- Раунд 3: 2/2 addressed, новых находок нет - **VERDICT: 0 blockers, 0 warnings** (2026-08-28)
- Ограничение: codex read-only sandbox не может исполнить uv/make (EPERM на кэши) - verify-гейт переотдоказан оркестратором в нормальной оболочке: scripts/agent/verify PASS, make verify PASS (см. историю рана)
