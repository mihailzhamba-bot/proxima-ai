import assert from 'node:assert/strict';
import { chmod, mkdtemp, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import test from 'node:test';

import { readProductConfigCsv, readWarehouseMapCsv } from '../src/business-signal/config.js';

async function privateCsv(name: string, content: string): Promise<string> {
  const directory = await mkdtemp(join(tmpdir(), 'proxima-signal-config-'));
  const path = join(directory, name);
  await writeFile(path, content, { mode: 0o600 });
  return path;
}

test('reads strict private product and warehouse version CSVs', async () => {
  const productPath = await privateCsv('products.csv', [
    'tenant_id,nm_id,internal_article,cogs_rub,lead_time_days,safety_buffer_days,effective_from',
    'pilot-tenant,1234567,SKU-TEST,123.45,40,7,2026-08-13',
  ].join('\n'));
  const warehousePath = await privateCsv('warehouses.csv', [
    'tenant_id,sales_warehouse_name,stock_warehouse_name,canonical_warehouse,effective_from',
    'pilot-tenant,Коледино,Коледино,Коледино,2026-08-13',
  ].join('\n'));

  const [products, warehouses] = await Promise.all([
    readProductConfigCsv(productPath),
    readWarehouseMapCsv(warehousePath),
  ]);
  assert.equal(products[0]?.nmId, 1234567n);
  assert.equal(products[0]?.cogsRub.toFixed(2), '123.45');
  assert.equal(warehouses[0]?.canonicalWarehouse, 'Коледино');
});

test('rejects group-readable business config before parsing', async () => {
  const path = await privateCsv('products.csv', 'tenant_id\nvalue\n');
  await chmod(path, 0o640);
  await assert.rejects(readProductConfigCsv(path), { code: 'CONFIG_UNSAFE' });
});

test('rejects ambiguous product values', async () => {
  const path = await privateCsv('products.csv', [
    'tenant_id,nm_id,internal_article,cogs_rub,lead_time_days,safety_buffer_days,effective_from',
    'pilot-tenant,1234567, SKU,12.345,0,-1,2026-08-13',
  ].join('\n'));
  await assert.rejects(readProductConfigCsv(path), { code: 'CONFIG_INVALID' });
});
