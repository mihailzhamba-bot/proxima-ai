#!/usr/bin/env node
import { privateDatabasePool } from '../business-signal/runtime.js';
import { promoteOrderCounts } from '../facts/promote-order-counts.js';

const REQUIRED = ['tenant', 'task-id', 'parser-version', 'database-url-file'] as const;

function args(): Record<(typeof REQUIRED)[number], string> {
  const values: Partial<Record<(typeof REQUIRED)[number], string>> = {};
  for (let index = 2; index < process.argv.length; index += 2) {
    const option = process.argv[index];
    const value = process.argv[index + 1];
    const key = option?.startsWith('--') ? option.slice(2) : '';
    if (!REQUIRED.includes(key as (typeof REQUIRED)[number]) || !value || value.startsWith('--') || values[key as (typeof REQUIRED)[number]]) {
      throw new Error(`required options: ${REQUIRED.map((item) => `--${item}`).join(', ')}`);
    }
    values[key as (typeof REQUIRED)[number]] = value;
  }
  if (REQUIRED.some((key) => !values[key])) throw new Error(`required options: ${REQUIRED.map((item) => `--${item}`).join(', ')}`);
  return values as Record<(typeof REQUIRED)[number], string>;
}

async function main(): Promise<void> {
  const values = args();
  const pool = await privateDatabasePool(values['database-url-file']);
  try {
    const client = await pool.connect();
    try {
      await client.query('SET ROLE proxima_source_publisher');
      const role = await client.query<{ current_user: string }>('SELECT current_user');
      if (role.rows[0]?.current_user !== 'proxima_source_publisher') throw new Error('ROLE_REQUIRED');
      const result = await promoteOrderCounts(client, { tenantId: values.tenant, taskId: values['task-id'], parserVersion: values['parser-version'] });
      process.stdout.write(`${JSON.stringify({ attempt_id: result.attemptId, status: result.status, accepted: result.accepted, quarantined: result.quarantined })}\n`);
    } finally {
      client.release();
    }
  } finally {
    await pool.end();
  }
}

main().catch((error: unknown) => {
  const code = error && typeof error === 'object' && 'code' in error ? String(error.code) : error instanceof Error ? error.message : 'FAILED';
  process.stderr.write(`${JSON.stringify({ status: 'failed', code })}\n`);
  process.exitCode = 1;
});
