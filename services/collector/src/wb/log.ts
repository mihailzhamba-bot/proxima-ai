/** Small JSON logger for run lifecycle events. Values deliberately exclude URLs,
 * request bodies, response bodies and credentials; those live only in CAS. */
export function logRunEvent(event: 'running' | 'succeeded' | 'failed', runId: string, tenantId: string): void {
  process.stdout.write(`${JSON.stringify({ event: `run-ledger:${event}`, run_id: runId, tenant_id: tenantId, at: new Date().toISOString() })}\n`);
}

export interface RunStepEvent {
  level?: 'info' | 'warn' | 'error';
  run_id: string;
  tenant_id: string;
  kind: string;
  step: string;
  msg: string;
  /** Counts, codes and ids only - never payload, URLs or secrets. */
  [extra: string]: unknown;
}

/** One JSON line per job step in the spine Conventions shape
 * `{ts, level, run_id, tenant_id, kind, step, msg, ...}`. */
export function logRunStep(event: RunStepEvent): void {
  const { level = 'info', ...rest } = event;
  process.stdout.write(`${JSON.stringify({ ts: new Date().toISOString(), level, ...rest })}\n`);
}
