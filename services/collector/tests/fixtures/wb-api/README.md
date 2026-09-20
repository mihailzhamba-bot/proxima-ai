# WB API fixtures (обезличенные)

Малые обезличенные фикстуры ответов WB API для тестов collector (AD-4, Story 1.0).
Источник - полные ответы, снятые 30.08.2026 (UTC-метка в имени исходного файла); полные
файлы живут вне git (VPS `~/signal-inputs/fixtures/wb-api/` + S3), сюда коммитится
только обезличенный срез ≤ 200 КБ.

Инструмент: `tools/anonymize_fixture.py` (fail-closed: неизвестный ключ роняет прогон).
Параметры: seed **42** (публичный, влияет только на структурную перенумерацию и UUID)
и **секретная соль** `--salt-file` (вне git: мак `~/.config/proxima/fixture-salt`,
0600) - от неё производятся денежный коэффициент и ремап времени. Тот же seed + та же
соль + тот же вход = идентичный вывод; без соли суммы и секунды невоспроизводимы и
необратимы.

| Фикстура | Исходный полный ответ (30.08.2026) | Команда генерации (из корня репо, `SALT=~/.config/proxima/fixture-salt`) |
|---|---|---|
| `statistics/orders/sample.json` (301 строка, 14 дней 2026-08-17..30) | `statistics/supplier-orders/20260830T060041Z__dateFrom-2023-01-01_flag-0.json` | `python3 tools/anonymize_fixture.py <src> statistics/orders/sample.json --seed 42 --salt-file $SALT --limit-days 14 --max-bytes 200000` |
| `statistics/sales/sample.json` (295 строк, 14 дней 2026-08-17..30) | `statistics/supplier-sales/20260830T055939Z__dateFrom-2023-01-01_flag-0.json` | `python3 tools/anonymize_fixture.py <src> statistics/sales/sample.json --seed 42 --salt-file $SALT --limit-days 14 --max-bytes 200000` |
| `analytics/sales_funnel_v3_history/sample.json` (3 nmId, 7 дней) | `analytics/sales-funnel-v3-history/20260830T141424Z__nmIDs-3_period-2026-08-24_2026-08-30_day.json` (HTTP 200) | `python3 tools/anonymize_fixture.py <src> analytics/sales_funnel_v3_history/sample.json --seed 42 --salt-file $SALT` |
| `analytics/nm_report_downloads/sample.json` (список отчётов) | `analytics/nm-report-downloads/20260830T060719Z__list.json` | `python3 tools/anonymize_fixture.py <src> analytics/nm_report_downloads/sample.json --seed 42 --salt-file $SALT` |

`analytics/nm_report_downloads/funnel_csv_promote.json` — synthetic-фикстура
Story 3.3: 3 обезличенных `nmID` × 7 дней, 21 строка payload в форме,
которую `complete_download` сохраняет из CSV. Структура по пробе 3.0
(08.09.2026), значения синтетические; сохранены все 15 колонок реального CSV.

Что обезличено (структура и календарные дни сохранены):

- `nmId` -> перенумерация 12345001, ...; `subjectId` -> 9001, ... (порядок первого вхождения);
- `supplierArticle`/`vendorCode` -> `sku-<n>`, `subject`/`subjectName` -> `subject-<n>`,
  `brand`/`brandName` -> `brand-<n>`, `title` -> `title-<n>`, `category` -> `category-<n>`;
- денежные поля (`totalPrice`, `priceWithDisc`, `finishedPrice`, `forPay`,
  `paymentSaleAmount`, `orderSum`, `buyoutSum`) умножены на один коэффициент
  0.8-1.2 на файл, производный от секретной соли (НЕ от публичного seed);
- временные метки (`date`, `lastChangeDate`, `cancelDate`, `createdAt`): дата
  сохранена, время суток ремапится секретной монотонной линейной картой на файл -
  порядок и равенство внутри дня сохранены, точные секунды уничтожены; сентинел
  `0001-01-01T00:00:00` и чистые даты (`2026-08-24`, `startDate`/`endDate`) не меняются;
- `srid`/`saleID`/`gNumber`/`sticker`/`barcode` -> синтетические с сохранением
  уникальности и префикса S/R у `saleID` (пустые строки проходят как есть);
  UUID (`id`) -> синтетические валидные v4;
- география (`regionName`, `oblastOkrugName`, `countryName`, `warehouseName`) ->
  фиксированные плейсхолдеры.

Оставлено как есть (осознанно, см. PASSTHROUGH_KEYS): флаги и enum'ы
(`isCancel`, `isSupply`, `isRealization`, `warehouseType`, `status`, `currency`,
`name`), `techSize`, `discountPercent`, `spp`, счётчики и конверсии воронки
(`openCount`, `cartCount`, `orderCount`, `buyoutCount`, `buyoutPercent`,
`addToCartConversion`, `cartToOrderConversion`, `addToWishlistCount`), `size`,
`startDate`/`endDate`. Без точных сумм, секунд и категорий они кабинет не
идентифицируют.

Ограничение: маппинги строятся на файл - `nmId: 12345001` в `orders` и в
`sales_funnel_v3_history` это разные реальные товары. Джойнить фикстуры разных
эндпоинтов по id нельзя; когда тестам понадобится связность между эндпоинтами,
инструменту нужен общий словарь маппинга (в бэклог).

Проверка перед коммитом: `grep -rlE 'eyJ[A-Za-z0-9_-]{40,}' .` - пусто; grep по
реальным брендам/категориям/городам кабинета - пусто.
