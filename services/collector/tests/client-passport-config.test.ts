import assert from 'node:assert/strict';
import { chmod, mkdtemp, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import test from 'node:test';

import { readClientPassportCsv, readSupplyPlanCsv } from '../src/business-signal/config.js';

async function privateCsv(name: string, content: string): Promise<string> {
  const directory = await mkdtemp(join(tmpdir(), 'proxima-passport-config-'));
  const path = join(directory, name);
  await writeFile(path, content, { mode: 0o600 });
  return path;
}

const PASSPORT_CSV = [
  'tenant_id,effective_from,sales_drop_threshold_pct,days_cover_threshold_days,lead_time_days,safety_buffer_days,cogs_status,priority_categories,warehouses,weekend_days',
  'amirova-test,2026-08-28,20,21,60,15,top_sku,cat-a;cat-b,synthetic_warehouse,sat;sun',
].join('\n');

const SUPPLY_CSV = [
  'supply_id,tenant_id,nm_id,quantity,order_date,expected_arrival_date,status,entered_by,entered_at',
  'supply:test:001,amirova-test,1234567,500,2026-08-01,2026-10-01,PLAN,synthetic_am,2026-08-01T09:00:00Z',
].join('\n');

test('reads strict private client passport and supply plan CSVs', async () => {
  const [passportPath, supplyPath] = await Promise.all([
    privateCsv('passport.csv', PASSPORT_CSV),
    privateCsv('supplies.csv', SUPPLY_CSV),
  ]);
  const [passports, supplies] = await Promise.all([
    readClientPassportCsv(passportPath),
    readSupplyPlanCsv(supplyPath),
  ]);
  assert.equal(passports[0]?.salesDropThresholdPct, 20);
  assert.equal(passports[0]?.cogsStatus, 'top_sku');
  assert.deepEqual(passports[0]?.weekendDays, ['sat', 'sun']);
  assert.deepEqual(passports[0]?.contacts, []);
  assert.equal(supplies[0]?.nmId, 1234567n);
  assert.equal(supplies[0]?.status, 'PLAN');
});

test('rejects group-readable passport config before parsing', async () => {
  const path = await privateCsv('passport.csv', PASSPORT_CSV);
  await chmod(path, 0o640);
  await assert.rejects(readClientPassportCsv(path), { code: 'CONFIG_UNSAFE' });
});

test('rejects invalid passport threshold and weekday', async () => {
  const zeroThreshold = await privateCsv('passport.csv', PASSPORT_CSV.replace('2026-08-28,20,', '2026-08-28,0,'));
  await assert.rejects(readClientPassportCsv(zeroThreshold), { code: 'CONFIG_INVALID' });
  const badWeekday = await privateCsv('passport.csv', PASSPORT_CSV.replace('sat;sun', 'monday'));
  await assert.rejects(readClientPassportCsv(badWeekday), { code: 'CONFIG_INVALID' });
});

test('rejects invalid supply status and impossible arrival date', async () => {
  const badStatus = await privateCsv('supplies.csv', SUPPLY_CSV.replace(',PLAN,', ',принято,'));
  await assert.rejects(readSupplyPlanCsv(badStatus), { code: 'CONFIG_INVALID' });
  const badDates = await privateCsv('supplies.csv', SUPPLY_CSV.replace('2026-08-01,2026-10-01', '2026-10-01,2026-08-01'));
  await assert.rejects(readSupplyPlanCsv(badDates), { code: 'CONFIG_INVALID' });
});
