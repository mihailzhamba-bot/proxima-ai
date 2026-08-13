#!/usr/bin/env node
import { resolve } from 'node:path';

import { runBusinessSignal } from '../business-signal/pipeline.js';
import { PostgresSignalRepository } from '../business-signal/repository.js';
import { readFounderChatId, privateDatabasePool } from '../business-signal/runtime.js';
import { readPrivateSecret } from '../business-signal/secrets.js';
import { TelegramBotApi } from '../business-signal/telegram.js';

function args(): { values: Record<string, string>; send: boolean; allowAnalyticsReadWrite: boolean } {
  const values: Record<string, string> = {};
  let send = false;
  let allowAnalyticsReadWrite = false;
  for (let index = 2; index < process.argv.length; index += 1) {
    const key = process.argv[index];
    if (key === '--send') { send = true; continue; }
    if (key === '--allow-analytics-read-write') { allowAnalyticsReadWrite = true; continue; }
    const value = process.argv[index + 1];
    if (!key?.startsWith('--') || !value || value.startsWith('--')) throw new Error('invalid CLI arguments');
    values[key.slice(2)] = value;
    index += 1;
  }
  return { values, send, allowAnalyticsReadWrite };
}

async function main(): Promise<void> {
  const { values, send, allowAnalyticsReadWrite } = args();
  const required = ['tenant', 'database-url-file', 'raw-root', 'statistics-token-file', 'analytics-token-file', 'finance-token-file'];
  if (required.some((key) => !values[key])) throw new Error(`required options: ${required.join(', ')}`);
  const [statisticsToken, analyticsToken, financeToken] = await Promise.all([
    readPrivateSecret(values['statistics-token-file']!, 'WB Statistics token file'),
    readPrivateSecret(values['analytics-token-file']!, 'WB Analytics token file'),
    readPrivateSecret(values['finance-token-file']!, 'WB Finance token file'),
  ]);
  let telegram: { telegram: TelegramBotApi; founderChatId: bigint } | undefined;
  if (send) {
    if (!values['telegram-token-file'] || !values['founder-chat-source']) throw new Error('--send requires Telegram token and founder chat private source');
    const [token, founderChatId] = await Promise.all([
      readPrivateSecret(values['telegram-token-file'], 'Telegram token file'),
      readFounderChatId(values['founder-chat-source']),
    ]);
    telegram = { telegram: new TelegramBotApi(token), founderChatId };
  }
  const pool = await privateDatabasePool(values['database-url-file']!);
  try {
    const result = await runBusinessSignal(new PostgresSignalRepository(pool), {
      tenantId: values.tenant!,
      repositoryRoot: resolve(import.meta.dirname, '../../../..'),
      rawRoot: values['raw-root']!,
      statisticsToken,
      analyticsToken,
      financeToken,
      allowAnalyticsReadWrite,
      ...(telegram ? { send: telegram } : {}),
    });
    process.stdout.write(`${JSON.stringify({
      run_id: result.runId,
      status: result.status,
      reason: result.reason,
      candidate: result.candidate ? {
        nm_id: result.candidate.nmId.toString(),
        internal_article: result.candidate.internalArticle,
        warehouse: result.candidate.warehouse,
        days_cover: result.candidate.daysCover,
        margin_per_unit_rub: result.candidate.marginPerUnitRub.toFixed(2),
      } : undefined,
      telegram_message_id: result.telegramMessageId?.toString(),
    })}\n`);
    if (result.status === 'BLOCKED') process.exitCode = 2;
  } finally { await pool.end(); }
}

main().catch((error: unknown) => {
  const code = error && typeof error === 'object' && 'code' in error ? String(error.code) : 'FAILED';
  process.stderr.write(`${JSON.stringify({ status: 'failed', code })}\n`);
  process.exitCode = 1;
});
