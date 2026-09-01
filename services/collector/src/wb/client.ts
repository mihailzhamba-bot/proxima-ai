import { throwIfAborted } from '../business-signal/cancellation.js';
import { filterResponseHeaders } from '../business-signal/http.js';
import type { WbEndpointSpec, WbTokenCategory } from './registry.js';
import { endpointLimit, WB_ENDPOINTS } from './registry.js';
import type { ArtifactSink } from './artifact-sink.js';
import { buildUrl, networkTransport, RETRYABLE_STATUS, retryDelayMilliseconds, type WbRequestQuery, type WbTransport } from './transport.js';

export const MAX_RETRIES_AFTER_RATE_LIMIT = 3;

export type WbClientErrorCode =
  | 'WB_ENDPOINT_UNKNOWN'
  | 'WB_TOKEN_NOT_CONFIGURED'
  | 'WB_RATE_LIMIT_EXHAUSTED'
  | 'WB_AUTH_FAILED'
  | 'WB_HTTP_FAILED'
  | 'WB_SCHEMA_DRIFT'
  | 'CANCELLED';

export class WbClientError extends Error {
  constructor(
    readonly code: WbClientErrorCode,
    message: string,
    readonly endpointId?: WbEndpointSpec['id'],
    readonly httpStatus?: number,
  ) {
    super(message);
    this.name = 'WbClientError';
  }
}

export interface Clock {
  now(): number;
  sleep(milliseconds: number, signal?: AbortSignal): Promise<void>;
}

export const wallClock: Clock = {
  now: () => Date.now(),
  sleep: (milliseconds, signal) => sleepMilliseconds(milliseconds, signal),
};

function sleepMilliseconds(milliseconds: number, signal?: AbortSignal): Promise<void> {
  throwIfAborted(signal);
  if (milliseconds <= 0) return Promise.resolve();
  return new Promise<void>((resolve, reject) => {
    const timer = setTimeout(() => { signal?.removeEventListener('abort', onAbort); resolve(); }, milliseconds);
    const onAbort = (): void => { clearTimeout(timer); reject(abortError(signal as AbortSignal)); };
    signal?.addEventListener('abort', onAbort, { once: true });
  });
}

function abortError(signal: AbortSignal): Error {
  return signal.reason instanceof Error ? signal.reason : new WbClientError('CANCELLED', 'WB client run cancelled');
}

/**
 * Client-side fixed-window budget per endpoint (`limitPerMinute` from the
 * registry). Every `reserve()` books exactly one slot atomically: a window
 * holds at most `limit` reservations, and callers that arrive while a future
 * window is being booked join that window instead of sneaking into the past.
 */
export class RateBudget {
  private readonly windowStartAt = new Map<string, number>();
  private readonly reservedInWindow = new Map<string, number>();

  constructor(
    private readonly limitFor: (endpointId: string) => number = endpointLimit,
    private readonly now: () => number = () => Date.now(),
  ) {}

  earliestAllowedAt(endpointId: string): number {
    const start = this.windowStartAt.get(endpointId);
    const reserved = this.reservedInWindow.get(endpointId) ?? 0;
    if (start === undefined || reserved < this.limitFor(endpointId)) return this.now();
    return start + 60_000;
  }

  /**
   * Books the next free slot and returns how long the caller must wait
   * before sending. The booking is synchronous, so concurrent callers can
   * never be handed the same slot or a slot inside an already full window.
   */
  reserve(endpointId: string): number {
    const limit = this.limitFor(endpointId);
    if (!Number.isSafeInteger(limit) || limit < 1) {
      throw new WbClientError('WB_ENDPOINT_UNKNOWN', `no rate budget for endpoint ${endpointId}`, endpointId as WbEndpointSpec['id']);
    }
    const windowMs = 60_000;
    const current = this.now();
    const start = this.windowStartAt.get(endpointId) ?? current;
    const reserved = this.reservedInWindow.get(endpointId) ?? 0;

    if (current >= start + windowMs) {
      // The tracked window is stale: nothing was booked into it recently.
      this.windowStartAt.set(endpointId, current);
      this.reservedInWindow.set(endpointId, 1);
      return 0;
    }
    if (current < start) {
      // A future window is already taking reservations for this endpoint.
      if (reserved < limit) {
        this.reservedInWindow.set(endpointId, reserved + 1);
      } else {
        this.windowStartAt.set(endpointId, start + windowMs);
        this.reservedInWindow.set(endpointId, 1);
      }
      return this.windowStartAt.get(endpointId)! - current;
    }
    if (reserved < limit) {
      this.reservedInWindow.set(endpointId, reserved + 1);
      return 0;
    }
    this.windowStartAt.set(endpointId, start + windowMs);
    this.reservedInWindow.set(endpointId, 1);
    return start + windowMs - current;
  }
}

export const MIN_RETRY_DELAY_MILLISECONDS = 1_000;

/**
 * Conservative wait for a 429 that came without any retry hint: one pacing
 * interval of the endpoint's own budget, floored at one second, so a missing
 * header can never turn into a hot retry loop.
 */
export function fallbackRetryDelayMilliseconds(limitPerMinute: number): number {
  const limit = Number.isSafeInteger(limitPerMinute) && limitPerMinute > 0 ? limitPerMinute : 1;
  return Math.max(MIN_RETRY_DELAY_MILLISECONDS, Math.ceil(60_000 / limit));
}

export interface WbClientOptions {
  readonly transport?: WbTransport;
  readonly clock?: Clock;
  readonly artifactSink?: ArtifactSink;
  readonly signal?: AbortSignal;
  readonly maxRetries?: number;
}

export interface WbResponseRecord {
  readonly endpointId: WbEndpointSpec['id'];
  readonly requestUrl: string;
  readonly httpStatus: number;
  readonly responseHeaders: Record<string, string>;
  readonly body: Buffer;
  readonly retrievedAt: Date;
}

/**
 * The only WB HTTP client (AD-4). URLs come from the registry, the per-endpoint
 * budget is enforced before every call, a 429 waits `X-Ratelimit-Retry` seconds
 * and gives up after 3 retries, and every response reaches the artifact sink
 * before its status is inspected.
 */
export class WbClient {
  private readonly transport: WbTransport;
  private readonly clock: Clock;
  private readonly budget: RateBudget;
  private readonly sink: ArtifactSink | undefined;
  private readonly signal: AbortSignal | undefined;
  private readonly maxRetries: number;
  private readonly tokens: Readonly<Partial<Record<WbTokenCategory, string>>>;

  constructor(tokens: Readonly<Partial<Record<WbTokenCategory, string>>>, options: WbClientOptions = {}) {
    this.transport = options.transport ?? networkTransport();
    this.clock = options.clock ?? wallClock;
    this.budget = new RateBudget(endpointLimit, this.clock.now.bind(this.clock));
    this.sink = options.artifactSink;
    this.signal = options.signal;
    this.maxRetries = options.maxRetries ?? MAX_RETRIES_AFTER_RATE_LIMIT;
    this.tokens = tokens;
  }

  async request(
    endpointId: WbEndpointSpec['id'],
    input: { query?: WbRequestQuery; body?: unknown } = {},
  ): Promise<WbResponseRecord> {
    const spec = WB_ENDPOINTS[endpointId];
    if (!spec) throw new WbClientError('WB_ENDPOINT_UNKNOWN', `unknown WB endpoint ${String(endpointId)}`);
    throwIfAborted(this.signal);

    let attempt = 0;
    for (;;) {
      const delay = this.budget.reserve(spec.id);
      if (delay > 0) await this.clock.sleep(delay, this.signal);
      throwIfAborted(this.signal);

      const token = this.tokens[spec.token];
      if (typeof token !== 'string' || token.length === 0) {
        throw new WbClientError(
          'WB_TOKEN_NOT_CONFIGURED',
          `WB ${spec.token} token is not configured; live calls require --${spec.token}-token-file`,
          spec.id,
        );
      }

      const url = buildUrl(spec.url, input.query);
      const response = await this.transport({
        method: spec.method,
        url,
        token,
        ...(input.body === undefined ? {} : { body: input.body }),
        ...(this.signal === undefined ? {} : { signal: this.signal }),
      });
      const responseHeaders = filterResponseHeaders(Object.entries(response.headers ?? {}));
      const retrievedAt = response.retrievedAt ?? new Date(this.clock.now());
      if (this.sink) {
        await this.sink.store({ endpointId: spec.id, url, httpStatus: response.status, responseHeaders, body: response.body, retrievedAt, attempt });
      }

      if (response.status === RETRYABLE_STATUS) {
        if (attempt >= this.maxRetries) {
          throw new WbClientError('WB_RATE_LIMIT_EXHAUSTED', `${spec.id} still rate limited after ${attempt} retries`, spec.id, response.status);
        }
        attempt += 1;
        const hinted = retryDelayMilliseconds(responseHeaders);
        const delay = hinted ?? fallbackRetryDelayMilliseconds(spec.limitPerMinute);
        await this.clock.sleep(delay, this.signal);
        continue;
      }

      if (response.status !== 200) {
        const code = response.status === 401 || response.status === 403 ? 'WB_AUTH_FAILED' : 'WB_HTTP_FAILED';
        throw new WbClientError(code, `${spec.id} returned HTTP ${response.status}`, spec.id, response.status);
      }
      return { endpointId: spec.id, requestUrl: url, httpStatus: response.status, responseHeaders, body: response.body, retrievedAt };
    }
  }
}

export function parseJsonArray(body: Buffer, endpointId: WbEndpointSpec['id']): unknown[] {
  let parsed: unknown;
  try {
    parsed = JSON.parse(body.toString('utf8'));
  } catch {
    throw new WbClientError('WB_SCHEMA_DRIFT', `${endpointId} response is not valid JSON`, endpointId);
  }
  if (!Array.isArray(parsed)) {
    throw new WbClientError('WB_SCHEMA_DRIFT', `${endpointId} response must be a JSON array`, endpointId);
  }
  return parsed;
}
