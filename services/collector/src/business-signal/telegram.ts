import type { SignalCandidate, SignalWindow } from './types.js';
import { BusinessSignalError } from './types.js';

function escapeHtml(value: string): string {
  return value.replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;').replaceAll('"', '&quot;');
}

export function formatStockoutMessage(candidate: SignalCandidate, window: SignalWindow): string {
  const margin = candidate.marginPerUnitRub.toDecimalPlaces(0, 4).toFixed(0);
  return [
    '<b>Риск out-of-stock</b>',
    '',
    `SKU ${escapeHtml(candidate.internalArticle)}, склад ${escapeHtml(candidate.warehouse)}: остатка хватит на ${candidate.daysCover} дн. Срок поставки - ${candidate.leadTimeDays} дн., буфер - ${candidate.safetyBufferDays} дн. Маржа - ${margin} ₽/шт.`,
    `Остаток на ${candidate.stockAsOf.toISOString()}; продажи и маржа за ${window.from}-${window.to}.`,
  ].join('\n');
}

export interface TelegramTransport {
  call(method: 'getMe' | 'getChat' | 'getWebhookInfo' | 'getUpdates' | 'sendMessage', body: Record<string, unknown>): Promise<unknown>;
}

export class TelegramBotApi implements TelegramTransport {
  constructor(private readonly token: string) {}
  async call(method: 'getMe' | 'getChat' | 'getWebhookInfo' | 'getUpdates' | 'sendMessage', body: Record<string, unknown>): Promise<unknown> {
    const response = await fetch(`https://api.telegram.org/bot${this.token}/${method}`, {
      method: 'POST',
      redirect: 'error',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      signal: AbortSignal.timeout(30_000),
    });
    if (!response.ok) throw new BusinessSignalError('TELEGRAM_FAILED', `Telegram ${method} returned HTTP ${response.status}`);
    const payload: unknown = await response.json();
    if (!payload || typeof payload !== 'object' || Array.isArray(payload) || (payload as Record<string, unknown>).ok !== true) {
      throw new BusinessSignalError('TELEGRAM_FAILED', `Telegram ${method} rejected the request`);
    }
    return payload;
  }
}

function telegramResult(payload: unknown): Record<string, unknown> {
  if (!payload || typeof payload !== 'object' || Array.isArray(payload)) throw new BusinessSignalError('TELEGRAM_FAILED', 'Telegram response is invalid');
  const result = (payload as Record<string, unknown>).result;
  if (!result || typeof result !== 'object' || Array.isArray(result)) throw new BusinessSignalError('TELEGRAM_FAILED', 'Telegram result is invalid');
  return result as Record<string, unknown>;
}

export async function preflightAndSend(transport: TelegramTransport, chatId: bigint, message: string): Promise<bigint> {
  telegramResult(await transport.call('getMe', {}));
  telegramResult(await transport.call('getChat', { chat_id: chatId.toString() }));
  const result = telegramResult(await transport.call('sendMessage', {
    chat_id: chatId.toString(),
    text: message,
    parse_mode: 'HTML',
    disable_web_page_preview: true,
  }));
  if ((typeof result.message_id !== 'number' && typeof result.message_id !== 'string') || !/^\d+$/.test(String(result.message_id))) {
    throw new BusinessSignalError('TELEGRAM_FAILED', 'Telegram message_id is invalid');
  }
  return BigInt(String(result.message_id));
}
