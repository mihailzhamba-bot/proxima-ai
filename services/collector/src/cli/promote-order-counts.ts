#!/usr/bin/env node
import { privateDatabasePool } from '../business-signal/runtime.js';
import { promoteOrderCounts, PromotionError } from '../facts/promote-order-counts.js';
import { parsePromotionArgs } from './promotion-args.js';

async function main(): Promise<void> {
  const args = parsePromotionArgs(process.argv.slice(2));
  const pool = await privateDatabasePool(args['database-url-file']);
  try {
    const result = await promoteOrderCounts(pool, { tenantId: args.tenant, taskId: args['task-id'] });
    process.stdout.write(`${JSON.stringify({ attempt_id: result.attemptId, status: result.status, accepted_rows: result.acceptedRows, quarantined_rows: result.quarantinedRows })}\n`);
    if (result.status === 'FAILED') process.exitCode = 2;
  } finally {
    await pool.end();
  }
}

main().catch((error: unknown) => {
  const code = error instanceof PromotionError ? error.code : 'PROMOTION_FAILED';
  process.stderr.write(`${JSON.stringify({ status: 'failed', code })}\n`);
  process.exitCode = 1;
});
