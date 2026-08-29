#!/usr/bin/env node
import {
  readClientPassportCsv,
  readProductConfigCsv,
  readSupplyPlanCsv,
  readWarehouseMapCsv,
  seedClientPassport,
  seedSignalConfig,
  seedSupplyPlans,
} from '../business-signal/config.js';
import { privateDatabasePool } from '../business-signal/runtime.js';

function args(): Record<string, string> {
  const result: Record<string, string> = {};
  for (let index = 2; index < process.argv.length; index += 2) {
    const key = process.argv[index];
    const value = process.argv[index + 1];
    if (!key?.startsWith('--') || !value) throw new Error('expected --database-url-file, --products-csv and --warehouses-csv (optional: --passport-csv, --supplies-csv)');
    result[key.slice(2)] = value;
  }
  return result;
}

async function main(): Promise<void> {
  const options = args();
  if (!options['database-url-file'] || !options['products-csv'] || !options['warehouses-csv']) throw new Error('missing required seed option');
  const [products, warehouses] = await Promise.all([
    readProductConfigCsv(options['products-csv']),
    readWarehouseMapCsv(options['warehouses-csv']),
  ]);
  const passports = options['passport-csv'] ? await readClientPassportCsv(options['passport-csv']) : [];
  const supplies = options['supplies-csv'] ? await readSupplyPlanCsv(options['supplies-csv']) : [];
  const pool = await privateDatabasePool(options['database-url-file']);
  try {
    const client = await pool.connect();
    try {
      await seedSignalConfig(client, products, warehouses);
      if (passports.length > 0) await seedClientPassport(client, passports);
      if (supplies.length > 0) await seedSupplyPlans(client, supplies);
    } finally { client.release(); }
  } finally { await pool.end(); }
  process.stdout.write(`${JSON.stringify({ status: 'seeded', products: products.length, warehouse_mappings: warehouses.length, passports: passports.length, supplies: supplies.length })}\n`);
}

main().catch((error: unknown) => {
  const code = error && typeof error === 'object' && 'code' in error ? String(error.code) : 'FAILED';
  process.stderr.write(`${JSON.stringify({ status: 'failed', code })}\n`);
  process.exitCode = 1;
});
