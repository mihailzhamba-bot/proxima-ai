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

### F4. Блокеры для завершения spike (нужен Mike)

1. WB READ tokens (Statistics/Analytics/Finance) для кабинета отсутствуют на машине: проверены `.env` обоих source worktrees (только LLM/DB/Plane ключи в `proxima-ai-manager`; в `torgstat-collector` только Torgstat session) и `.env*` по MILV - вхождений `WB_API_TOKEN`/`WB_TOKEN` нет.
2. Официальные XLSX-выгрузки из кабинета WB на диске отсутствуют: все найденные XLSX по кабинету - Torgstat-экспорты.

До передачи токенов и хотя бы одной официальной выгрузки API-нога spike (наблюдаемые endpoints, поля, rate-limit заголовки) и XLSX-нога (структура официального экспорта, наличие daily grain) остаются pending.

## Статус

| Нога spike | Статус |
|------------|--------|
| Supporting source (Torgstat exports): структура, grain, manifest+contract | PASS 2026-08-12 |
| Official WB API: 3 ответа, endpoints, limits | Pending - токены у Mike |
| Official WB manual XLSX: структура, daily grain | Pending - выгрузка у Mike |
