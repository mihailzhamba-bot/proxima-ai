import { Decimal } from 'decimal.js';

import type { ProductConfig, SignalCandidate, WarehouseMap } from './types.js';
import { BusinessSignalError, SIGNAL_WINDOW_DAYS } from './types.js';
import type { WbFinanceRow, WbSale, WbStock } from './wb-client.js';

export function normalizeWarehouse(value: string): string {
  return value.normalize('NFKC').trim().replace(/\s+/g, ' ').toLocaleLowerCase('ru-RU');
}

function decimal(value: string, field: string): Decimal {
  let result: Decimal;
  try { result = new Decimal(value); } catch { throw new BusinessSignalError('WB_SCHEMA_DRIFT', `${field} is not a decimal`); }
  if (!result.isFinite()) throw new BusinessSignalError('WB_SCHEMA_DRIFT', `${field} is not finite`);
  return result;
}

export function calculateMargins(products: ProductConfig[], rows: WbFinanceRow[]): Map<bigint, Decimal> {
  const result = new Map<bigint, Decimal>();
  for (const product of products) {
    const skuRows = rows.filter((row) => row.nmId === product.nmId);
    const sales = skuRows.filter((row) => row.docTypeName === 'Продажа');
    if (sales.length === 0) continue;
    const soldUnits = sales.reduce((sum, row) => sum.plus(decimal(row.quantity, 'quantity')), new Decimal(0));
    if (!soldUnits.isPositive()) throw new BusinessSignalError('WB_SCHEMA_DRIFT', 'finance sold quantity must be positive');
    const price = sales.reduce((sum, row) => sum.plus(decimal(row.retailPriceWithDisc, 'retailPriceWithDisc').times(decimal(row.quantity, 'quantity'))), new Decimal(0)).div(soldUnits);
    const commission = sales.reduce((sum, row) => sum.plus(decimal(row.ppvzSalesCommission, 'ppvzSalesCommission').times(decimal(row.quantity, 'quantity'))), new Decimal(0)).div(soldUnits);
    const logistics = skuRows.reduce((sum, row) => sum.plus(decimal(row.deliveryService, 'deliveryService')), new Decimal(0)).div(soldUnits);
    result.set(product.nmId, price.minus(commission).minus(logistics).minus(product.cogsRub).toDecimalPlaces(2));
  }
  return result;
}

export function calculateCandidates(input: {
  products: ProductConfig[];
  warehouseMap: WarehouseMap[];
  sales: WbSale[];
  stocks: WbStock[];
  margins: Map<bigint, Decimal>;
  stockAsOf: Date;
}): SignalCandidate[] {
  const productById = new Map(input.products.map((product) => [product.nmId, product]));
  const salesAlias = new Map<string, string>();
  const stockAlias = new Map<string, string>();
  for (const mapping of input.warehouseMap) {
    const salesKey = normalizeWarehouse(mapping.salesWarehouseName);
    const stockKey = normalizeWarehouse(mapping.stockWarehouseName);
    if (salesAlias.has(salesKey) || stockAlias.has(stockKey)) throw new BusinessSignalError('WAREHOUSE_MAP_AMBIGUOUS', 'warehouse mapping has duplicate normalized aliases');
    salesAlias.set(salesKey, mapping.canonicalWarehouse);
    stockAlias.set(stockKey, mapping.canonicalWarehouse);
  }
  const netSales = new Map<string, number>();
  for (const sale of input.sales.filter((row) => productById.has(row.nmId))) {
    const warehouse = salesAlias.get(normalizeWarehouse(sale.warehouseName));
    if (!warehouse) throw new BusinessSignalError('WAREHOUSE_MAP_MISSING', `sales warehouse is not mapped: ${sale.warehouseName}`);
    const key = `${sale.nmId}:${warehouse}`;
    netSales.set(key, (netSales.get(key) ?? 0) + (sale.kind === 'sale' ? 1 : -1));
  }
  const stockByKey = new Map<string, number>();
  for (const stock of input.stocks.filter((row) => productById.has(row.nmId))) {
    const warehouse = stockAlias.get(normalizeWarehouse(stock.warehouseName));
    if (!warehouse) throw new BusinessSignalError('WAREHOUSE_MAP_MISSING', `stock warehouse is not mapped: ${stock.warehouseName}`);
    const key = `${stock.nmId}:${warehouse}`;
    stockByKey.set(key, (stockByKey.get(key) ?? 0) + stock.quantity);
  }
  const candidates: SignalCandidate[] = [];
  for (const [key, units] of netSales) {
    if (units <= 0) continue;
    const delimiter = key.indexOf(':');
    const nmId = BigInt(key.slice(0, delimiter));
    const warehouse = key.slice(delimiter + 1);
    const product = productById.get(nmId);
    const margin = input.margins.get(nmId);
    if (!product || !margin) throw new BusinessSignalError('MARGIN_MISSING', `margin is unavailable for nmId ${nmId}`);
    const velocity = new Decimal(units).div(SIGNAL_WINDOW_DAYS);
    const stockQuantity = stockByKey.get(key) ?? 0;
    const daysCover = new Decimal(stockQuantity).div(velocity).floor().toNumber();
    const thresholdDays = product.leadTimeDays + product.safetyBufferDays;
    if (daysCover <= thresholdDays) {
      candidates.push({
        nmId,
        internalArticle: product.internalArticle,
        warehouse,
        stockQuantity,
        velocityUnitsPerDay: velocity,
        daysCover,
        leadTimeDays: product.leadTimeDays,
        safetyBufferDays: product.safetyBufferDays,
        thresholdDays,
        marginPerUnitRub: margin,
        stockAsOf: input.stockAsOf,
      });
    }
  }
  return candidates;
}

export function selectTopRisk(candidates: SignalCandidate[]): SignalCandidate | undefined {
  return [...candidates].sort((left, right) => {
    const deficit = (right.thresholdDays - right.daysCover) - (left.thresholdDays - left.daysCover);
    if (deficit !== 0) return deficit;
    if (left.daysCover !== right.daysCover) return left.daysCover - right.daysCover;
    if (left.nmId !== right.nmId) return left.nmId < right.nmId ? -1 : 1;
    return left.warehouse.localeCompare(right.warehouse, 'ru');
  })[0];
}
