# WB API fixtures (обезличенные)

Малые обезличенные фикстуры ответов WB API для тестов collector (AD-4, Story 1.0).
Источник - полные ответы, снятые 30.08.2026 (UTC-метка в имени исходного файла); полные
файлы живут вне git (VPS `~/signal-inputs/fixtures/wb-api/` + S3), сюда коммитится
только обезличенный срез ≤ 200 КБ.

Инструмент: `tools/anonymize_fixture.py`, seed **42** (детерминированный вывод).

| Фикстура | Исходный полный ответ (30.08.2026) | Команда генерации (из корня репо) |
|---|---|---|
| `statistics/orders/sample.json` (295 строк, 14 дней 2026-08-17..30) | `statistics/supplier-orders/20260830T060041Z__dateFrom-2023-01-01_flag-0.json` | `python3 tools/anonymize_fixture.py <src> statistics/orders/sample.json --seed 42 --limit-days 14 --max-bytes 200000` |
| `statistics/sales/sample.json` (285 строк, 14 дней 2026-08-17..30) | `statistics/supplier-sales/20260830T055939Z__dateFrom-2023-01-01_flag-0.json` | `python3 tools/anonymize_fixture.py <src> statistics/sales/sample.json --seed 42 --limit-days 14 --max-bytes 200000` |
| `analytics/sales_funnel_v3_history/sample.json` (3 nmId, 7 дней) | `analytics/sales-funnel-v3-history/20260830T141424Z__nmIDs-3_period-2026-08-24_2026-08-30_day.json` (HTTP 200) | `python3 tools/anonymize_fixture.py <src> analytics/sales_funnel_v3_history/sample.json --seed 42` |
| `analytics/nm_report_downloads/sample.json` (список отчётов) | `analytics/nm-report-downloads/20260830T060719Z__list.json` | `python3 tools/anonymize_fixture.py <src> analytics/nm_report_downloads/sample.json --seed 42` |

Что обезличено (структура и даты сохранены, `date`/`lastChangeDate` не меняются):

- `nmId` -> перенумерация 12345001, 12345002, ... (детерминированная на файл);
- `supplierArticle`/`vendorCode` -> `sku-<n>`, `subject`/`subjectName` -> `subject-<n>`,
  `brand`/`brandName` -> `brand-<n>`, `title` -> `title-<n>`;
- денежные поля (`totalPrice`, `priceWithDisc`, `finishedPrice`, `forPay`,
  `paymentSaleAmount`, `orderSum`, `buyoutSum`) умножены на один случайный
  коэффициент 0.8-1.2 на файл (seed 42), округление до 2 знаков;
- `srid`/`saleID`/`gNumber`/`sticker`/`barcode` -> синтетические с сохранением
  уникальности и префикса S/R у `saleID`; UUID (`id`) -> синтетические;
- география (`regionName`, `oblastOkrugName`, `countryName`, `warehouseName`) ->
  фиксированные плейсхолдеры.

Проверка на токены перед коммитом: `grep -rlE 'eyJ[A-Za-z0-9_-]{40,}' .` - пусто.
