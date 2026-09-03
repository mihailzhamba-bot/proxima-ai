/* eslint-disable */
// AUTO-GENERATED from contracts/*.schema.json by `make codegen` - DO NOT EDIT.
export interface CabinetDailyV1 {
  schema_version: 1;
  tenant_id: string;
  /**
   * Moscow calendar day of the WB `date` field (AD-7, mskDay).
   */
  calendar_day: string;
  /**
   * WB Statistics `orders` rows for the day by `date`, excluding `isCancel` (glossary: Заказы).
   */
  orders_count: number;
  cancelled_count: number;
  /**
   * `sales` rows with saleID on `S` for the day (glossary: Продажи).
   */
  sales_count: number;
  returns_count: number;
  /**
   * Money as a string with exactly two decimal places (AD-10); sum of finishedPrice over `S` sales.
   */
  revenue_rub: string;
  /**
   * Money as a string with exactly two decimal places (AD-10).
   */
  forpay_rub: string;
  /**
   * Evidence pointers (AD-1): content_sha256 of the raw artifacts the day was folded from; never empty.
   *
   * @minItems 1
   */
  source_refs: [string, ...string[]];
}

