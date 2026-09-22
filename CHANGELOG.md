# Список изменений (CHANGELOG)

Формат - [Keep a Changelog 1.1](https://keepachangelog.com/ru/1.1.0/). Журнал ведётся с 08.09.2026: изменения попадают в `## [Unreleased]` по мере слияния в `main`, при релизе исполнитель (см. `docs/operations/releases/`) переносит их в раздел с тегом и датой. Номера PR - в скобках; группировка по темам. Даты релизов и факты дня релиза - журнал релиза `docs/operations/releases/YYYY-MM-DD-<release>.md`.

## [Unreleased]

Попало в `main` 07.09-08.09.2026 (ночь 07-08.09, D31, и день 08.09, D32 + трек D35); релизная привязка - релиз M-01 22.09.2026, тег `v2026.09.22-2` (начало деплоя, `b68c2f6`) с контент-фиксом `v2026.09.22-3` (`36b6dbf`, PR #163) (см. `docs/operations/releases/2026-09-22-m01.md`).

### Added

- Тестовая база и сандбокс M-01 (Story 1.8, PA-60) (#73)
- Ежедневная воронка WB v3 (Story 3.1, PMM-51): job `funnel_v3`, миграция 017 «funnel observations and daily versions», юнит и таймер `proxima-funnel-v3@` на 06:15 МСК, гейт `funnel` в `make verify` (#78, #79)
- CSV-отчёт как прогон реестра (`funnel_csv_download` в ledger) (Story 3.2) (#76)
- Промоушен CSV в витрины, откат по `run_id` (Story 3.3) (#82)
- Грейн nmId по AD-19: `fact_nm_daily`, `dim_nm_subject`, миграция 018; пишутся тем же прогоном, что и дневной факт (#87)
- Детектор нормы и сигналы на `brief_daily`: каркас `norm/` и шаг детектора (Story 4.0) (#95); сигналы по заказам и выручке с UNKNOWN-категорией (Story 4.1) (#100); аномалии на `/brief` с блоком «что проверить» (Story 4.3) (#106)
- Ранжирование сигналов по деньгам под риском с детерминированным tie-break (#102)
- Репетиционный стенд релиза на VPS: override `infra/compose.rehearsal.yaml` (проект `proxima-rehearsal`, postgres на `127.0.0.1:5434`, изоляция от боевого контура) и `tools/rehearsal_run.sh` (`init → up → backfill → tail --live → steps → check → down`) (#111)

### Changed

- Гигиена M-01 в гейте: `webapp-lint` и `codegen-diff` в `make verify`, pre-commit hooks через `make install` (#85)
- **Порог тревоги: значение не задано (все три поля `null`), см. `detector/threshold.toml`** - обвязка конфигурации, фильтрации, payload, подписи `/brief` и verify-гейта готова (Stories 4.2/4.4, #104); значение, источник и дата ждут отдельного решения Mike после ретро-разметки
- Ретрай отправки алерта (`--retry 3 --retry-delay 5`, ретрайит сам curl) и крайний срок 06:30 в `TimeoutStartSec` утреннего юнита (PA-65) (#80)
- WB-токены и raw-артефакты монтируются в контейнер `collector` через compose `secrets:`/`volumes:`, runners переведены на контейнерные пути (#103)
- Живой WB разрешён только сервису `collector`: `WB_ALLOW_LIVE_NETWORK=1` в `environment:` `infra/compose.yaml` (AD-4) + гейт `make live-network` (`tools/verify_live_network.py` в `make verify`) (#110)
- Гейт цифр релиза §4 по правилу 08.09: W10 - сумма недели с копейками (`649|700860.50`), W35 - по дням (24-26.08 равны паре 31.08, 27-30.08 - последним наблюдениям); `rehearsal_run.sh check` реализует то же (#112, #116)

### Fixed

- KF-3: плавающий «московский день» - сдвиг часового пояса берётся только за час сэмплирования (#75)
- Follow-ups Story 3.1: окно хвоста `[today-6, today]`, log-and-skip для пропусков, drop-in PA-13; вызов заданий через `npm run <job>` (у образа коллектора нет ENTRYPOINT) (#90)
- Follow-ups Stories 3.2/3.3: guard по префиксу «один отчёт в сутки», реальные имена колонок CSV в `CSV_COLUMN_MAP` (#97)
- Follow-ups Story 4.1: сигнал и по выручке (не только заказы), знак оценки денег, UNKNOWN-категория отклонения (#102)
- Postgres-режим webapp: полоса метрик скрывается, когда провайдер данных не поддерживает метрики (раньше `getMetrics()` отдавал 500 на каждой странице) (#114)
- Webapp читает свой URI-секрет: `proxima_webapp_uri`/`_password` получают владельца `1001:1001` (uid образа webapp) в provision и `init` репетиции (#115)

### Docs

- Проба Story 3.0 (6 HTTP-запросов): факты async CSV Analytics - глубина 6 месяцев, 15 колонок - в `docs/state/API-FACTS.md` (#91)
- Runbook релиза M-01 сведён с `main` и сервером (15 правок, раздел «Сверка 08.09.2026»); эталоны W10/W35 записаны в `API-FACTS.md`; исполнитель - Claude по D7 (#99, #113)
- Готовность к релизу 1.14: чек-лист v1 с блокерами B1-B6 (#93), ревизия v2 с блокерами B1-B10 и результатом репетиции (#113)
- Трек D35: решение о приоритете сбора данных и репетиции (#108); факты репетиции 08.09 и эталон W10 с копейками в `API-FACTS.md` (#112); правило гейта W35 по дням в runbook §4 и `API-FACTS.md` (#116)
- Runbook 1.14: webapp в postgres-режиме для задачи №1 (D01, диагностика 21.09 - `WEBAPP_DATA_MODE=postgres` в §1.1); §2 - webapp через overlay `infra/webapp.staging.compose.yaml` со снятием ручного контейнера `proxima-webapp-staging` (конфликт порта 3000, HANDOFF 09.09)
