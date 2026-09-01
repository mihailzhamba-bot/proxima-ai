import { randomUUID } from 'node:crypto';

import type { Pool, PoolClient } from 'pg';

import { logRunEvent } from './log.js';

export type CollectorRunKind = 'collect' | 'backfill' | 'funnel_v3' | 'funnel_csv_download' | 'funnel_csv_promote' | 'norm' | 'brief';
export type CollectorRunStatus = 'RUNNING' | 'SUCCEEDED' | 'FAILED';

export interface RunLedgerInput {
  tenantId: string;
  kind: CollectorRunKind;
  gitSha?: string;
  imageId?: string;
  notes?: string;
}

export class RunLedger {
  constructor(private readonly pool: Pool) {}

  private async connect(tenantId: string): Promise<PoolClient> {
    const client = await this.pool.connect();
    try {
      await client.query("SELECT set_config('proxima.tenant_id', $1, false)", [tenantId]);
      return client;
    } catch (error) {
      client.release();
      throw error;
    }
  }

  async open(input: RunLedgerInput): Promise<string> {
    const runId = randomUUID();
    const client = await this.connect(input.tenantId);
    try {
      await client.query(
        'INSERT INTO collector_runs (run_id, tenant_id, kind, status, git_sha, image_id, notes) VALUES ($1, $2, $3, $4, $5, $6, $7)',
        [runId, input.tenantId, input.kind, 'RUNNING', input.gitSha ?? null, input.imageId ?? null, input.notes ?? null],
      );
      logRunEvent('running', runId, input.tenantId);
      return runId;
    } finally { client.release(); }
  }

  async succeed(tenantId: string, runId: string, work?: (client: PoolClient) => Promise<void>): Promise<void> {
    const client = await this.connect(tenantId);
    try {
      await client.query('BEGIN');
      await work?.(client);
      await client.query("UPDATE collector_runs SET status = 'SUCCEEDED', finished_at = CURRENT_TIMESTAMP WHERE run_id = $1 AND status = 'RUNNING'", [runId]);
      await client.query('COMMIT');
      logRunEvent('succeeded', runId, tenantId);
    } catch (error) {
      await client.query('ROLLBACK').catch(() => undefined);
      throw error;
    } finally { client.release(); }
  }

  async fail(tenantId: string, runId: string): Promise<void> {
    const client = await this.connect(tenantId);
    try {
      await client.query("UPDATE collector_runs SET status = 'FAILED', finished_at = CURRENT_TIMESTAMP WHERE run_id = $1 AND status = 'RUNNING'", [runId]);
      logRunEvent('failed', runId, tenantId);
    } finally { client.release(); }
  }
}
