import { parse } from 'csv-parse/sync';
import { Decimal } from 'decimal.js';
import type { PoolClient } from 'pg';

import {
  BusinessSignalError,
  type CogsStatus,
  type ClientPassportConfig,
  type ProductConfig,
  type SupplyPlanRecord,
  type SupplyStatus,
  type WarehouseMap,
} from './types.js';
import { readPrivateFile } from './secrets.js';

const PRODUCT_HEADERS = [
  'tenant_id',
  'nm_id',
  'internal_article',
  'cogs_rub',
  'lead_time_days',
  'safety_buffer_days',
  'effective_from',
] as const;
const WAREHOUSE_HEADERS = [
  'tenant_id',
  'sales_warehouse_name',
  'stock_warehouse_name',
  'canonical_warehouse',
  'effective_from',
] as const;
const PASSPORT_HEADERS = [
  'tenant_id',
  'effective_from',
  'sales_drop_threshold_pct',
  'days_cover_threshold_days',
  'lead_time_days',
  'safety_buffer_days',
  'cogs_status',
  'priority_categories',
  'warehouses',
  'weekend_days',
] as const;
const SUPPLY_HEADERS = [
  'supply_id',
  'tenant_id',
  'nm_id',
  'quantity',
  'order_date',
  'expected_arrival_date',
  'status',
  'entered_by',
  'entered_at',
] as const;
const TENANT_PATTERN = /^[a-z0-9][a-z0-9_-]{2,63}$/;
const DATE_PATTERN = /^\d{4}-\d{2}-\d{2}$/;
const WEEKDAY_VALUES = new Set(['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun']);
const COGS_STATUS_VALUES = new Set<CogsStatus>(['complete', 'top_sku', 'missing']);
const SUPPLY_STATUS_VALUES = new Set<SupplyStatus>(['PLAN', 'SHIPPED', 'ACCEPTED', 'CANCELLED']);

type CsvRow = Record<string, string>;

function exactPositiveInteger(value: string, label: string, allowZero = false): number {
  if (!/^\d+$/.test(value)) throw new BusinessSignalError('CONFIG_INVALID', `${label} must be an integer`);
  const result = Number(value);
  if (!Number.isSafeInteger(result) || (allowZero ? result < 0 : result <= 0)) {
    throw new BusinessSignalError('CONFIG_INVALID', `${label} is outside the supported range`);
  }
  return result;
}

function requiredText(value: string, label: string, maxLength = 256): string {
  if (!value || value !== value.trim() || value.length > maxLength) {
    throw new BusinessSignalError('CONFIG_INVALID', `${label} is invalid`);
  }
  return value;
}

function validDate(value: string): string {
  if (!DATE_PATTERN.test(value) || Number.isNaN(Date.parse(`${value}T00:00:00Z`))) {
    throw new BusinessSignalError('CONFIG_INVALID', 'effective_from must be YYYY-MM-DD');
  }
  return value;
}

function validDateField(value: string, label: string): string {
  if (!DATE_PATTERN.test(value) || Number.isNaN(Date.parse(`${value}T00:00:00Z`))) {
    throw new BusinessSignalError('CONFIG_INVALID', `${label} must be YYYY-MM-DD`);
  }
  return value;
}

function thresholdPct(value: string, label: string): number {
  if (!/^\d{1,3}(\.\d{1,2})?$/.test(value)) {
    throw new BusinessSignalError('CONFIG_INVALID', `${label} must be a number with at most 2 decimals`);
  }
  const result = Number(value);
  if (!(result > 0) || result > 100) {
    throw new BusinessSignalError('CONFIG_INVALID', `${label} is outside the supported range`);
  }
  return result;
}

function enumValue<T extends string>(value: string, allowed: Set<T>, label: string): T {
  if (!allowed.has(value as T)) {
    throw new BusinessSignalError('CONFIG_INVALID', `${label} must be one of: ${[...allowed].join('|')}`);
  }
  return value as T;
}

function textList(value: string, label: string): string[] {
  if (value === '') return [];
  return value.split(';').map((item) => {
    const trimmed = item.trim();
    if (!trimmed || trimmed !== item || trimmed.length > 128) {
      throw new BusinessSignalError('CONFIG_INVALID', `${label} contains an invalid entry`);
    }
    return trimmed;
  });
}

function weekdayList(value: string): string[] {
  if (value === '') return [];
  const items = value.split(';');
  if (new Set(items).size !== items.length) {
    throw new BusinessSignalError('CONFIG_INVALID', 'weekend_days contains duplicates');
  }
  return items.map((item) => {
    if (!WEEKDAY_VALUES.has(item)) {
      throw new BusinessSignalError('CONFIG_INVALID', 'weekend_days must be mon|tue|wed|thu|fri|sat|sun');
    }
    return item;
  });
}

async function readPrivateCsv(path: string, headers: readonly string[]): Promise<CsvRow[]> {
  let bytes: Buffer;
  try { bytes = await readPrivateFile(path, 'config CSV'); } catch (error) {
    if (error instanceof BusinessSignalError) throw new BusinessSignalError('CONFIG_UNSAFE', 'config CSV must be a private regular file with mode 0600');
    throw error;
  }
  const rows = parse(bytes, {
    bom: true,
    columns: true,
    skip_empty_lines: true,
    trim: false,
  }) as CsvRow[];
  if (rows.length === 0) throw new BusinessSignalError('CONFIG_INVALID', 'config CSV has no rows');
  const actualHeaders = Object.keys(rows[0] ?? {});
  if (actualHeaders.length !== headers.length || actualHeaders.some((header, index) => header !== headers[index])) {
    throw new BusinessSignalError('CONFIG_INVALID', `config CSV headers must be exactly: ${headers.join(',')}`);
  }
  return rows;
}

export async function readProductConfigCsv(path: string): Promise<ProductConfig[]> {
  const rows = await readPrivateCsv(path, PRODUCT_HEADERS);
  return rows.map((row) => {
    const tenantId = requiredText(row.tenant_id ?? '', 'tenant_id', 64);
    if (!TENANT_PATTERN.test(tenantId)) throw new BusinessSignalError('CONFIG_INVALID', 'tenant_id is invalid');
    const nmId = BigInt(exactPositiveInteger(row.nm_id ?? '', 'nm_id'));
    const cogsRub = new Decimal(row.cogs_rub ?? '');
    if (!cogsRub.isFinite() || cogsRub.isNegative() || cogsRub.decimalPlaces() > 2) {
      throw new BusinessSignalError('CONFIG_INVALID', 'cogs_rub must be a non-negative amount with at most 2 decimals');
    }
    return {
      tenantId,
      nmId,
      internalArticle: requiredText(row.internal_article ?? '', 'internal_article', 128),
      cogsRub,
      leadTimeDays: exactPositiveInteger(row.lead_time_days ?? '', 'lead_time_days'),
      safetyBufferDays: exactPositiveInteger(row.safety_buffer_days ?? '', 'safety_buffer_days', true),
      effectiveFrom: validDate(row.effective_from ?? ''),
    };
  });
}

export async function readWarehouseMapCsv(path: string): Promise<WarehouseMap[]> {
  const rows = await readPrivateCsv(path, WAREHOUSE_HEADERS);
  return rows.map((row) => {
    const tenantId = requiredText(row.tenant_id ?? '', 'tenant_id', 64);
    if (!TENANT_PATTERN.test(tenantId)) throw new BusinessSignalError('CONFIG_INVALID', 'tenant_id is invalid');
    return {
      tenantId,
      salesWarehouseName: requiredText(row.sales_warehouse_name ?? '', 'sales_warehouse_name'),
      stockWarehouseName: requiredText(row.stock_warehouse_name ?? '', 'stock_warehouse_name'),
      canonicalWarehouse: requiredText(row.canonical_warehouse ?? '', 'canonical_warehouse'),
      effectiveFrom: validDate(row.effective_from ?? ''),
    };
  });
}

export async function readClientPassportCsv(path: string): Promise<ClientPassportConfig[]> {
  const rows = await readPrivateCsv(path, PASSPORT_HEADERS);
  return rows.map((row) => {
    const tenantId = requiredText(row.tenant_id ?? '', 'tenant_id', 64);
    if (!TENANT_PATTERN.test(tenantId)) throw new BusinessSignalError('CONFIG_INVALID', 'tenant_id is invalid');
    return {
      tenantId,
      effectiveFrom: validDate(row.effective_from ?? ''),
      salesDropThresholdPct: thresholdPct(row.sales_drop_threshold_pct ?? '', 'sales_drop_threshold_pct'),
      daysCoverThresholdDays: exactPositiveInteger(row.days_cover_threshold_days ?? '', 'days_cover_threshold_days'),
      leadTimeDays: exactPositiveInteger(row.lead_time_days ?? '', 'lead_time_days'),
      safetyBufferDays: exactPositiveInteger(row.safety_buffer_days ?? '', 'safety_buffer_days', true),
      cogsStatus: enumValue(row.cogs_status ?? '', COGS_STATUS_VALUES, 'cogs_status'),
      priorityCategories: textList(row.priority_categories ?? '', 'priority_categories'),
      warehouses: textList(row.warehouses ?? '', 'warehouses'),
      weekendDays: weekdayList(row.weekend_days ?? ''),
      contacts: [],
    };
  });
}

export async function readSupplyPlanCsv(path: string): Promise<SupplyPlanRecord[]> {
  const rows = await readPrivateCsv(path, SUPPLY_HEADERS);
  return rows.map((row) => {
    const supplyId = requiredText(row.supply_id ?? '', 'supply_id', 128);
    const tenantId = requiredText(row.tenant_id ?? '', 'tenant_id', 64);
    if (!TENANT_PATTERN.test(tenantId)) throw new BusinessSignalError('CONFIG_INVALID', 'tenant_id is invalid');
    const orderDate = validDateField(row.order_date ?? '', 'order_date');
    const expectedArrivalDate = validDateField(row.expected_arrival_date ?? '', 'expected_arrival_date');
    if (Date.parse(expectedArrivalDate) < Date.parse(orderDate)) {
      throw new BusinessSignalError('CONFIG_INVALID', 'expected_arrival_date must not precede order_date');
    }
    return {
      supplyId,
      tenantId,
      nmId: BigInt(exactPositiveInteger(row.nm_id ?? '', 'nm_id')),
      quantity: exactPositiveInteger(row.quantity ?? '', 'quantity'),
      orderDate,
      expectedArrivalDate,
      status: enumValue(row.status ?? '', SUPPLY_STATUS_VALUES, 'status'),
      enteredBy: requiredText(row.entered_by ?? '', 'entered_by', 64),
      enteredAt: new Date().toISOString(),
    };
  });
}

export async function seedClientPassport(client: PoolClient, passports: ClientPassportConfig[]): Promise<void> {
  await client.query('BEGIN');
  try {
    for (const passport of passports) {
      await client.query('INSERT INTO tenants (tenant_id) VALUES ($1) ON CONFLICT (tenant_id) DO NOTHING', [passport.tenantId]);
      const result = await client.query<{ sales_drop_threshold_pct: string; days_cover_threshold_days: number; lead_time_days: number; safety_buffer_days: number; cogs_status: string }>(
        `INSERT INTO dim_client_passport
          (tenant_id, effective_from, sales_drop_threshold_pct, days_cover_threshold_days, lead_time_days, safety_buffer_days, cogs_status, priority_categories, warehouses, weekend_days, contacts)
         VALUES ($1, $2, $3, $4, $5, $6, $7, $8::jsonb, $9::jsonb, $10::jsonb, '[]'::jsonb)
         ON CONFLICT (tenant_id, effective_from) DO UPDATE SET tenant_id = EXCLUDED.tenant_id
         RETURNING sales_drop_threshold_pct::text, days_cover_threshold_days, lead_time_days, safety_buffer_days, cogs_status`,
        [
          passport.tenantId,
          passport.effectiveFrom,
          passport.salesDropThresholdPct.toFixed(2),
          passport.daysCoverThresholdDays,
          passport.leadTimeDays,
          passport.safetyBufferDays,
          passport.cogsStatus,
          JSON.stringify(passport.priorityCategories),
          JSON.stringify(passport.warehouses),
          JSON.stringify(passport.weekendDays),
        ],
      );
      const stored = result.rows[0];
      if (!stored || !new Decimal(stored.sales_drop_threshold_pct).equals(passport.salesDropThresholdPct)
        || stored.days_cover_threshold_days !== passport.daysCoverThresholdDays
        || stored.lead_time_days !== passport.leadTimeDays
        || stored.safety_buffer_days !== passport.safetyBufferDays
        || stored.cogs_status !== passport.cogsStatus) {
        throw new BusinessSignalError('CONFIG_CONFLICT', `conflicting client passport for ${passport.tenantId}/${passport.effectiveFrom}`);
      }
    }
    await client.query('COMMIT');
  } catch (error) {
    await client.query('ROLLBACK');
    throw error;
  }
}

export async function seedSupplyPlans(client: PoolClient, supplies: SupplyPlanRecord[]): Promise<void> {
  await client.query('BEGIN');
  try {
    for (const supply of supplies) {
      await client.query('INSERT INTO tenants (tenant_id) VALUES ($1) ON CONFLICT (tenant_id) DO NOTHING', [supply.tenantId]);
      const result = await client.query<{ nm_id: string; quantity: number; status: string }>(
        `INSERT INTO stg_supply_plan
          (tenant_id, supply_id, nm_id, quantity, order_date, expected_arrival_date, status, entered_by, entered_at)
         VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
         ON CONFLICT (tenant_id, supply_id) DO UPDATE SET tenant_id = EXCLUDED.tenant_id
         RETURNING nm_id::text, quantity, status`,
        [supply.tenantId, supply.supplyId, supply.nmId.toString(), supply.quantity, supply.orderDate, supply.expectedArrivalDate, supply.status, supply.enteredBy, supply.enteredAt],
      );
      const stored = result.rows[0];
      if (!stored || stored.nm_id !== supply.nmId.toString() || stored.quantity !== supply.quantity || stored.status !== supply.status) {
        throw new BusinessSignalError('CONFIG_CONFLICT', `conflicting supply plan for ${supply.tenantId}/${supply.supplyId}`);
      }
    }
    await client.query('COMMIT');
  } catch (error) {
    await client.query('ROLLBACK');
    throw error;
  }
}

export async function seedSignalConfig(
  client: PoolClient,
  products: ProductConfig[],
  warehouses: WarehouseMap[],
): Promise<void> {
  await client.query('BEGIN');
  try {
    for (const product of products) {
      await client.query('INSERT INTO tenants (tenant_id) VALUES ($1) ON CONFLICT (tenant_id) DO NOTHING', [product.tenantId]);
      const result = await client.query<{ internal_article: string; cogs_rub: string; lead_time_days: number; safety_buffer_days: number }>(
        `INSERT INTO dim_product
          (tenant_id, nm_id, internal_article, cogs_rub, lead_time_days, safety_buffer_days, effective_from)
         VALUES ($1, $2, $3, $4, $5, $6, $7)
         ON CONFLICT (tenant_id, nm_id, effective_from) DO UPDATE SET tenant_id = EXCLUDED.tenant_id
         RETURNING internal_article, cogs_rub::text, lead_time_days, safety_buffer_days`,
        [product.tenantId, product.nmId.toString(), product.internalArticle, product.cogsRub.toFixed(2), product.leadTimeDays, product.safetyBufferDays, product.effectiveFrom],
      );
      const stored = result.rows[0];
      if (!stored || stored.internal_article !== product.internalArticle || !new Decimal(stored.cogs_rub).equals(product.cogsRub)
        || stored.lead_time_days !== product.leadTimeDays || stored.safety_buffer_days !== product.safetyBufferDays) {
        throw new BusinessSignalError('CONFIG_CONFLICT', `conflicting dim_product version for ${product.tenantId}/${product.nmId}`);
      }
    }
    for (const warehouse of warehouses) {
      await client.query('INSERT INTO tenants (tenant_id) VALUES ($1) ON CONFLICT (tenant_id) DO NOTHING', [warehouse.tenantId]);
      const result = await client.query<{ stock_warehouse_name: string; canonical_warehouse: string }>(
        `INSERT INTO dim_warehouse_map
          (tenant_id, sales_warehouse_name, stock_warehouse_name, canonical_warehouse, effective_from)
         VALUES ($1, $2, $3, $4, $5)
         ON CONFLICT (tenant_id, sales_warehouse_name, effective_from) DO UPDATE SET tenant_id = EXCLUDED.tenant_id
         RETURNING stock_warehouse_name, canonical_warehouse`,
        [warehouse.tenantId, warehouse.salesWarehouseName, warehouse.stockWarehouseName, warehouse.canonicalWarehouse, warehouse.effectiveFrom],
      );
      const stored = result.rows[0];
      if (!stored || stored.stock_warehouse_name !== warehouse.stockWarehouseName || stored.canonical_warehouse !== warehouse.canonicalWarehouse) {
        throw new BusinessSignalError('CONFIG_CONFLICT', `conflicting warehouse map for ${warehouse.tenantId}/${warehouse.salesWarehouseName}`);
      }
    }
    await client.query('COMMIT');
  } catch (error) {
    await client.query('ROLLBACK');
    throw error;
  }
}
