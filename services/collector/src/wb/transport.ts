import type { HttpTransport } from '../business-signal/http.js';

export type { HttpRequest, HttpResponse, HttpTransport } from '../business-signal/http.js';

export type WbRequestQuery = Map<string, string>;

export type WbTransport = HttpTransport;

export const RETRYABLE_STATUS = 429;

export function buildUrl(baseUrl: string, query?: WbRequestQuery): string {
  if (!query || query.size === 0) return baseUrl;
  const url = new URL(baseUrl);
  for (const [key, value] of query) url.searchParams.set(key, value);
  return url.toString();
}

/**
 * Delay WB asked us to wait before the next call, in milliseconds.
 * `X-Ratelimit-Retry` is the documented header; `X-Ratelimit-Reset` and
 * `Retry-After` are accepted as seconds-based fallbacks (see API-FACTS).
 */
export function retryDelayMilliseconds(headers: Readonly<Record<string, string>> | undefined): number | null {
  const raw = headers?.['x-ratelimit-retry'] ?? headers?.['x-ratelimit-reset'] ?? headers?.['retry-after'];
  if (raw === undefined || raw.trim() === '') return null;
  const seconds = Number(raw);
  if (!Number.isFinite(seconds) || seconds < 0) return null;
  return Math.ceil(seconds) * 1000;
}

/** Live network transport. Fail-closed outside production: AD-4 bans network in tests. */
export function networkTransport(): WbTransport {
  return async (request) => {
    if (process.env['WB_ALLOW_LIVE_NETWORK'] !== '1') {
      throw new Error(
        'WB_NETWORK_FORBIDDEN: live WB API calls are disabled (network is banned in tests, AD-4); set WB_ALLOW_LIVE_NETWORK=1 and provide tokens to allow them',
      );
    }
    const { fetchTransport } = await import('../business-signal/http.js');
    return fetchTransport(request);
  };
}
