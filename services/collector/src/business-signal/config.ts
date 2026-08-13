import { parse } from 'csv-parse/sync';
import { Decimal } from 'decimal.js';
import type { PoolClient } from 'pg';

import { BusinessSignalError, type ProductConfig, type WarehouseMap } from './types.js';
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
const TENANT_PATTERN = /^[a-z0-9][a-z0-9_-]{2,63}$/;
const DATE_PATTERN = /^\d{4}-\d{2}-\d{2}$/;

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
