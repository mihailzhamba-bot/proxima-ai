import { readProductConfigCsv, readWarehouseMapCsv } from './config.js';
import { readFounderChatId } from './runtime.js';
import { assertLeastPrivilegeToken, readPrivateSecret } from './secrets.js';
import { BusinessSignalError } from './types.js';

export interface SignalInputPaths {
  tenantId: string;
  statisticsTokenFile: string;
  analyticsTokenFile: string;
  financeTokenFile: string;
  telegramTokenFile: string;
  founderChatSource: string;
  productsCsv: string;
  warehousesCsv: string;
  allowAnalyticsReadWrite?: boolean;
}

export interface SignalInputValidation {
  tenantId: string;
  products: number;
  warehouseMappings: number;
  wbScopes: readonly ['statistics', 'analytics', 'finance'];
  analyticsAccess: 'read-only' | 'read-write-temporary';
  telegramTokenShape: 'valid';
  founderChatSource: 'valid';
}

const TELEGRAM_TOKEN_PATTERN = /^\d{8,12}:[A-Za-z0-9_-]{30,64}$/;

export async function validateSignalInputFiles(
  paths: SignalInputPaths,
  now = new Date(),
): Promise<SignalInputValidation> {
  const [statisticsToken, analyticsToken, financeToken, telegramToken, products, warehouses] = await Promise.all([
    readPrivateSecret(paths.statisticsTokenFile, 'WB Statistics token file'),
    readPrivateSecret(paths.analyticsTokenFile, 'WB Analytics token file'),
    readPrivateSecret(paths.financeTokenFile, 'WB Finance token file'),
    readPrivateSecret(paths.telegramTokenFile, 'Telegram token file'),
    readProductConfigCsv(paths.productsCsv),
    readWarehouseMapCsv(paths.warehousesCsv),
    readFounderChatId(paths.founderChatSource),
  ]);

  assertLeastPrivilegeToken(statisticsToken, 'statistics', now);
  assertLeastPrivilegeToken(analyticsToken, 'analytics', now, { allowReadWrite: paths.allowAnalyticsReadWrite });
  assertLeastPrivilegeToken(financeToken, 'finance', now);
  if (!TELEGRAM_TOKEN_PATTERN.test(telegramToken)) {
    throw new BusinessSignalError('TELEGRAM_TOKEN_INVALID', 'Telegram token shape is invalid');
  }
  if (products.some((product) => product.tenantId !== paths.tenantId)
    || warehouses.some((warehouse) => warehouse.tenantId !== paths.tenantId)) {
    throw new BusinessSignalError('CONFIG_TENANT_MISMATCH', 'all signal config rows must match the requested tenant');
  }

  return {
    tenantId: paths.tenantId,
    products: products.length,
    warehouseMappings: warehouses.length,
    wbScopes: ['statistics', 'analytics', 'finance'],
    analyticsAccess: paths.allowAnalyticsReadWrite ? 'read-write-temporary' : 'read-only',
    telegramTokenShape: 'valid',
    founderChatSource: 'valid',
  };
}
