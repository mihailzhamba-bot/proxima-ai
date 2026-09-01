/* eslint-disable */
// AUTO-GENERATED from contracts/*.schema.json by `make codegen` - DO NOT EDIT.
export interface CabinetDailyV1 {
  schema_version: 1;
  day: string;
  orders: number;
  revenue: string;
  /**
   * @minItems 1
   */
  source_refs: [string, ...string[]];
}
