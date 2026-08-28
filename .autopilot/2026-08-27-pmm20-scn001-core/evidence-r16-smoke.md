# Evidence R16 — smoke реестра колонок против реального staging payload

Read-only прогон `python -m proxima_control_plane.detectors.scn001.smoke` через SSH-туннель
на staging VPS. Транскрипт зафиксирован вручную из вывода прогона: типы значений колонок
в этом транскрипте не сохранены, факты ниже — только наличие/отсутствие ключей.

- Дата прогона: 2026-08-28
- Task: `f1b8892a-4e8a-46df-81eb-c1dae58b88a5` (lifecycle DOWNLOADED)
- Row: 1

```
SMOKE R16: payload column registry vs real staging row (read-only, one row)
row: task_id=f1b8892a-4e8a-46df-81eb-c1dae58b88a5 row_number=1
  field=sku            column='nmID'         PRESENT
  field=date           column='dt'           PRESENT
  field=orders         column='ordersCount'  PRESENT
  field=open_card      column='openCardCount' PRESENT
  field=orders_sum_rub column='ordersSumRub' PRESENT
  field=buyouts        column='buyoutsCount' PRESENT
payload keys not in registry: ['addToCartConversion', 'addToCartCount', 'addToWishlist', 'buyoutPercent', 'buyoutsSumRub', 'cancelCount', 'cancelSumRub', 'cartToOrderConversion', 'currency']
SMOKE R16: REGISTRY STATUS OK
```

Вывод: все шесть колонок `COLUMN_MAP` присутствуют в реальном payload; имена в реестре
верифицированы (UNKNOWN снят). Внесистемные ключи payload вне реестра перечислены выше —
в канонический вход не попадают.
