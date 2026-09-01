/* eslint-disable */
// AUTO-GENERATED from contracts/*.schema.json by `make codegen` - DO NOT EDIT.
/**
 * Planned inbound supply, phase A of the OQ-2 decision (PMM-34): manual AM entry. Status labels in Russian: PLAN=план, SHIPPED=отгружено, ACCEPTED=принято, CANCELLED=отменено; stored ASCII per DB convention. Phase B (PMM-36) automates ACCEPTED via WB Supplies API factDate - additive-compatible.
 */
export interface SupplyPlanV1 {
  schema_version: 1;
  supply_id: string;
  tenant_id: string;
  nm_id: string;
  quantity: number;
  order_date: string;
  expected_arrival_date: string;
  status: 'PLAN' | 'SHIPPED' | 'ACCEPTED' | 'CANCELLED';
  entered_by: string;
  entered_at: string;
}
