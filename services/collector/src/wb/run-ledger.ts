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

export class RunLedgerError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'RunLedgerError';
  }
}

function nullableProvenance(value: string | undefined): string | null {
  return value === '' || value === undefined ? null : value;
}

export class RunLedger {
  constructor(private readonly pool: Pool) {}

  private async connect(tenantId: string): Promise<PoolClient> {
    const client = await this.pool.connect();
    try {
      await client.query("SELECT set_config('proxima.tenant_id', $1, false)", [tenantId]);
      return client;
    } catch (error) {
      client.release(error as Error);
      throw error;
    }
  }

  /** A pooled session must never retain its preceding run's tenant GUC. */
  private async release(client: PoolClient): Promise<void> {
    try {
      await client.query('RESET proxima.tenant_id');
      client.release();
    } catch (error) {
      client.release(error as Error);
      throw error;
    }
  }

  async open(input: RunLedgerInput): Promise<string> {
    const runId = randomUUID();
    const client = await this.connect(input.tenantId);
    try {
      await client.query(
        'INSERT INTO collector_runs (run_id, tenant_id, kind, status, git_sha, image_id, notes) VALUES ($1, $2, $3, $4, $5, $6, $7)',
        [runId, input.tenantId, input.kind, 'RUNNING', nullableProvenance(input.gitSha), nullableProvenance(input.imageId), input.notes ?? null],
      );
      logRunEvent('running', runId, input.tenantId);
      return runId;
    } finally { await this.release(client); }
  }

  async lastFullDay(tenantId: string): Promise<string | null> {
    const client = await this.connect(tenantId);
    try {
      const result = await client.query<{ last_full_day: string | null }>(
        'SELECT last_full_day::text FROM data_status_current WHERE tenant_id = $1',
        [tenantId],
      );
      return result.rows[0]?.last_full_day ?? null;
    } finally { await this.release(client); }
  }

  async succeed(tenantId: string, runId: string, work?: (client: PoolClient) => Promise<void>): Promise<void> {
    const client = await this.connect(tenantId);
    try {
      await client.query('BEGIN');
      await work?.(client);
      const result = await client.query("UPDATE collector_runs SET status = 'SUCCEEDED', finished_at = CURRENT_TIMESTAMP WHERE run_id = $1 AND status = 'RUNNING'", [runId]);
      if (result.rowCount !== 1) {
        throw new RunLedgerError(`cannot mark run ${runId} SUCCEEDED: expected one RUNNING row visible to tenant ${tenantId}, updated ${result.rowCount ?? 0}`);
      }
      await client.query('COMMIT');
      logRunEvent('succeeded', runId, tenantId);
    } catch (error) {
      await client.query('ROLLBACK').catch(() => undefined);
      throw error;
    } finally { await this.release(client); }
  }

  /** `notes` (optional) records why - e.g. the funnel coverage summary; the row keeps its existing notes otherwise. */
  async fail(tenantId: string, runId: string, notes?: string): Promise<void> {
    const client = await this.connect(tenantId);
    try {
      const result = await client.query(
        "UPDATE collector_runs SET status = 'FAILED', finished_at = CURRENT_TIMESTAMP, notes = COALESCE($2, notes) WHERE run_id = $1 AND status = 'RUNNING'",
        [runId, notes ?? null],
      );
      if (result.rowCount !== 1) {
        throw new RunLedgerError(`cannot mark run ${runId} FAILED: expected one RUNNING row visible to tenant ${tenantId}, updated ${result.rowCount ?? 0}`);
      }
      logRunEvent('failed', runId, tenantId);
    } finally { await this.release(client); }
  }
}
