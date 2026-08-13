import type { TelegramTransport } from './telegram.js';
import { BusinessSignalError } from './types.js';

function apiResult(payload: unknown): unknown {
  if (!payload || typeof payload !== 'object' || Array.isArray(payload) || (payload as Record<string, unknown>).ok !== true) {
    throw new BusinessSignalError('TELEGRAM_SETUP_FAILED', 'Telegram setup response is invalid');
  }
  return (payload as Record<string, unknown>).result;
}

function object(value: unknown): Record<string, unknown> | undefined {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : undefined;
}

function integer(value: unknown): bigint | undefined {
  if ((typeof value !== 'number' && typeof value !== 'string') || !/^-?\d+$/.test(String(value))) return undefined;
  const result = BigInt(String(value));
  return result === 0n ? undefined : result;
}

export async function discoverFounderChatId(transport: TelegramTransport): Promise<bigint> {
  const webhook = object(apiResult(await transport.call('getWebhookInfo', {})));
  if (!webhook || typeof webhook.url !== 'string') {
    throw new BusinessSignalError('TELEGRAM_SETUP_FAILED', 'Telegram webhook status is invalid');
  }
  if (webhook.url !== '') {
    throw new BusinessSignalError('TELEGRAM_WEBHOOK_ACTIVE', 'disable the Telegram webhook before founder discovery');
  }

  const updates = apiResult(await transport.call('getUpdates', {
    limit: 100,
    timeout: 0,
    allowed_updates: ['message'],
  }));
  if (!Array.isArray(updates)) throw new BusinessSignalError('TELEGRAM_SETUP_FAILED', 'Telegram updates result is invalid');

  const chatIds = new Set<bigint>();
  for (const updateValue of updates) {
    const update = object(updateValue);
    const message = object(update?.message);
    const chat = object(message?.chat);
    const from = object(message?.from);
    const chatId = integer(chat?.id);
    const fromId = integer(from?.id);
    if (!message || !chat || !from || !chatId || !fromId) continue;
    if (chat.type !== 'private' || from.is_bot !== false || chatId !== fromId) continue;
    if (typeof message.text !== 'string' || !/^\/start(?:@[A-Za-z0-9_]+)?(?:\s|$)/.test(message.text)) continue;
    chatIds.add(chatId);
  }

  if (chatIds.size === 0) throw new BusinessSignalError('TELEGRAM_START_NOT_FOUND', 'send /start to the bot from the founder account');
  if (chatIds.size !== 1) throw new BusinessSignalError('TELEGRAM_START_AMBIGUOUS', 'more than one private account sent /start to the bot');
  return [...chatIds][0]!;
}
