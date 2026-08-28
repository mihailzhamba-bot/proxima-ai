# 03 — Eval: датасет ≥12 кейсов, раннер, гейт ≥80%, latency

**Требования:** R04, R05, R07, R08, R09, R10, R11, R12, R13, R14, R15, R23, A01, R26
**Blocked by:** 02
**Зона:** `services/control-plane/tests/diagnosis/` (data/eval/, eval_runner.py); + корневой `.gitignore` (ровно одна строка: `logs/` - владелец по ревью T02, дефолтный audit_path не должен попадать в git)
**Волна:** 3
**Status:** ready

## Что должно заработать

Eval-датасет ≥12 фиксированных кейсов W1 на SYNTH-*-fixtures + детерминированный раннер с отчётом pass-rate и гейтом ≥80% в pytest. Adversarial-кейс с prompt-инъекцией и кейс «числа Z нет во входе» проходят. Полный путь сигнал→диагноз зелёный без сети и живого токена. После тикета: make verify, reviewer, PR.

## Из брифа, дословно

> «Свои ≥12 кейсов ...: schema-valid, все числа output ∈ input, каждый факт с source_ref», + adversarial-кейс + кейс «числа Z нет во входе»
> «SCN-001 = синтетика с декомпозицией U×CVR×AOV, SCN-005 = OOS/days-cover поля»; SCN-008 = форма scn_008_partial.json (SYNTH-*)
> «GIVEN eval dataset (≥10 кейсов W1) WHEN прогон THEN ≥80% ...; 0 unsupported чисел»
> «Формат датасета расширяемый для PMM-33»; «latency budget: диагноз батча ... ≤ 5 мин»

## Разделы спецификации

Истории 6, 7, 9, 13, 17, 19, 20, 21; Решения: eval-датасет, fixtures, поставка; Границы: eval_runner.

## Критерии приёмки

- [ ] `cases.json` ≥12 кейсов c `dataset_version`: 4×SCN-001 (вкл. 2 U×CVR×AOV-кейса + 1 «числа Z нет во входе»), 4×SCN-005 (вкл. alternatives≥2/unknowns≥1), 3×SCN-008 (форма CycleInputBundle), 1 adversarial (инъекция в текстовом поле); все значения SYNTH-*
- [ ] SCN-001 payload: units/cvr/aov baseline+current; SCN-005 payload: days_cover, stock_units, avg_daily_orders, oos_flag, oos_started_at, lost_orders_est
- [ ] `eval_runner.run_eval(cases, client) -> EvalReport`: schema-valid, числа ⊆ вход, source_refs ⊆ вход, пер-сценарные asserts (SCN-001 - компонент декомпозиции в primary_cause; SCN-005 - alternatives≥2, unknowns≥1), adversarial - выход не содержит следов инъекции и остаётся schema-valid
- [ ] CLI-подкоманда `eval --dataset <путь>` печатает pass-rate (A01)
- [ ] pytest-гейт: pass_rate ≥ 0.80; 0 unsupported чисел на всём датасете
- [ ] Latency: wall-clock eval-батча < 5 мин (mock - секунды, метрика фиксируется в отчёте)
- [ ] Полный прогон `uv run pytest services/control-plane/tests` зелёный без сети
- [ ] После признания тикета: `make verify`, independent reviewer, PR `pmm-5-llm-analyst` (R26); DoD-чеклист PMM-12 - в Jira-комментарии
