#!/usr/bin/env node
import { writeFounderChatId } from '../business-signal/runtime.js';
import { readPrivateSecret } from '../business-signal/secrets.js';
import { TelegramBotApi } from '../business-signal/telegram.js';
import { discoverFounderChatId } from '../business-signal/telegram-setup.js';

function args(): Record<string, string> {
  if ((process.argv.length - 2) % 2 !== 0) throw new Error('every option requires a value');
  const result: Record<string, string> = {};
  for (let index = 2; index < process.argv.length; index += 2) {
    const key = process.argv[index];
    const value = process.argv[index + 1];
    if (!key?.startsWith('--') || !value || value.startsWith('--')) throw new Error('invalid CLI arguments');
    const name = key.slice(2);
    if (!['telegram-token-file', 'founder-chat-source'].includes(name) || result[name]) throw new Error('unknown or duplicate option');
    result[name] = value;
  }
  return result;
}

async function main(): Promise<void> {
  const options = args();
  if (!options['telegram-token-file'] || !options['founder-chat-source']) throw new Error('required options: telegram-token-file, founder-chat-source');
  const token = await readPrivateSecret(options['telegram-token-file'], 'Telegram token file');
  const chatId = await discoverFounderChatId(new TelegramBotApi(token));
  await writeFounderChatId(options['founder-chat-source'], chatId);
  process.stdout.write(`${JSON.stringify({ status: 'founder-chat-written' })}\n`);
}

main().catch((error: unknown) => {
  const code = error && typeof error === 'object' && 'code' in error ? String(error.code) : 'FAILED';
  process.stderr.write(`${JSON.stringify({ status: 'failed', code })}\n`);
  process.exitCode = 1;
});
