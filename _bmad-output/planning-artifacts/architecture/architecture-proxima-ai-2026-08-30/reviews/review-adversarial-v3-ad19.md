# Reviewer Gate - AD-19 (update v3.4 → v3.5, 08.09.2026)

Режим: update intent, без субагентов (ограничение единицы) - один враждебный проход автора против спайна после дистилляции. Lint `lint_spine.py`: 0 находок до и после. Рендер mermaid не выполнялся (в worktree нет `mmdc`, сеть запрещена) - три новые строки erDiagram синтаксически повторяют существующие.

**Вердикт:** AD-19 пригоден как предложение к D32; 7 уточнений внесены в правило, 1 дыра вынесена в Deferred, 4 вопроса - Mike.

## Атака: две единицы, соблюдающие AD дословно, но несовместимые

| # | Дыра | Уровень | Исход |
|---|---|---|---|
| 1 | Нулевая строка (день × nmId без наблюдений): одна единица кладёт `evidence_sha256 = '{}'`, другая - артефакты прогона | high | autofix: правило кабинета (артефакты прогона) записано явно |
| 2 | Гейт `order-counts` только как `*.db.test.ts` - в CI и на VPS без PG16 `pg-roundtrip = SKIP`, AC «`make verify` зелёный» недостижим | high | autofix: гейт = unit-тест `node:test` на фикстурах (везде) + тот же SQL в db-тесте (где есть PG16) |
| 3 | Story 4.3 показывает артикул и предмет; без правила webapp мог бы получить грант на факты вопреки AD-9 | high | autofix: адаптер копирует `nm_id`, `supplier_article`, `subject_name` в `detection_data`; webapp читает payload |
| 4 | Check по дням: день без строк nm даёт `NULL`, одна единица считает это MISMATCH, другая - PASS | medium | autofix: `COALESCE`, отсутствие = 0 |
| 5 | `dim_nm_subject` без индекса `(run_id)` - CASCADE при `delete_run` идёт seq-scan'ом, в отличие от 017 | medium | autofix: индекс добавлен |
| 6 | Читатель AD-2 («сумма nmId никогда не подменяет кабинетный ряд») против AD-19 («суммы равны по построению»): можно прочитать как разрешение брать заказы кабинета из `fact_nm_daily` | medium | autofix: явная фраза «заказы кабинета только из `fact_cabinet_daily`; равенство - проверка, не источник» |
| 7 | `collector_runs.kind` CHECK из 011 под additive-only заморожен (`DROP CONSTRAINT` запрещён): детектор как отдельный прогон невозможен; Story 5.0 обещает `kind = decision` | high (вне AD-19) | AD-19: детектор - шаг `brief`; дыра для 5.0 и Epic 6 вынесена в Deferred, вопрос Mike |
| 8 | Имя: epics.md 4.0/4.1 говорят `fact_order_counts_current`, AD-19 - `fact_nm_daily_current` (конвенция `fact_<grain>_daily`, и legacy-таблица 007 с тем же именем) | high | не autofix (epics.md вне границ единицы): вопрос Mike/оркестратору - править 4.0/4.1 при записи D32 |
| 9 | Given истории: «гранты collector/norm/webapp/janitor»; AD-19 не даёт гранта webapp (AD-9: ровно два SELECT из `brief_current`/`data_status_current`) | medium | сознательное отклонение, вопрос Mike |
| 10 | Метка ребра PG → control-plane в AD-16 (`fact_*_current`) не называет `dim_nm_subject_current`; ребро существует, метка иллюстративна | low | не трогаем чужой AD; при D32 оркестратор может расширить метку |

## Rubric walker (good-spine checklist)

- Точки расхождения для уровня ниже (4.0, 4.1, 4.3): грейн, справочник, писатель, check, роли, контракт чтения - все закрыты правилом; норма SKU - Deferred с зафиксированным промежуточным поведением (считается в прогоне детектора, пишется в `detection_data`), две единицы разойтись не могут.
- Каждое Prevents имеет исполняемый пункт правила: legacy 007 - запрет писателя + причина; два определения заказов - отдельная таблица; категория колонкой - справочник с версиями; чтение payload - гранты только на факты; нули - правило «строка на каждый день × nmId»; подмена ряда - фраза про AD-2; двойная выручка - колонки `revenue_rub`/`forpay_rub` в факте; невидимые строки - CASCADE от `collector_runs`.
- Ратификация brownfield: формулы и транзакция - из `cabinet-daily.ts`/`collect.ts`/`backfill.ts` (оба зовут `aggregateCabinetDaily` внутри `ledger.succeed`); имена полей payload - по фикстуре (`subject`, `category`, `brand`, `supplierArticle`, `nmId`), не по тексту истории (`subjectName` - имя из v3); формы миграции - по `verify_migrations.py`.
- Verified-current: новых технологий нет; номер миграции 018 сверен с `db/migrations/` (017 - последняя); ветки `pa41-full-w2-phase3` и `pmm-20-scn-001-…` прочитаны.
- Наследованные AD не ослаблены: AD-2 (кабинетный ряд - источник), AD-3 (версии, CASCADE, `_current`), AD-9 (webapp два SELECT), AD-11 (шаблон грантов/политик), AD-14 (additive-only, целевой номер), AD-16 (control-plane читает только `_current`).

## Что осталось Mike (см. отчёт единицы, «Open questions»)

1. Имя таблицы `fact_nm_daily` вместо `fact_order_counts` в epics.md 4.0/4.1 (правка при D32).
2. Без гранта webapp на факты (отклонение от Given истории).
3. Заморозка `collector_runs.kind`: доктрина AD-14 vs Story 5.0 `kind = decision`.
4. Допуск check по деньгам, если полные фикстуры покажут больше двух знаков (вместе с OQ-7).
