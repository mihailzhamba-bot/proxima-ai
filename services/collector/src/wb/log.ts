/** Small JSON logger for run lifecycle events. Values deliberately exclude URLs,
 * request bodies, response bodies and credentials; those live only in CAS. */
export function logRunEvent(event: 'running' | 'succeeded' | 'failed', runId: string, tenantId: string): void {
  process.stdout.write(`${JSON.stringify({ event: `run-ledger:${event}`, run_id: runId, tenant_id: tenantId, at: new Date().toISOString() })}\n`);
}
