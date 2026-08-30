# Data Spike - 2026-08-12

Первый контакт архитектуры с реальными данными пилотного кабинета. Только метаданные и структура; business values и raw bytes в Git не попадают (правило STATE.md Todos).

## Что проверено

Source worktree `torgstat-collector` (read-only, не мутировался): `data/raw/wb/store_9725/` = ИП Богатова, бренд Belle robe. 11 датасетов Torgstat-экспортов WB-данных, покрытие до 2026-08-02: abc_goods, adv_daily, adv_items, dashboard_goods, geo, plan, pnl, reports_summary, sales_dynamics, stocks, supplies.

## Findings

### F1. Torgstat-экспорты не дают daily grain (ломает исходный DATA-07)

- `sales_dynamics`: строки SKU x метрика, колонки агрегированы по НЕДЕЛЯМ (`29.06 – 05.07`, `06.07 – 12.07`, ...), 5254 x 14.
- `dashboard_goods`: SKU-агрегаты за весь период выгрузки, 311 x 103.
- `stocks`: point-in-time snapshot по размер/баркод, 16039 x 32.

Сверка `cabinet + SKU + calendar_day` против этих экспортов невозможна. Следствие: daily grain для reconciliation обязан приходить из official WB API и/или официального XLSX кабинета. DATA-07 переформулирован (см. REQUIREMENTS.md): canonical = official WB API, supporting в M1 = official manual XLSX; Torgstat supporting отложен до M2.

### F2. Две разные семантики order_count внутри одного Torgstat-экспорта

Метрики в `sales_dynamics` различают `Заказы (из ленты в API)` и `Заказы (из отчета по воронке)` - Torgstat сам показывает, что WB отдаёт разные order counts разными каналами. Подтверждает PITFALLS.md Pitfall 6 на реальных данных: MetricAuthority (DATA-06) обязан пинить exact endpoint + field + status filter.

### F3. Контракт source-artifact v1 прошёл валидацию против реального файла

- Файл: `wb__ип_богатова__sales_dynamics__2026-07-04__2026-08-02__2026-08-02T07-33-40.xlsx`, 2 981 464 bytes.
- SHA-256: `55047ff0c2d7611783be34b368e40060dc2906b5a04e999f97e265c97a01058e`.
- Manifest построен по реальным метаданным (tenant `bogatova-belle-robe`, source `torgstat_supporting`, retrieval_mode `supporting_import`, locator `artifact://sha256/...`) и валидирован `Draft202012Validator` + `FormatChecker`: PASS, 0 errors.

### F5. API-нога закрыта тестовым токеном (кабинет Амировой, 2026-08-12)

Один JWT-токен покрыл все три READ API. Наблюдения (только статусы, заголовки, имена полей; business values не читались в docs):

- **Срок жизни токена**: `exp` = 2027-02-01, выдан ~на 180 дней, флаг `t=false` (боевой). Закрывает вопрос D11 по expiry: rotation cadence должен быть короче 180 дней.
- **Один токен = все scope.** SRC-02 требует три отдельных least-privilege SecretRef - при создании боевых токенов на Phase 4 выпускать 3 токена с раздельными scope (Статистика / Аналитика / Финансы), не один общий.

| API | Вызов | HTTP | Наблюдаемый rate limit | Grain |
|-----|-------|------|------------------------|-------|
| Statistics | `GET statistics-api.wildberries.ru/api/v1/supplier/orders?dateFrom=...&flag=0` | 200 | `x-ratelimit-remaining: 9` после 1 вызова | Order-level строки: `date`, `lastChangeDate`, `srid`, `nmId`, `isCancel` - **daily grain есть**, агрегируется до cabinet+SKU+day |
| Analytics | `POST seller-analytics-api.wildberries.ru/api/analytics/v3/sales-funnel/products` | 200 | `x-ratelimit-remaining: 2` после 1 вызова (лимит 3/мин, интервал 20s) | Агрегат за период (`selected`/`past`/`comparison`); daily только через `sales-funnel/products/history`, макс 7 дней |
| Finance | `GET statistics-api.wildberries.ru/api/v5/supplier/reportDetailByPeriod?dateFrom=...&dateTo=...&rrdid=0` | 200 | `x-ratelimit-remaining: 9` после 1 вызова | Settlement-строки с `date_from`/`date_to` периодами + `order_dt` - подтверждает PITFALLS: Finance разворачивать в дни через `order_dt`/календарь |

- **Семантика Statistics подтвердила Pitfall 6 на живом API**: при `flag=0` параметр `dateFrom` фильтрует по `lastChangeDate`, не по дате заказа - запрос от 2026-08-10 вернул заказы с 2026-06-23. MetricAuthority обязан пинить `flag` и поле даты.
- Данные закрывают половину gap C9 (endpoints + наблюдаемые limits); ADR Phase 4 дополнить официальными лимитами из dev.wildberries.ru.
- Повторить эти 3 вызова на боевом токене кабинета Богатовой при получении (ожидание: идентичная структура).

### F4. Блокеры для завершения spike (нужен Mike)

1. WB READ tokens (Statistics/Analytics/Finance) для кабинета отсутствуют на машине: проверены `.env` обоих source worktrees (только LLM/DB/Plane ключи в `proxima-ai-manager`; в `torgstat-collector` только Torgstat session) и `.env*` по MILV - вхождений `WB_API_TOKEN`/`WB_TOKEN` нет.
2. Официальные XLSX-выгрузки из кабинета WB на диске отсутствуют: все найденные XLSX по кабинету - Torgstat-экспорты.

До передачи токенов и хотя бы одной официальной выгрузки API-нога spike (наблюдаемые endpoints, поля, rate-limit заголовки) и XLSX-нога (структура официального экспорта, наличие daily grain) остаются pending.

## Статус

| Нога spike | Статус |
|------------|--------|
| Supporting source (Torgstat exports): структура, grain, manifest+contract | PASS 2026-08-12 |
| Official WB API: 3 ответа, endpoints, limits | PASS 2026-08-12 (тестовый токен кабинета Амировой; повторить на токене Богатовой) |
| Official WB manual XLSX: структура, daily grain | Pending - выгрузка у Mike |
