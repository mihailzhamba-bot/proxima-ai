# Релиз: <имя релиза, например M-01>

## Дата и исполнитель

- Дата релиза: UNKNOWN
- Исполнитель (runbook, «Исполняет»): UNKNOWN
- Слово «деплой» от Mike получено: UNKNOWN (дата/время UTC: UNKNOWN)

## Тег и `main` sha

- Релизный тег: UNKNOWN (форма по runbook §0/§2)
- `main` sha на момент тега: UNKNOWN
- Baseline-тег отката: UNKNOWN

## Предусловия (readiness, блокеры B1-B10)

Источник статусов: `docs/state/RELEASE-READINESS-1.14.md` (ревизия на день релиза). В клетку - статус на день релиза и однострочный факт.

| # | Блокер | Статус | Факт (дата, источник) |
|---|---|---|---|
| B1 | Story 6.1 теневой пересчёт | UNKNOWN | |
| B2 | Дата деплоя + слово «деплой» | UNKNOWN | |
| B3 | Runbook сведён с `main` и сервером | UNKNOWN | |
| B4 | Схема боевой базы против кода | UNKNOWN | |
| B5 | Роль аналитика (Story 6.4) | UNKNOWN | |
| B6 | Копия артефактов бэкфилла в S3 | UNKNOWN | |
| B7 | Живая сеть WB в контуре деплоя | UNKNOWN | |
| B8 | Репетиция на VPS | UNKNOWN | |
| B9 | Webapp читает свой URI-секрет | UNKNOWN | |
| B10 | Postgres-режим webapp без 500 | UNKNOWN | |

## Шаги runbook §0-§6

Каждая строка - шаг runbook. «Отклонения» - расхождения с ожидаемым выводом runbook; пусто = совпало.

| Раздел | Шаг | Время (UTC) | Результат | Отклонения |
|---|---|---|---|---|
| §0 | оживление чекаута, baseline-тег, checkout релизного тега | | UNKNOWN | |
| §1.1 | `.env` и `jobs.env` (копия старого `.env`) | | UNKNOWN | |
| §1.2 | переименование токенов, chown 1010:1010 | | UNKNOWN | |
| §1.3 | raw-каталог | | UNKNOWN | |
| §1.4 | `proxima-psql-owner`, provision (прогон 1) | | UNKNOWN | |
| §2 | build образов | | UNKNOWN | |
| §2 | `apply-migrations` через `control-plane-admin` | | UNKNOWN | |
| §2 | `schema_migrations` → ожидание runbook | | UNKNOWN | |
| §2 | provision (прогон 2, идемпотентность) | | UNKNOWN | |
| §2 | `compose up -d postgres` | | UNKNOWN | |
| §3 | sha256 артефактов 31.08 против `API-FACTS.md` | | UNKNOWN | |
| §3 | `cas_import.ts` (пара 31.08) | | UNKNOWN | |
| §3 | `backfill --source artifact:…` | | UNKNOWN | |
| §3 | живой хвост `collect --date-from 2026-08-27` | | UNKNOWN | |
| §4 | W10 - сумма недели | | UNKNOWN | |
| §4 | дни 24-26.08 - пара 31.08 | | UNKNOWN | |
| §4 | дни 27-30.08 - последние наблюдения | | UNKNOWN | |
| §4 | ledger: прогоны, `last_full_day`, `stale` | | UNKNOWN | |
| §4 | `WORKS-TODAY.md` пройден целиком | | UNKNOWN | |
| §5 | проверка монтирования compose (AD-6) | | UNKNOWN | |
| §5 | установка юнитов, enable таймеров | | UNKNOWN | |
| §5 | drop-in PA-13 поставлен | | UNKNOWN | |
| §6 | тестовое сообщение `proxima-alert@test.service` | | UNKNOWN | |

## Проверка цифр §4

Формы - runbook §4 и `docs/state/API-FACTS.md` («Эталоны недельных сумм W10/W35», «Что означают эталоны»); правило гейта - решение Mike 08.09.2026: W10 точно, W35 по дням.

- **W10 (02.03-08.03.2026) - сумма недели, копейка в копейку.**
  - SQL: `sum(orders_count), sum(revenue_rub)` по `fact_cabinet_daily_current`, `calendar_day BETWEEN '2026-03-02' AND '2026-03-08'`.
  - Эталон: `649 | 700860.50`.
  - Получено: UNKNOWN
- **Дни 24-26.08 - равны паре 31.08 точь-в-точь.**
  - SQL: `calendar_day, orders_count, cancelled_count, revenue_rub` за `BETWEEN '2026-08-24' AND '2026-08-26'`.
  - Эталон: `55|6|62146.87`, `40|7|29247.90`, `28|4|44956.00`.
  - Получено: UNKNOWN
- **Дни 27-30.08 - равны последним наблюдениям.**
  - SQL: факт дня против счёта строк `stg_wb_orders_latest` за московский день (первые 10 символов бесзонного текста WB, AD-7) с `isCancel` не-true / true; четыре строки, `t` в последней колонке у каждой.
  - Эталон: равенство пар колонок, `same = t` ×4 (внешних констант для этих дней нет; числа дня релиза не сравниваются с репетицией).
  - Получено: UNKNOWN
- **Ledger после гейта:** `last_full_day` = UNKNOWN, `stale` = UNKNOWN, прогоны `backfill` = UNKNOWN, `collect` = UNKNOWN.

Расхождение любой строки - гейт не пройден, релиз останавливается (runbook §4).

## Наблюдение три утра (CAP-1)

Три утра подряд после релиза: прогон SUCCEEDED, `last_full_day` вчерашний (runbook §8).

| Утро | Дата | Статус прогона | `last_full_day` | Примечание |
|---|---|---|---|---|
| 1 | UNKNOWN | UNKNOWN | UNKNOWN | |
| 2 | UNKNOWN | UNKNOWN | UNKNOWN | |
| 3 | UNKNOWN | UNKNOWN | UNKNOWN | |

## Откат (§7) - применялся или нет

- Откат применялся: UNKNOWN (да/нет)
- Если да - что выполнено (снятие таймеров, drop-in, `delete_run.py` по прогонам, возврат кода и `.env` на baseline): UNKNOWN
- Миграции не откатывались (AD-14): UNKNOWN / не применимо

## Открытые вопросы

- (пусто)
