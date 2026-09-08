# Словарь данных

Составлен 03.09.2026 по миграциям `db/migrations/001`-`011` в `main` и по плану миграций `012`-`017` из `ARCHITECTURE-SPINE.md` (AD-14); 08.09.2026 добавлена реальная миграция `018` (AD-19, Story 4.0). Назначение: одно место, где видно, какая таблица зачем нужна, кто в неё пишет, кто читает и чем она удаляется. До этого сведения жили прозой внутри правил спайна и в AC историй.

## Три состояния схемы одновременно - читать внимательно

| Где | Версия | Что это значит |
|---|---|---|
| Боевая база на VPS | `schema_migrations` = 6 | Применены только `001`-`006`. RLS выключен, политик ноль, ролей спайна нет. Проверено 03.09 |
| Репозиторий `main` | `011` | Есть `007`-`011`, включая реестр прогонов и роли `proxima_job_*` |
| Рабочее дерево `sunfish` | `010` | Отстаёт от `main` на 22 коммита: `011`, контракты `norm`/`brief`/`cabinet-daily` локально не видны |
| План спайна | `016` | `012`-`016` пишутся историями 1.4, 1.6, 2.3, 2.4, 3.1 |

Практическое следствие: SQL, работающий на боевой базе, может не работать на локальном PostgreSQL после `make verify`, и наоборот. Первый релиз M-01 применяет `007`-`011` на боевой (порядок - AC Story 1.13).

## Правила, общие для всех таблиц лестницы

- `tenant_id text NOT NULL REFERENCES tenants` в каждой новой таблице; RLS включён; политика по образцу `USING (tenant_id = current_setting('proxima.tenant_id', true))` (AD-11, AD-13).
- Каждая строка фактов несёт `run_id` и удаляется вместе с прогоном; удаление транзитивно по `collector_run_inputs` (AD-3).
- Деньги: `numeric(14,2)` в базе, строка с двумя знаками в JSON (AD-10).
- Календарный день - по полю WB `date` в Europe/Moscow через единственный helper; `CURRENT_DATE` в `db/` запрещён (AD-7).
- Миграции additive-only, с self-checksum; ветка, мержащаяся второй, перенумеровывает свои файлы (AD-14).

## Существующие таблицы (миграции 001-011, 018)

| Таблица | Миграция | Назначение | Ключ | Пишет | Читает |
|---|---|---|---|---|---|
| `schema_migrations` | 001 | Реестр применённых миграций с контрольной суммой | `version` | `apply_migrations` | `verify_migrations.py`, регрессия WT-03 |
| `tenants` | 002 | Кабинет как единица платформы | `tenant_id` | вручную при подключении кабинета | всё |
| `source_artifacts` | 002 | Неизменяемое доказательство: хэш, размер, локатор | `artifact_id` (`artifact:sha256:…`) | приёмник артефактов | расчёты через SourceRef |
| `artifact_manifests` | 002 | Манифест артефакта (провенанс, время получения) | по артефакту | приёмник | бэкфилл, аудит |
| `intake_attempts` | 002 | Попытки приёма источника | `attempt_id` | приёмник | диагностика |
| `wb_analytics_report_tasks` | 003 | Задачи async-отчётов WB (create → status → file) | `task_id` | `wb_async_report.py` | промоушен воронки |
| `wb_analytics_quota_events` | 003 | События квоты 20 отчётов в сутки | по событию | `wb_async_report.py` | контроль квоты (OQ-10) |
| `raw_wb_analytics_responses` | 003 | Сырые ответы аналитики WB | по ответу | сборщик | разбор |
| `dim_product` | 004 | Справочник товаров кабинета | `nm_id` | сигнал остатков | детекторы |
| `dim_warehouse_map` | 004 | Карта складов | по складу | сигнал остатков | детекторы |
| `business_signal_runs` | 004 | Прогоны контура сигнала остатков (август, до лестницы) | `run_id` | `business-signal` | регрессия |
| `business_signal_raw_artifacts` | 004 | Артефакты того же контура | по артефакту | `business-signal` | аудит |
| `stg_wb_nm_report_rows` | 005 | Строки скачанного CSV отчёта | `(task_id, row_number)` | загрузка CSV | промоушен в воронку (Story 3.3) |
| `fact_attempt_runs` | 007 | Прогоны качества и происхождения фактов | `attempt_id` | конвейер фактов | `fact_order_counts` |
| `stg_quarantine_rows` | 007 | Строки, не прошедшие проверку качества | по строке | конвейер фактов | разбор качества |
| `fact_order_counts` | 007 | Заказы по товару и дню из CSV (`ordersCount`), lineage по `attempt_id` - **legacy** | `(attempt_id, tenant_id, nm_id, calendar_day)` | конвейер фактов веток `PA-03-02`/`pa41` (не приняты); писателя лестницы нет и не будет (AD-19) - разрез nmId лестницы см. `fact_nm_daily` (018) | три view 008 |
| `fact_lineage_records` | 007 | Происхождение факта | по факту | конвейер фактов | аудит |
| `quality_check_results` | 007 | Результаты проверок качества | по проверке | конвейер фактов | отчёт качества |
| `release_attempts`, `release_promoted_facts`, `domain_release_pointers` | 008 | Публикация доменов (операционный, запасы, финансы) | по попытке и указателю | релизный контур августа | три view `public_order_counts_*` |
| `dim_client_passport` | 010 | Паспорт кабинета: пороги, срок поставки, страховой запас, статус себестоимости, приоритетные категории, склады, выходные | `(tenant_id, effective_from)` | ручной ввод (CSV, позже форма) | M-04, M-06+ |
| `stg_supply_plan` | 010 | Плановые поставки: количество, дата заказа, ожидаемая приёмка, статус | `(tenant_id, supply_id)` | ручной ввод (фаза A) | OOS-детектор (CM-1) |
| `collector_runs` | 011 | **Реестр прогонов**: вид (`collect`, `backfill`, `funnel_v3`, `funnel_csv_*`, `norm`, `brief`), статус, `git_sha`, `image_id` | `run_id` | все job-ы | единственный источник статуса прогона (AD-3, AD-17) |
| `collector_run_inputs` | 011 | Связь «прогон использовал прогон» - основа транзитивного отката | `(tenant_id, run_id, input_run_id)` | job-ы | `delete_run.py` |
| `wb_raw_artifacts` | 011 | Артефакт ответа WB: эндпоинт, статус, заголовки, хэш, локатор, попытка | `artifact_id` | `recording-client` | бэкфилл, SourceRef, сверка |
| `dim_nm_subject` + `_current` | 018 (AD-19, Story 4.0) | Справочник nmId по данным WB: предмет (`subject_name` - категория аномалии), `category_name`, бренд, артикул, `last_change_at` и хэш выигравшего наблюдения; версия на прогон для каждого nmId из `stg_wb_orders_latest ∪ stg_wb_sales_latest` (максимальный `last_change_at`, при равенстве заказ раньше продажи, затем больший ключ); `_current` - последний SUCCEEDED прогон по `(tenant_id, nm_id)` | `(tenant_id, nm_id, run_id)` | `collect`, `backfill` (та же транзакция, что кабинетный ряд, до `fact_nm_daily`) | адаптер детектора 4.1 (`proxima_job_norm`); webapp гранта не имеет (AD-9) |
| `fact_nm_daily` + `_current` | 018 (AD-19, Story 4.0) | Дневной ряд по nmId: те же шесть колонок и формулы, что у `fact_cabinet_daily`, по `payload.nmId`; строка на каждый версионируемый день `[floor, run_day-1]` × каждый nmId справочника прогона, нули включительно (нет строки ⇔ день не версионирован, ноль ⇔ наблюдений нет; у нулевой строки `evidence_sha256` = артефакты прогона); сумма по nmId = кабинетный ряд - check `per_nm_sums_vs_cabinet` (одна JSON-строка лога `quality_check`, PASS/MISMATCH, порог `UNKNOWN` до OQ-7, прогон не блокирует); `_current` - последний SUCCEEDED прогон по `(tenant_id, calendar_day, nm_id)` | `(tenant_id, calendar_day, nm_id, run_id)` | `collect`, `backfill` (сразу после `aggregateCabinetDaily`, из тех же строк `_latest`) | детектор 4.1 (`proxima_job_norm`); webapp гранта не имеет (AD-9); удаляется `delete_run.py` каскадом от `collector_runs` |

Три view из 008 (`public_order_counts_operational`, `_inventory`, `_financial`) - публикация домена заказов с `security_invoker`.

## Планируемые таблицы лестницы (миграции 012-017)

| Таблица или view | Миграция | Назначение | Ключ | Пишет | Читает | Носитель |
|---|---|---|---|---|---|---|
| `stg_wb_orders_obs` | 012 | Наблюдения заказов с их `lastChangeDate` | `(tenant_id, srid, last_change_at)` | `collect`, `backfill` | агрегатор дня | Story 1.4 |
| `stg_wb_sales_obs` | 012 | Наблюдения продаж | `(tenant_id, sale_id, last_change_at)` | `collect`, `backfill` | агрегатор дня | Story 1.4 |
| `stg_wb_*_obs_latest` | 012 | Последнее наблюдение по ключу | view | - | агрегатор, сверка | Story 1.4 |
| `fact_cabinet_daily` | 013 | Дневной ряд кабинета: заказы, отмены, продажи, возвраты, выручка, доказательства | `(tenant_id, calendar_day, run_id)` | агрегатор | норма, сводка | Story 1.6 |
| `fact_cabinet_daily_current` | 013 | Версия дня из последнего успешного прогона | view | - | норма, сводка, теневой пересчёт | Story 1.6 |
| `data_status_current` | 013 | Последний полный день, время сбора, признак несвежести | view | - | экран `/brief`, алерты | Story 1.6 |
| `stg_wb_funnel_obs` | 017 | Наблюдения воронки по товару и дню, источник `v3` или `csv`; CSV: `nmID` → `nm_id`, `dt` → `calendar_day`, `openCardCount` → `open_card`, `addToCartCount` → `cart`, `ordersCount` → `orders`, `ordersSumRub` → `orders_sum_rub`, `buyoutsCount` → `buyouts`, `buyoutsSumRub` → `buyouts_sum_rub`; остальные колонки сохранены в `payload` | `(tenant_id, nm_id, calendar_day, source, canonical_sha256)` | `funnel_v3`, промоушен CSV | факты воронки | Story 3.1 |
| `fact_funnel_daily` + `_current` | 017 | Дневная воронка; `_current` предпочитает `csv` над `v3` | по товару и дню | промоушен | M-04, диагноз | Story 3.1, 3.3 |
| `norm_daily` + `_current` | 014 (норма) | Норма кабинета: окно, число дней выборки, значение, статус | `(tenant_id, evaluation_day, metric, run_id)` | `norm` | сводка, детекторы | Story 2.3 |
| `brief_daily` + `brief_current` | 015 | Материализованная сводка дня по контракту `brief`; с Story 4.1 `payload.signals[]` заполняет шаг детектора SCN-001 того же прогона (AD-19): сигналы по SKU и предмету из `fact_nm_daily_current`/`dim_nm_subject_current`, только при `status = ok`, отдельного носителя у сигналов нет. С Story 4.2 `signals[]` отсортированы по `rub_assessment.value_rub` по убыванию (при равенстве - глубже падение, затем SKU раньше предмета, затем `nm_id`), рост числом в `deviation_pct`/`detection_data` и никогда не сигнал; `payload.threshold {value, source, date}` - порог из конфигурации control-plane (`services/control-plane/src/proxima_control_plane/detector/threshold.toml`, переопределение `PROXIMA_THRESHOLD_CONFIG_FILE`), пишется при любом статусе и дублируется в `detection_data` каждого сигнала (`threshold_pct`, `threshold_source`, `threshold_date`); до Story 4.4 все три `null` = порог не применяется, после - кандидаты с падением на порог или глубже | по дню и прогону; `_current` - одна строка на кабинет | `brief` (+ шаг детектора) | экран `/brief` | Story 2.4, 4.1, 4.2 |
| роли и гранты | 016 | Донастройка ролей под новые таблицы | - | - | - | хвост Epic 2 |
| `decision_records` | после AD (Story 5.0) | Записи решений человека и исходов сверки | по решению | webapp (первая запись из UI) | сводка, метрики SM-4, SM-9 | Story 5.3 |

## Роли и права

| Роль | Тип | Права | Где заводится |
|---|---|---|---|
| `proxima_migration_owner`, `proxima_source_publisher`, `proxima_release_publisher`, `proxima_data_health_read` | групповые, без входа | приём источников, публикация, чтение здоровья данных | миграция 009 |
| `proxima_job_collector`, `proxima_job_norm`, `proxima_webapp_readonly`, `proxima_run_janitor` | групповые, без входа | сбор, расчёт нормы, чтение витрины, удаление по `run_id` | миграция 011 |
| `proxima_collector`, `proxima_norm`, `proxima_webapp`, `proxima_janitor`, `proxima_sandbox` | со входом | членство в группах выше; песочница видит только тестовую базу | `infra/bootstrap/provision-runtime-roles.sh` |
| `proxima_diagnostics` | со входом, только чтение | единственная действующая read-only роль на боевой; пароль под root, обёртка требует `sudo` | `infra/bootstrap/provision-postgres-diagnostics.sh` |
| роль аналитика | со входом, только чтение | чтение наблюдений, фактов, нормы, сводки и реестра артефактов для независимого пересчёта | ещё не заведена, Story 6.4 |

Проверка доступа: `permission denied` означает отсутствие гранта; ноль строк на непустой таблице означает, что не установлен `proxima.tenant_id`; проверяется через `SELECT current_setting('proxima.tenant_id', true)`.

## Что удаляется и когда

Прогон удаляется целиком: `tools/delete_run.py --tenant --run [--dry-run]` (инструмент пишет Story 1.7) снимает транзитивное замыкание по `collector_run_inputs`. Файлы артефактов в хранилище остаются. Записи решений человека при откате прогона фактов помечаются осиротевшими и не удаляются (решение AD из Story 5.0). Автоматического удаления по сроку нет: ретеншн отложен (AD-17), решение вместе с персональными данными - OQ-15.
