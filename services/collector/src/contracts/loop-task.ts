/* eslint-disable */
// AUTO-GENERATED from contracts/*.schema.json by `make codegen` - DO NOT EDIT.
export interface LoopTaskV1 {
  schema_version: 1;
  task_id: string;
  tenant_id: string;
  decision_id: string;
  run_id: string;
  assignee_id: string;
  action: string;
  due_at: string;
  expected_outcome: string;
  horizon_days: number;
  created_at: string;
}

