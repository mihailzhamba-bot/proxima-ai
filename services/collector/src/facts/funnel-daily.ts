/**
 * Daily funnel versions (Story 3.1, AD-5): a run versions every product-day it
 * observed, copying the latest observation of that key from
 * `stg_wb_funnel_latest` (source `v3`) into `fact_funnel_daily`. The version
 * keeps the observation key and its evidence; runs whose observations fed the
 * versions become `collector_run_inputs` so the rollback closure (AD-3) holds.
 * Runs inside the SUCCEEDED transaction of `RunLedger.succeed`.
 */
import type { PoolClient } from 'pg';

import { FUNNEL_SOURCE, type FunnelSource } from '../wb/funnel-v3.js';

export interface FunnelProductDay {
  readonly nmId: number;
  readonly calendarDay: string;
}

export interface FunnelDailyInput {
  readonly tenantId: string;
  readonly runId: string;
  readonly productDays: readonly FunnelProductDay[];
  readonly source?: FunnelSource;
}

export interface VersionFunnelDailyResult {
  readonly versions: number;
  readonly inputRuns: number;
}

type QueryClient = Pick<PoolClient, 'query'>;

export async function versionFunnelDaily(client: QueryClient, input: FunnelDailyInput): Promise<VersionFunnelDailyResult> {
  const source = input.source ?? FUNNEL_SOURCE;
  const keys = new Map<string, FunnelProductDay>();
  for (const productDay of input.productDays) keys.set(`${productDay.nmId}:${productDay.calendarDay}`, productDay);
  if (keys.size === 0) return { versions: 0, inputRuns: 0 };
  const pairs = JSON.stringify([...keys.values()].map((pair) => ({ nm_id: pair.nmId, calendar_day: pair.calendarDay })));
  const versions = await client.query(
    `INSERT INTO fact_funnel_daily (tenant_id, nm_id, calendar_day, source, run_id, canonical_sha256, evidence_sha256,
       open_card, cart, orders, orders_sum_rub, buyouts, buyouts_sum_rub)
     SELECT l.tenant_id, l.nm_id, l.calendar_day, l.source, $2::uuid, l.canonical_sha256, l.evidence_sha256,
       l.open_card, l.cart, l.orders, l.orders_sum_rub, l.buyouts, l.buyouts_sum_rub
     FROM jsonb_to_recordset($3::jsonb) AS p(nm_id bigint, calendar_day date)
     JOIN stg_wb_funnel_latest l ON l.tenant_id = $1::text AND l.source = $4::text AND l.nm_id = p.nm_id AND l.calendar_day = p.calendar_day`,
    [input.tenantId, input.runId, pairs, source],
  );
  if ((versions.rowCount ?? 0) !== keys.size) {
    throw new Error(`funnel-daily: expected ${keys.size} versions from stg_wb_funnel_latest, wrote ${versions.rowCount ?? 0}`);
  }
  const inputs = await client.query(
    `INSERT INTO collector_run_inputs (tenant_id, run_id, input_run_id)
     SELECT DISTINCT l.tenant_id, $2::uuid, l.run_id
     FROM jsonb_to_recordset($3::jsonb) AS p(nm_id bigint, calendar_day date)
     JOIN stg_wb_funnel_latest l ON l.tenant_id = $1::text AND l.source = $4::text AND l.nm_id = p.nm_id AND l.calendar_day = p.calendar_day
     WHERE l.run_id <> $2::uuid
     ON CONFLICT (tenant_id, run_id, input_run_id) DO NOTHING`,
    [input.tenantId, input.runId, pairs, source],
  );
  return { versions: versions.rowCount ?? 0, inputRuns: inputs.rowCount ?? 0 };
}
