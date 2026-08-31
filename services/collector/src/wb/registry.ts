export type WbTokenCategory = 'statistics' | 'analytics';

export type WbEndpointId =
  | 'statistics.orders'
  | 'statistics.sales'
  | 'analytics.sales_funnel_v3_history'
  | 'analytics.nm_report_downloads';

export interface WbEndpointSpec {
  readonly id: WbEndpointId;
  readonly method: 'GET' | 'POST';
  readonly url: string;
  readonly token: WbTokenCategory;
  readonly api: 'statistics' | 'analytics';
  readonly fixtureDir: string;
  readonly limitPerMinute: number;
  readonly maxPerPage?: number;
}

export const WB_ENDPOINTS: Readonly<Record<WbEndpointId, WbEndpointSpec>> = {
  'statistics.orders': {
    id: 'statistics.orders',
    method: 'GET',
    url: 'https://statistics-api.wildberries.ru/api/v1/supplier/orders',
    token: 'statistics',
    api: 'statistics',
    fixtureDir: 'statistics/orders',
    limitPerMinute: 10,
  },
  'statistics.sales': {
    id: 'statistics.sales',
    method: 'GET',
    url: 'https://statistics-api.wildberries.ru/api/v1/supplier/sales',
    token: 'statistics',
    api: 'statistics',
    fixtureDir: 'statistics/sales',
    limitPerMinute: 1,
  },
  'analytics.sales_funnel_v3_history': {
    id: 'analytics.sales_funnel_v3_history',
    method: 'POST',
    url: 'https://seller-analytics-api.wildberries.ru/api/analytics/v3/sales-funnel/products/history',
    token: 'analytics',
    api: 'analytics',
    fixtureDir: 'analytics/sales_funnel_v3_history',
    limitPerMinute: 3,
    maxPerPage: 20,
  },
  'analytics.nm_report_downloads': {
    id: 'analytics.nm_report_downloads',
    method: 'GET',
    url: 'https://seller-analytics-api.wildberries.ru/api/v2/nm-report/downloads',
    token: 'analytics',
    api: 'analytics',
    fixtureDir: 'analytics/nm_report_downloads',
    limitPerMinute: 3,
  },
};

export const WB_ENDPOINT_LIST: readonly WbEndpointSpec[] = Object.values(WB_ENDPOINTS);

export function wbEndpoint(id: WbEndpointId): WbEndpointSpec {
  const spec = WB_ENDPOINTS[id];
  if (!spec) throw new Error(`unknown WB endpoint ${id}`);
  return spec;
}

export function endpointLimit(endpointId: string): number {
  const spec = WB_ENDPOINTS[endpointId as WbEndpointId];
  return spec ? spec.limitPerMinute : 0;
}
