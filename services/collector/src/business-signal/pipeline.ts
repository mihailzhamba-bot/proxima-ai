import { randomUUID } from 'node:crypto';

import { calculateCandidates, calculateMargins, selectTopRisk } from './calculate.js';
import { completedSignalWindow } from './date-window.js';
import { RecordedHttpClient, type HttpTransport } from './http.js';
import { BusinessSignalRawStore } from './raw-store.js';
import { assertLeastPrivilegeToken } from './secrets.js';
import { formatStockoutMessage, preflightAndSend, type TelegramTransport } from './telegram.js';
import { BusinessSignalError, type SignalCandidate, type SignalRepository } from './types.js';
import { WbSignalClient, type Sleep } from './wb-client.js';

export interface RunSignalInput {
  tenantId: string;
  repositoryRoot: string;
  rawRoot: string;
  statisticsToken: string;
  analyticsToken: string;
  financeToken: string;
  allowAnalyticsReadWrite?: boolean;
  now?: Date;
  send?: { telegram: TelegramTransport; founderChatId: bigint };
  httpTransport?: HttpTransport;
  sleep?: Sleep;
}

export interface RunSignalResult {
  runId: string;
  status: 'NO_SIGNAL' | 'BLOCKED' | 'READY' | 'SENT';
  reason?: string;
  candidate?: SignalCandidate;
  telegramMessageId?: bigint;
  newSkuNoHistory?: string[];
  marginMissing?: string[];
}

function safeReason(error: unknown): string {
  return error instanceof BusinessSignalError ? error.code : 'UNEXPECTED_FAILURE';
}

export async function runBusinessSignal(repository: SignalRepository, input: RunSignalInput): Promise<RunSignalResult> {
  const now = input.now ?? new Date();
  const window = completedSignalWindow(now);
  const runId = randomUUID();
  await repository.createRun(runId, input.tenantId, window);
  try {
    assertLeastPrivilegeToken(input.statisticsToken, 'statistics', now);
    assertLeastPrivilegeToken(input.analyticsToken, 'analytics', now, { allowReadWrite: input.allowAnalyticsReadWrite });
    assertLeastPrivilegeToken(input.financeToken, 'finance', now);
    const [products, warehouseMap] = await Promise.all([
      repository.loadProductConfig(input.tenantId, window.to),
      repository.loadWarehouseMap(input.tenantId, window.to),
    ]);
    if (products.length === 0) throw new BusinessSignalError('PRODUCT_CONFIG_MISSING', 'no effective dim_product rows');
    if (warehouseMap.length === 0) throw new BusinessSignalError('WAREHOUSE_MAP_MISSING', 'no effective warehouse map rows');
    const store = await BusinessSignalRawStore.open(input.rawRoot, input.repositoryRoot);
    const http = new RecordedHttpClient(runId, store, repository, input.httpTransport);
    const wb = new WbSignalClient(http, input.sleep ? { sleep: input.sleep } : {});
    const [sales, stocks, finance] = await Promise.all([
      wb.sales(input.statisticsToken, window),
      wb.stocks(input.analyticsToken, products.map((product) => product.nmId)),
      wb.finance(input.financeToken, window),
    ]);
    if (sales.length === 0) {
      throw new BusinessSignalError('WB_SALES_EMPTY', 'statistics returned no sales for an active cabinet window');
    }
    if (stocks.rows.length === 0) {
      throw new BusinessSignalError('WB_STOCKS_EMPTY', 'analytics returned no stock rows for configured products');
    }
    const margins = calculateMargins(products, finance);
    const calculation = calculateCandidates({ products, warehouseMap, sales, stocks: stocks.rows, margins, stockAsOf: stocks.asOf });
    const surfaced = { newSkuNoHistory: calculation.newSkuNoHistory, marginMissing: calculation.marginMissing };
    const candidate = selectTopRisk(calculation.candidates);
    if (!candidate) {
      await repository.completeRun(runId, 'NO_SIGNAL', 'NO_RISK');
      return { runId, status: 'NO_SIGNAL', reason: 'NO_RISK', ...surfaced };
    }
    await repository.markReady(runId, candidate);
    if (!input.send) return { runId, status: 'READY', candidate, ...surfaced };
    const attemptedAt = new Date();
    try {
      const messageId = await preflightAndSend(input.send.telegram, input.send.founderChatId, formatStockoutMessage(candidate, window));
      await repository.recordTelegramResult(runId, attemptedAt, messageId);
      return { runId, status: 'SENT', candidate, telegramMessageId: messageId, ...surfaced };
    } catch (error) {
      await repository.recordTelegramResult(runId, attemptedAt, null);
      throw error;
    }
  } catch (error) {
    const reason = safeReason(error);
    await repository.completeRun(runId, 'BLOCKED', reason);
    if (error instanceof BusinessSignalError && !input.send) return { runId, status: 'BLOCKED', reason };
    throw error;
  }
}
