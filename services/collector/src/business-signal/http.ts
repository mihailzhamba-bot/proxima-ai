import { randomUUID } from 'node:crypto';

import { BusinessSignalRawStore } from './raw-store.js';
import { BusinessSignalError, type SignalRepository, type SignalSource } from './types.js';

export interface HttpRequest {
  method: 'GET' | 'POST';
  url: string;
  token: string;
  body?: unknown;
}

export interface HttpResponse {
  status: number;
  body: Buffer;
  retrievedAt: Date;
}

export type HttpTransport = (request: HttpRequest) => Promise<HttpResponse>;

export const fetchTransport: HttpTransport = async (request) => {
  const response = await fetch(request.url, {
    method: request.method,
    redirect: 'error',
    headers: {
      Authorization: request.token,
      'Content-Type': 'application/json',
      'User-Agent': 'proxima-ai-business-signal/1',
    },
    ...(request.body === undefined ? {} : { body: JSON.stringify(request.body) }),
    signal: AbortSignal.timeout(60_000),
  });
  return { status: response.status, body: Buffer.from(await response.arrayBuffer()), retrievedAt: new Date() };
};

export class RecordedHttpClient {
  constructor(
    private readonly runId: string,
    private readonly store: BusinessSignalRawStore,
    private readonly repository: SignalRepository,
    private readonly transport: HttpTransport = fetchTransport,
  ) {}

  async request(input: HttpRequest & { source: SignalSource; stage: string; pageSequence: number; acceptedStatuses?: number[] }): Promise<HttpResponse> {
    const endpointPath = new URL(input.url).pathname;
    const response = await this.transport(input);
    const artifact = await this.store.persist({
      runId: this.runId,
      source: input.source,
      stage: input.stage,
      pageSequence: input.pageSequence,
      endpointPath,
      httpStatus: response.status,
      retrievedAt: response.retrievedAt,
      body: response.body,
    });
    await this.repository.recordRawArtifact({
      rawArtifactId: randomUUID(),
      runId: this.runId,
      source: input.source,
      stage: input.stage,
      pageSequence: input.pageSequence,
      endpointPath,
      httpStatus: response.status,
      retrievedAt: response.retrievedAt,
      ...artifact,
    });
    const accepted = input.acceptedStatuses ?? [200];
    if (!accepted.includes(response.status)) {
      const code = response.status === 401 || response.status === 403 ? 'WB_AUTH_FAILED'
        : response.status === 429 ? 'WB_RATE_LIMITED' : 'WB_HTTP_FAILED';
      throw new BusinessSignalError(code, `${input.source}/${input.stage} returned HTTP ${response.status}`);
    }
    return response;
  }
}

export function parseJson(body: Buffer, label: string): unknown {
  try { return JSON.parse(body.toString('utf8')); } catch {
    throw new BusinessSignalError('WB_SCHEMA_DRIFT', `${label} response is not valid JSON`);
  }
}
