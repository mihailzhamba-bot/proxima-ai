# Phase 3 Context - PostgreSQL Quality & Atomic Releases

## Locked decisions

- **Additive-only миграции (закрытие B6, 2026-08-25):** миграции ordered + immutable + append-only; ledger `schema_migrations` с normalized-self-v1 checksum остаётся единственной записью применения; исправление ошибки схемы = новая миграция, никогда не правка/откат применённой; `DROP TABLE`, `DROP COLUMN`, переписывающие `ALTER` и изменения уже применённых файлов запрещены verifier'ом. До сих пор соблюдалось де-факто с 001; фиксируется как доктрина.
- Phase 3 наследует и расширяет slice-миграции Phase 2 (`001_bootstrap` .. `006_raw_artifact_headers`); первая новая миграция - `007_`. Существующие таблицы (`tenants`, `source_artifacts`, `artifact_manifests`, `intake_attempts`, `dim_product`, `dim_warehouse_map`, `business_signal_*`, `wb_analytics_*`, `stg_wb_nm_report_rows`) не переписываются и не переименовываются.
- **Единый lineage-контракт поверх двух семей evidence:** (а) файловые артефакты ручного XLSX-пути (`source_artifacts`/`artifact_manifests`/`intake_attempts`, 002, путь спит после отмены 02-02) и (б) API-evidence WB-коллектора (`raw_wb_analytics_responses.content_sha256` + `wb_analytics_report_tasks`, 003/005, живой путь). Обе.anchor'ятся SHA-256 контента; каждый public fact обязан разрешаться до sha256 + manifest/record + parser/schema version + attempt по одной и той же форме ссылки.
- Три домена релизов - **operational, inventory, financial** - с независимыми release pointer'ами; продвижение pointer'а и promotion фактов - ровно одна транзакция; никакого частичного продвижения.
- **Last-known-good семантика:** failed/partial/stale/conflicting/schema-drift attempt оставляет pointer на LKG, но виден отдельной текущей записью failure; failure не подменяет состояние business health (DATA-04).
- **PostgreSQL dev/test-цикл без локального Docker** (решение Mike 2026-08-16): migration roundtrip и crash-injection тесты гоняются на disposable local PostgreSQL 16 (homebrew `initdb`-паттерн, доказан 02-01A evidence 2026-08-13 на pg 16.14; директория вне Git, уничтожается после прогона). CI сохраняет существующий паттерн skip Docker-dependent интеграционного теста. VPS Phase 3-тестами не трогается (business data guardrail до Phase 7).
- **Четыре runtime-роли** (migration owner, source publisher, release publisher, read-only Data Health) создаются как PostgreSQL roles в миграциях 007+; adversarial-тесты (cross-tenant, forbidden-write, crash-injection) обязательны и fail-closed.
- Tenant-изоляция и `Europe/Moscow` - в каждом новом объекте схемы; первый нормализованный факт - `order_count` на grain tenant + nm_id + calendar_day, но semantic authority/reconciliation - Phase 5 (DATA-06..08); Phase 3 строит машину фактов/качества/релизов без reconciliation-логики.
- **Новых источников нет:** Phase 3 потребляет уже застейдженные данные (`stg_wb_nm_report_rows`, 1 220 живых строк 2026-08-25) и synthetic structural fixtures; новых WB endpoints, токенов и внешних входов не появляется.
- Критическая фаза: каждый план завершается clean implementation commit + root `make verify` PASS + CI PASS + independent cross-model review **0 blocker / 0 warning**.

## Inherited schema surface (вход)

| Семья | Таблицы | Связь lineage |
|---|---|---|
| Служебные | `schema_migrations`, `tenants` | - |
| Файловая evidence | `source_artifacts`, `artifact_manifests`, `intake_attempts` | artifact_id → content_sha256 |
| Конфиг | `dim_product`, `dim_warehouse_map` | tenant + effective_from версионность |
| Business-signal | `business_signal_runs`, `business_signal_raw_artifacts` | run → raw artifact sha256 |
| WB Analytics API | `wb_analytics_report_tasks`, `wb_analytics_quota_events`, `raw_wb_analytics_responses`, `stg_wb_nm_report_rows` | stg row → task → raw response content_sha256 |

## Verification boundary

- `tools/verify_migrations.py` расширяется enforced-проверками additive-only (запрет деструктивных операций в новых миграциях) и остаётся fail-closed.
- Migration roundtrip на real PostgreSQL 16 - обязательная часть `make verify`-цикла через disposable-local-pg скрипт (create → apply all → idempotent re-apply check → destroy); скрипт не требует Docker и не трогает VPS.
- Crash-injection продвигается из TS-уровня (intake 02-01) на уровень PostgreSQL-транзакций promotion: отказ после каждой границы записи → полный откат → retry даёт ровно один консистентный набор и LKG не тронут.
