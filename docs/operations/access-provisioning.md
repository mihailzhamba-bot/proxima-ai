# Выдача доступа человеку

Кому: владельцу проекта, когда в работу входит второй человек. Обновлено 03.09.2026. Значения секретов в этом документе не приводятся - только имена файлов и переменных.

## Что выдаётся сразу

| Доступ | Как | Ограничение |
|---|---|---|
| GitHub `mihailzhamba-bot/proxima-ai` | приглашение в репозиторий | ветки и PR; мерж делает владелец |
| Jira, проекты PA и PMM | приглашение | комментарии и просмотр; статусы историй двигает конвейер |
| Кабинет WB | доступ на просмотр в личном кабинете продавца | без раздела «Доступ к API», без выпуска токенов |
| Обезличенные фикстуры | уже в репозитории (`services/collector/tests/fixtures/wb-api/`) | до 200 КБ на файл, деньги искажены коэффициентом |
| Полные фикстуры | копирование с сервера, см. ниже | только каталог `fixtures/wb-api/` |

## Копирование фикстур: где проходит опасная граница

Файлы токенов лежат на **один уровень выше** фикстур. Команда без сегмента `fixtures/` захватит их.

```bash
# безопасно, без 409 МБ финансового отчёта:
scp -r proxima:signal-inputs/fixtures/wb-api/statistics/supplier-orders ./fixtures/
scp -r proxima:signal-inputs/fixtures/wb-api/statistics/supplier-sales  ./fixtures/
scp -r proxima:signal-inputs/fixtures/wb-api/analytics                  ./fixtures/

# нельзя: scp -r proxima:signal-inputs/ …   ← рядом лежат wb_*_token и telegram_bot_token
```

Полные фикстуры в git не попадают (каталог в списке игнорируемых). В репозиторий идёт только обезличенное через `tools/anonymize_fixture.py`.

## Доступ к серверу

Не выдаётся по умолчанию. Если решение принято:

1. Публичный ключ человека добавляется **точечной строкой** в `authorized_keys` пользователя `proxima-admin`. Никогда не через `infra/bootstrap/bootstrap-vps.sh` - он перезаписывает файл целиком.
2. В `~/.ssh/config` человека: алиасы `proxima` (оболочка) и `proxima-db` (туннель на порт 5433). Обязательно `IdentitiesOnly yes` - на сервере лимит трёх попыток аутентификации; на macOS ещё `UseKeychain yes`.
3. Проверка одной командой: `bash infra/ssh-doctor` (только чтение).

Пользователь всегда `proxima-admin`; root заблокирован навсегда. Сервер для всех, кроме владельца, - только чтение.

## Доступ к боевой базе на чтение

Роль `proxima_analyst` - отдельная LOGIN-роль без наследования и членства в групповых ролях. Она получает только `CONNECT`, `USAGE` и прямой `SELECT` на все существующие и будущие таблицы и представления `public`; `default_transaction_read_only` и таймауты дополнительно ограничивают сессию. Скрипт не создаёт RLS-политик: до миграции 011 чтение не фильтруется, после 011 таблицы с политиками возвращают роли ноль строк без установленного `proxima.tenant_id`.

### Состав грантов

| Данные | Объекты | Условие видимости |
|---|---|---|
| Наблюдения orders/sales | `stg_wb_orders_obs`, `stg_wb_sales_obs`, `stg_wb_orders_latest`, `stg_wb_sales_latest` | через RLS по `tenant_id`; без `set_config` - без строк |
| Дневные факты кабинета | `fact_cabinet_daily`, `fact_cabinet_daily_current` | через RLS по `tenant_id`; без `set_config` - без строк |
| Факты по артикулам | `fact_nm_daily`, `fact_nm_daily_current`, `dim_nm_subject`, `dim_nm_subject_current` | через RLS по `tenant_id`; без `set_config` - без строк |
| Воронка | `stg_wb_funnel_obs`, `stg_wb_funnel_latest`, `fact_funnel_daily`, `fact_funnel_daily_current` | через RLS по `tenant_id`; без `set_config` - без строк |
| Норма и сводка | `norm_daily`, `norm_daily_current`, `brief_daily`, `brief_current` | через RLS по `tenant_id`; без `set_config` - без строк |
| Реестр прогонов и сырья | `collector_runs`, `collector_run_inputs`, `wb_raw_artifacts` | через RLS по `tenant_id`; без `set_config` - без строк |
| Статус данных | `data_status_current` | security-invoker view над RLS-таблицами; без `set_config` - без строк |
| Справочники и ledger | `tenants`, `schema_migrations` | без tenant-фильтра; только `SELECT` |

Технически роль получает `SELECT ON ALL TABLES IN SCHEMA public`, поэтому видит также прочие существующие и будущие объекты схемы. Это необходимо для `security_invoker`-представлений: грант на view не заменяет права на базовые таблицы. Прав `INSERT`, `UPDATE`, `DELETE`, `TRUNCATE`, `CREATE`, выполнения функций или доступа к sequence роль не получает.

### Процедура выдачи

1. После миграций релиза 1.14 и `provision-runtime-roles.sh` Mike на сервере выполняет `sudo bash infra/bootstrap/provision-analyst-role.sh`.
2. Скрипт печатает только пути `/etc/proxima-ai/secrets/proxima_analyst_password` и `/etc/proxima-ai/secrets/proxima_analyst_uri`. Mike читает URI-файл и передаёт его Владиславу вне чата; значение не выводится в логи или переписку.
3. Через туннель `ssh -N proxima-db` Владислав проверяет `psql "$DATABASE_URI" -c "SELECT 1"`; попытка `INSERT` должна завершиться `permission denied`.
4. После миграции 011 первый statement каждой сессии: `SELECT set_config('proxima.tenant_id', 'amirova-test', false)`. Без него защищённые RLS объекты возвращают ноль строк, а не ошибку доступа.
5. Строка о выдаче с датой и владельцем записывается в `docs/state/INVENTORY.md`.

Как человек делает запрос:

```bash
ssh -N proxima-db                       # держать открытым; снимать только ssh -O cancel -L …
export DATABASE_URI="$(< путь_к_файлу)" # значение не выводить в терминал
psql "$DATABASE_URI" -c "SELECT count(*) FROM collector_runs;"
```

После включения защиты по кабинетам (миграция 011 и далее) первым запросом сессии обязателен `SELECT set_config('proxima.tenant_id', 'amirova-test', false)` - третий аргумент `false` означает «на сессию», а не «на транзакцию». Как отличать причины пустого ответа: отказ в правах означает отсутствие гранта; ноль строк на непустой таблице означает, что не установлен идентификатор кабинета; проверка - `SELECT current_setting('proxima.tenant_id', true)`.

## Что не выдаётся никогда

Роль-владелец базы и её строка подключения; пароль диагностической роли; строка подключения песочницы (она про тестовую базу); любые токены WB и Telegram; ключ шифрования бэкапов; ключи и учётные данные S3/объектного хранилища; права `sudo` на сервере; права записи где-либо; ssh-доступ к серверу.

## Отзыв доступа

Удалить строку из `authorized_keys`; отозвать роль базы (`REVOKE CONNECT`, затем `DROP ROLE` после проверки владений); убрать из GitHub и Jira; попросить удалить локальные копии фикстур. Если был доступ к токенам - ротация по процедуре из `docs/operations/incident-runbook.md`.
