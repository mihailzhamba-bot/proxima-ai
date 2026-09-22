/**
 * Row-level observations of WB Statistics orders/sales (Story 1.4, AD-2).
 *
 * One observation = one natural key (`srid` for orders, `saleID` for sales)
 * at one WB `lastChangeDate`. The same PK with the same canonical payload is
 * a replay and is skipped. WB also renames warehouses retroactively without
 * bumping `lastChangeDate` (case 2026-09-22), so the same PK whose payload
 * differs only in `warehouseName` is accepted as a benign rename and updates
 * the stored payload. The same PK with any other payload difference means WB
 * changed a "closed" record and the run must fail with WB_SCHEMA_DRIFT
 * instead of silently choosing a version. Shared by `collect` and `backfill`
 * jobs.
 */
import type { PoolClient } from 'pg';

import { canonicalJson, sha256 } from '../intake/manifest.js';
import { WbClientError } from './client.js';
import { mskInstant } from './msk-day.js';
import type { WbEndpointId } from './registry.js';

export type ObservationTable = 'stg_wb_orders_obs' | 'stg_wb_sales_obs';
export type ObservationKeyColumn = 'srid' | 'sale_id';

export interface WbObservation {
  readonly key: string;
  /** Instant with explicit Moscow offset, e.g. `2026-08-17T06:48:49+03:00`. */
  readonly lastChangeAt: string;
  readonly canonicalSha256: string;
  readonly payload: Readonly<Record<string, unknown>>;
}

export interface ObservationSet {
  readonly endpointId: WbEndpointId;
  readonly table: ObservationTable;
  readonly keyColumn: ObservationKeyColumn;
  /** sha256 of the raw response body these rows were parsed from. */
  readonly contentSha256: string;
  /** Rows as received, before in-batch replay collapse. */
  readonly received: number;
  readonly rows: readonly WbObservation[];
}

export interface InsertObservationsResult {
  readonly received: number;
  readonly inserted: number;
  readonly skipped: number;
}

interface ObservationSpec {
  readonly endpointId: WbEndpointId;
  readonly table: ObservationTable;
  readonly keyColumn: ObservationKeyColumn;
  readonly keyField: 'srid' | 'saleID';
}

const ORDERS_SPEC: ObservationSpec = { endpointId: 'statistics.orders', table: 'stg_wb_orders_obs', keyColumn: 'srid', keyField: 'srid' };
const SALES_SPEC: ObservationSpec = { endpointId: 'statistics.sales', table: 'stg_wb_sales_obs', keyColumn: 'sale_id', keyField: 'saleID' };
const TABLE_SPECS: Readonly<Record<ObservationTable, ObservationSpec>> = { stg_wb_orders_obs: ORDERS_SPEC, stg_wb_sales_obs: SALES_SPEC };
const SHA256_HEX = /^[0-9a-f]{64}$/;
const ZONELESS_DATETIME = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?$/;

export function toOrderObservations(rows: readonly unknown[], contentSha256: string): ObservationSet {
  return toObservations(rows, contentSha256, ORDERS_SPEC);
}

export function toSaleObservations(rows: readonly unknown[], contentSha256: string): ObservationSet {
  return toObservations(rows, contentSha256, SALES_SPEC);
}

function drift(spec: ObservationSpec, message: string): WbClientError {
  return new WbClientError('WB_SCHEMA_DRIFT', `${spec.endpointId}: ${message}`, spec.endpointId);
}

function toObservations(rows: readonly unknown[], contentSha256: string, spec: ObservationSpec): ObservationSet {
  if (!SHA256_HEX.test(contentSha256)) {
    throw new RangeError('toObservations: contentSha256 must be 64 lowercase hex chars');
  }
  const byPrimaryKey = new Map<string, WbObservation>();
  rows.forEach((row, index) => {
    if (row === null || typeof row !== 'object' || Array.isArray(row)) {
      throw drift(spec, `row ${index} is not an object`);
    }
    const record = row as Record<string, unknown>;
    const key = record[spec.keyField];
    if (typeof key !== 'string' || key === '') {
      throw drift(spec, `row ${index} has no usable ${spec.keyField}`);
    }
    const lastChangeDate = record.lastChangeDate;
    if (typeof lastChangeDate !== 'string' || !ZONELESS_DATETIME.test(lastChangeDate)) {
      throw drift(spec, `row ${index} (${spec.keyField} ${key}) has no zoneless lastChangeDate`);
    }
    const observation: WbObservation = {
      key,
      lastChangeAt: mskInstant(lastChangeDate),
      canonicalSha256: sha256(canonicalJson(record)),
      payload: record,
    };
    const primaryKey = `${key} ${observation.lastChangeAt}`;
    const seen = byPrimaryKey.get(primaryKey);
    if (seen === undefined) {
      byPrimaryKey.set(primaryKey, observation);
    } else if (seen.canonicalSha256 !== observation.canonicalSha256) {
      throw drift(spec, `${spec.keyField} ${key} at ${lastChangeDate} appears twice with different payloads`);
    }
  });
  return {
    endpointId: spec.endpointId,
    table: spec.table,
    keyColumn: spec.keyColumn,
    contentSha256,
    received: rows.length,
    rows: [...byPrimaryKey.values()],
  };
}

/**
 * Writes an observation set inside the caller's transaction (the `work`
 * callback of `RunLedger.succeed`, whose session already carries the tenant
 * GUC). Each batch checks drift before its own insert; earlier batches may
 * already be written when a later one drifts, so "no observations of a failed
 * run" is guaranteed by the caller's ROLLBACK, not by this function alone.
 * Table and key column names come from the closed spec table, never from input.
 * Identical replays stay no-ops (skipped); a warehouse-only rename rewrites
 * the stored payload in place; any other difference fails the drift check
 * before the insert.
 */
export async function insertObservations(
  client: PoolClient,
  tenantId: string,
  runId: string,
  set: ObservationSet,
  batchSize = 5_000,
): Promise<InsertObservationsResult> {
  const spec = TABLE_SPECS[set.table];
  if (spec === undefined || spec.keyColumn !== set.keyColumn) {
    throw new RangeError(`insertObservations: unknown observation table ${String(set.table)}`);
  }
  if (!Number.isSafeInteger(batchSize) || batchSize < 1) {
    throw new RangeError('insertObservations: batchSize must be a positive integer');
  }
  const { table, keyColumn } = spec;
  const driftSql =
    `SELECT v.key FROM jsonb_to_recordset($2::jsonb) AS v(key text, last_change_at timestamptz, canonical_sha256 text, payload jsonb)` +
    ` JOIN ${table} s ON s.tenant_id = $1 AND s.${keyColumn} = v.key AND s.last_change_at = v.last_change_at` +
    ` WHERE (s.payload - 'warehouseName') IS DISTINCT FROM (v.payload - 'warehouseName') LIMIT 5`;
  const insertSql =
    `INSERT INTO ${table} (tenant_id, ${keyColumn}, last_change_at, run_id, content_sha256, canonical_sha256, payload)` +
    ` SELECT $1, v.key, v.last_change_at, $3, $4, v.canonical_sha256, v.payload` +
    ` FROM jsonb_to_recordset($2::jsonb) AS v(key text, last_change_at timestamptz, canonical_sha256 text, payload jsonb)` +
    ` ON CONFLICT (tenant_id, ${keyColumn}, last_change_at) DO UPDATE SET` +
    ` payload = EXCLUDED.payload, canonical_sha256 = EXCLUDED.canonical_sha256, content_sha256 = EXCLUDED.content_sha256, run_id = EXCLUDED.run_id` +
    ` WHERE ${table}.payload IS DISTINCT FROM EXCLUDED.payload`;
  let inserted = 0;
  for (let offset = 0; offset < set.rows.length; offset += batchSize) {
    const batch = JSON.stringify(set.rows.slice(offset, offset + batchSize).map((row) => ({
      key: row.key,
      last_change_at: row.lastChangeAt,
      canonical_sha256: row.canonicalSha256,
      payload: row.payload,
    })));
    const conflicts = await client.query<{ key: string }>(driftSql, [tenantId, batch]);
    if ((conflicts.rowCount ?? 0) > 0) {
      const keys = conflicts.rows.map((row) => row.key).join(', ');
      throw drift(spec, `${table}: existing observations differ for the same ${keyColumn}/lastChangeDate (${keys})`);
    }
    const result = await client.query(insertSql, [tenantId, batch, runId, set.contentSha256]);
    inserted += result.rowCount ?? 0;
  }
  return { received: set.received, inserted, skipped: set.rows.length - inserted };
}
