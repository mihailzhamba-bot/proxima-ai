import { Decimal } from 'decimal.js';
import type { Pool } from 'pg';

import type { ProductConfig, RawArtifactRecord, SignalCandidate, SignalRepository, SignalWindow, WarehouseMap } from './types.js';

export class PostgresSignalRepository implements SignalRepository {
  constructor(private readonly pool: Pool) {}

  async createRun(runId: string, tenantId: string, window: SignalWindow): Promise<void> {
    await this.pool.query('INSERT INTO business_signal_runs (run_id, tenant_id, status, window_from, window_to, timezone) VALUES ($1, $2, $3, $4, $5, $6)', [runId, tenantId, 'RUNNING', window.from, window.to, 'Europe/Moscow']);
  }

  async loadProductConfig(tenantId: string, asOf: string): Promise<ProductConfig[]> {
    const result = await this.pool.query<{ nm_id: string; internal_article: string; cogs_rub: string; lead_time_days: number; safety_buffer_days: number; effective_from: string }>(
      `SELECT DISTINCT ON (nm_id) nm_id::text, internal_article, cogs_rub::text, lead_time_days, safety_buffer_days, effective_from::text
       FROM dim_product WHERE tenant_id = $1 AND effective_from <= $2 ORDER BY nm_id, effective_from DESC`, [tenantId, asOf],
    );
    return result.rows.map((row) => ({ tenantId, nmId: BigInt(row.nm_id), internalArticle: row.internal_article, cogsRub: new Decimal(row.cogs_rub), leadTimeDays: row.lead_time_days, safetyBufferDays: row.safety_buffer_days, effectiveFrom: row.effective_from }));
  }

  async loadWarehouseMap(tenantId: string, asOf: string): Promise<WarehouseMap[]> {
    const result = await this.pool.query<{ sales_warehouse_name: string; stock_warehouse_name: string; canonical_warehouse: string; effective_from: string }>(
      `SELECT DISTINCT ON (sales_warehouse_name) sales_warehouse_name, stock_warehouse_name, canonical_warehouse, effective_from::text
       FROM dim_warehouse_map WHERE tenant_id = $1 AND effective_from <= $2 ORDER BY sales_warehouse_name, effective_from DESC`, [tenantId, asOf],
    );
    return result.rows.map((row) => ({ tenantId, salesWarehouseName: row.sales_warehouse_name, stockWarehouseName: row.stock_warehouse_name, canonicalWarehouse: row.canonical_warehouse, effectiveFrom: row.effective_from }));
  }

  async recordRawArtifact(record: RawArtifactRecord): Promise<void> {
    await this.pool.query(
      `INSERT INTO business_signal_raw_artifacts
       (raw_artifact_id, run_id, source, stage, page_sequence, endpoint_path, http_status, response_headers, content_sha256, content_size, object_locator, manifest_sha256, retrieved_at)
       VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13)`,
      [record.rawArtifactId, record.runId, record.source, record.stage, record.pageSequence, record.endpointPath, record.httpStatus, JSON.stringify(record.responseHeaders), record.contentSha256, record.contentSize, record.objectLocator, record.manifestSha256, record.retrievedAt],
    );
  }

  async completeRun(runId: string, status: 'NO_SIGNAL' | 'BLOCKED', reason: string): Promise<void> {
    await this.pool.query('UPDATE business_signal_runs SET status=$2, block_reason=$3, completed_at=CURRENT_TIMESTAMP WHERE run_id=$1 AND status=$4', [runId, status, reason, 'RUNNING']);
  }

  async markReady(runId: string, candidate: SignalCandidate): Promise<void> {
    await this.pool.query(
      `UPDATE business_signal_runs SET status='READY', selected_nm_id=$2, selected_internal_article=$3,
       selected_warehouse=$4, stock_quantity=$5, velocity_units_per_day=$6, days_cover=$7,
       threshold_days=$8, margin_per_unit_rub=$9, stock_as_of=$10, completed_at=CURRENT_TIMESTAMP
       WHERE run_id=$1 AND status='RUNNING'`,
      [runId, candidate.nmId.toString(), candidate.internalArticle, candidate.warehouse, candidate.stockQuantity, candidate.velocityUnitsPerDay.toFixed(6), candidate.daysCover, candidate.thresholdDays, candidate.marginPerUnitRub.toFixed(2), candidate.stockAsOf],
    );
  }

  async recordTelegramResult(runId: string, attemptedAt: Date, messageId: bigint | null): Promise<void> {
    await this.pool.query(
      `UPDATE business_signal_runs SET status=$2, telegram_attempted_at=$3, telegram_message_id=$4, completed_at=CURRENT_TIMESTAMP
       WHERE run_id=$1 AND status='READY'`,
      [runId, messageId === null ? 'SEND_FAILED' : 'SENT', attemptedAt, messageId?.toString() ?? null],
    );
  }
}
