#!/usr/bin/env node
import { validateSignalInputFiles } from '../business-signal/input-validation.js';

const REQUIRED_OPTIONS = [
  'tenant',
  'statistics-token-file',
  'analytics-token-file',
  'finance-token-file',
  'telegram-token-file',
  'founder-chat-source',
  'products-csv',
  'warehouses-csv',
] as const;

function args(): Record<string, string> {
  if ((process.argv.length - 2) % 2 !== 0) throw new Error('every option requires a value');
  const result: Record<string, string> = {};
  for (let index = 2; index < process.argv.length; index += 2) {
    const key = process.argv[index];
    const value = process.argv[index + 1];
    if (!key?.startsWith('--') || !value || key === '--') throw new Error('expected named file options');
    const name = key.slice(2);
    if (!(REQUIRED_OPTIONS as readonly string[]).includes(name) || result[name] !== undefined) {
      throw new Error('unknown or duplicate option');
    }
    result[name] = value;
  }
  for (const option of REQUIRED_OPTIONS) {
    if (!result[option]) throw new Error(`missing --${option}`);
  }
  return result;
}

async function main(): Promise<void> {
  const options = args();
  const validation = await validateSignalInputFiles({
    tenantId: options.tenant!,
    statisticsTokenFile: options['statistics-token-file']!,
    analyticsTokenFile: options['analytics-token-file']!,
    financeTokenFile: options['finance-token-file']!,
    telegramTokenFile: options['telegram-token-file']!,
    founderChatSource: options['founder-chat-source']!,
    productsCsv: options['products-csv']!,
    warehousesCsv: options['warehouses-csv']!,
  });
  process.stdout.write(`${JSON.stringify({ status: 'valid', ...validation })}\n`);
}

main().catch((error: unknown) => {
  const code = error && typeof error === 'object' && 'code' in error ? String(error.code) : 'FAILED';
  process.stderr.write(`${JSON.stringify({ status: 'failed', code })}\n`);
  process.exitCode = 1;
});
