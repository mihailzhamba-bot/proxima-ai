import { RecordedHttpClient, parseJson } from './http.js';
import { BusinessSignalError, type SignalWindow } from './types.js';
import { isInsideWindow, moscowWindowBounds } from './date-window.js';

const SALES_PAGE_LIMIT = 80_000;
const STOCK_PAGE_LIMIT = 250_000;
const FINANCE_PAGE_LIMIT = 100_000;
const MAX_PAGES = 100;
const STATISTICS_PAGE_INTERVAL_MS = 60_000;
const ANALYTICS_PAGE_INTERVAL_MS = 20_000;
const FINANCE_PAGE_INTERVAL_MS = 60_000;
const FINANCE_FIELDS = [
  'rrdId',
  'nmId',
  'docTypeName',
  'quantity',
  'retailPriceWithDisc',
  'ppvzSalesCommission',
  'deliveryService',
] as const;

export type Sleep = (milliseconds: number) => Promise<void>;
const realSleep: Sleep = async (milliseconds) => new Promise((resolve) => setTimeout(resolve, milliseconds));

export interface WbSignalClientOptions {
  sleep?: Sleep;
  salesPageLimit?: number;
  stockPageLimit?: number;
  financePageLimit?: number;
}

function objectRow(value: unknown, label: string): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new BusinessSignalError('WB_SCHEMA_DRIFT', `${label} row must be an object`);
  return value as Record<string, unknown>;
}

function positiveInteger(value: unknown, field: string): bigint {
  if ((typeof value !== 'number' && typeof value !== 'string') || !/^\d+$/.test(String(value)) || BigInt(String(value)) <= 0n) {
    throw new BusinessSignalError('WB_SCHEMA_DRIFT', `${field} must be a positive integer`);
  }
  return BigInt(String(value));
}

function nonNegativeInteger(value: unknown, field: string): number {
  if (typeof value !== 'number' || !Number.isSafeInteger(value) || value < 0) throw new BusinessSignalError('WB_SCHEMA_DRIFT', `${field} must be a non-negative integer`);
  return value;
}

function jsonInteger(value: bigint, field: string): number {
  const result = Number(value);
  if (!Number.isSafeInteger(result)) throw new BusinessSignalError('WB_SCHEMA_DRIFT', `${field} exceeds safe JSON integer range`);
  return result;
}

function text(value: unknown, field: string): string {
  if (typeof value !== 'string' || !value.trim()) throw new BusinessSignalError('WB_SCHEMA_DRIFT', `${field} must be non-empty text`);
  return value;
}

function stringValue(value: unknown, field: string): string {
  if (typeof value !== 'string') throw new BusinessSignalError('WB_SCHEMA_DRIFT', `${field} must be text`);
  return value;
}

export interface WbSale {
  saleId: string;
  kind: 'sale' | 'return';
  date: string;
  lastChangeDate: string;
  nmId: bigint;
  warehouseName: string;
}

export interface WbStock {
  nmId: bigint;
  warehouseName: string;
  quantity: number;
}

export interface WbFinanceRow {
  nmId: bigint;
  docTypeName: string;
  quantity: string;
  retailPriceWithDisc: string;
  ppvzSalesCommission: string;
  deliveryService: string;
  rrdId: bigint;
}

export class WbSignalClient {
  private readonly sleep: Sleep;
  private readonly salesPageLimit: number;
  private readonly stockPageLimit: number;
  private readonly financePageLimit: number;

  constructor(private readonly http: RecordedHttpClient, options: WbSignalClientOptions = {}) {
    this.sleep = options.sleep ?? realSleep;
    this.salesPageLimit = options.salesPageLimit ?? SALES_PAGE_LIMIT;
    this.stockPageLimit = options.stockPageLimit ?? STOCK_PAGE_LIMIT;
    this.financePageLimit = options.financePageLimit ?? FINANCE_PAGE_LIMIT;
  }

  async sales(token: string, window: SignalWindow): Promise<WbSale[]> {
    const rows = new Map<string, WbSale>();
    let cursor = moscowWindowBounds(window).from;
    for (let page = 0; page < MAX_PAGES; page += 1) {
      if (page > 0) await this.sleep(STATISTICS_PAGE_INTERVAL_MS);
      const url = new URL('https://statistics-api.wildberries.ru/api/v1/supplier/sales');
      url.searchParams.set('dateFrom', cursor);
      url.searchParams.set('flag', '0');
      const response = await this.http.request({ method: 'GET', url: url.toString(), token, source: 'official_wb_statistics', stage: 'sales', pageSequence: page });
      const payload = parseJson(response.body, 'sales');
      if (!Array.isArray(payload)) throw new BusinessSignalError('WB_SCHEMA_DRIFT', 'sales response must be an array');
      const pageRows = payload.map((value) => {
        const row = objectRow(value, 'sales');
        const saleId = text(row.saleID, 'saleID');
        const prefix = saleId[0];
        if (prefix !== 'S' && prefix !== 'R') throw new BusinessSignalError('WB_UNKNOWN_SALE_KIND', 'saleID has an unknown sale/return prefix');
        const date = text(row.date, 'date');
        const lastChangeDate = text(row.lastChangeDate, 'lastChangeDate');
        if (Number.isNaN(Date.parse(date)) || Number.isNaN(Date.parse(lastChangeDate))) throw new BusinessSignalError('WB_SCHEMA_DRIFT', 'sales dates are invalid');
        return {
          saleId,
          kind: prefix === 'S' ? 'sale' as const : 'return' as const,
          date,
          lastChangeDate,
          nmId: positiveInteger(row.nmId, 'nmId'),
          warehouseName: text(row.warehouseName, 'warehouseName'),
        };
      });
      for (const row of pageRows.filter((candidate) => isInsideWindow(candidate.date, window))) {
        const existing = rows.get(row.saleId);
        if (existing && JSON.stringify({ ...existing, nmId: existing.nmId.toString() }) !== JSON.stringify({ ...row, nmId: row.nmId.toString() })) {
          throw new BusinessSignalError('WB_SCHEMA_DRIFT', `saleID ${row.saleId} changed inside one collection`);
        }
        rows.set(row.saleId, row);
      }
      if (pageRows.length < this.salesPageLimit) return [...rows.values()];
      const next = pageRows.at(-1)?.lastChangeDate;
      if (!next || new Date(next).getTime() <= new Date(cursor).getTime()) throw new BusinessSignalError('WB_INCOMPLETE_PAGINATION', 'sales pagination cursor did not advance');
      cursor = next;
    }
    throw new BusinessSignalError('WB_INCOMPLETE_PAGINATION', 'sales pagination exceeded the safe page limit');
  }

  async stocks(token: string, nmIds: bigint[]): Promise<{ rows: WbStock[]; asOf: Date }> {
    const rows: WbStock[] = [];
    let latest = new Date(0);
    for (let page = 0; page < MAX_PAGES; page += 1) {
      if (page > 0) await this.sleep(ANALYTICS_PAGE_INTERVAL_MS);
      const offset = page * this.stockPageLimit;
      const response = await this.http.request({
        method: 'POST',
        url: 'https://seller-analytics-api.wildberries.ru/api/analytics/v1/stocks-report/wb-warehouses',
        token,
        source: 'official_wb_analytics',
        stage: 'stocks',
        pageSequence: page,
        body: { params: { nmIDs: nmIds.map((value) => jsonInteger(value, 'nmId')), limit: this.stockPageLimit, offset } },
      });
      latest = response.retrievedAt > latest ? response.retrievedAt : latest;
      const payload = objectRow(parseJson(response.body, 'stocks'), 'stocks');
      const data = objectRow(payload.data, 'stocks.data');
      if (!Array.isArray(data.items)) throw new BusinessSignalError('WB_SCHEMA_DRIFT', 'stocks.data.items must be an array');
      const pageRows = data.items.map((value) => {
        const row = objectRow(value, 'stocks');
        return {
          nmId: positiveInteger(row.nmId, 'nmId'),
          warehouseName: text(row.warehouseName, 'warehouseName'),
          quantity: nonNegativeInteger(row.quantity, 'quantity'),
        };
      });
      rows.push(...pageRows);
      if (pageRows.length < this.stockPageLimit) return { rows, asOf: latest };
    }
    throw new BusinessSignalError('WB_INCOMPLETE_PAGINATION', 'stock pagination exceeded the safe page limit');
  }

  async finance(token: string, window: SignalWindow): Promise<WbFinanceRow[]> {
    const rows: WbFinanceRow[] = [];
    let rrdId = 0n;
    const bounds = moscowWindowBounds(window);
    for (let page = 0; page < MAX_PAGES; page += 1) {
      if (page > 0) await this.sleep(FINANCE_PAGE_INTERVAL_MS);
      const response = await this.http.request({
        method: 'POST',
        url: 'https://finance-api.wildberries.ru/api/finance/v1/sales-reports/detailed',
        token,
        source: 'official_wb_finance',
        stage: 'sales_report_detailed',
        pageSequence: page,
        acceptedStatuses: [200, 204],
        body: {
          dateFrom: bounds.from,
          dateTo: bounds.to,
          limit: this.financePageLimit,
          rrdId: jsonInteger(rrdId, 'rrdId'),
          fields: FINANCE_FIELDS,
        },
      });
      if (response.status === 204) return rows;
      const payload = parseJson(response.body, 'finance');
      if (!Array.isArray(payload)) throw new BusinessSignalError('WB_SCHEMA_DRIFT', 'finance response must be an array');
      if (payload.length === 0) throw new BusinessSignalError('WB_INCOMPLETE_PAGINATION', 'finance must terminate with HTTP 204');
      const pageRows = payload.map((value) => {
        const row = objectRow(value, 'finance');
        return {
          nmId: positiveInteger(row.nmId, 'nmId'),
          docTypeName: stringValue(row.docTypeName, 'docTypeName'),
          quantity: text(String(row.quantity), 'quantity'),
          retailPriceWithDisc: text(row.retailPriceWithDisc, 'retailPriceWithDisc'),
          ppvzSalesCommission: text(row.ppvzSalesCommission, 'ppvzSalesCommission'),
          deliveryService: text(row.deliveryService, 'deliveryService'),
          rrdId: positiveInteger(row.rrdId, 'rrdId'),
        };
      });
      rows.push(...pageRows);
      const next = pageRows.at(-1)?.rrdId;
      if (!next || next <= rrdId) throw new BusinessSignalError('WB_INCOMPLETE_PAGINATION', 'finance pagination cursor did not advance');
      rrdId = next;
    }
    throw new BusinessSignalError('WB_INCOMPLETE_PAGINATION', 'finance pagination exceeded the safe page limit');
  }
}
