import { readFile } from 'node:fs/promises';
import { join, resolve } from 'node:path';

import type { HttpRequest, HttpResponse } from '../business-signal/http.js';
import type { WbTransport } from './transport.js';
import { WB_ENDPOINTS } from './registry.js';

export const DEFAULT_FIXTURE_ROOT = resolve(import.meta.dirname, '../../tests/fixtures/wb-api');

export interface FixtureScript {
  /**
   * Response the scripted call returns. The body is served verbatim; statuses
   * other than 200 (e.g. 429 drills) are allowed so tests can rehearse the
   * retry path without touching the network.
   */
  readonly status: number;
  readonly body?: string | Buffer;
  readonly headers?: Record<string, string>;
}

export interface FixtureTransportOptions {
  /** Directory holding `<api>/<endpoint>/*.json` (default: collector tests fixtures). */
  readonly root?: string;
  /** Injectable scripted responses keyed by endpoint id, consumed before fixture files. */
  readonly scripts?: Readonly<Partial<Record<keyof typeof WB_ENDPOINTS, readonly FixtureScript[]>>>;
  readonly now?: () => Date;
}

const ALLOWED_FIXTURE_STATUSES = new Set([200, 400, 401, 403, 404, 429]);

/**
 * Replay transport for tests (AD-4: no network). Maps a registry endpoint to
 * `tests/fixtures/wb-api/<api>/<endpoint>/sample.json` - the anonymized raw WB
 * response - and synthesizes HTTP 200 with exactly that body. Scenario drills
 * (429, ...) come from injectable scripts, never from invented fixture files.
 */
export class FixtureTransport {
  private readonly root: string;
  private readonly scripts: Readonly<FixtureTransportOptions['scripts']>;
  private readonly now: () => Date;
  private readonly cursor = new Map<string, number>();
  private readonly requests: HttpRequest[] = [];
  private readonly fileHits = new Set<string>();

  constructor(options: FixtureTransportOptions = {}) {
    this.root = options.root ?? DEFAULT_FIXTURE_ROOT;
    this.scripts = options.scripts ?? {};
    this.now = options.now ?? (() => new Date());
  }

  get transport(): WbTransport {
    return async (request) => this.handle(request);
  }

  recordedRequests(): readonly HttpRequest[] {
    return [...this.requests];
  }

  /** Endpoint ids whose fixture file was actually read at least once. */
  fixtureEndpointsUsed(): readonly string[] {
    return [...this.fileHits];
  }

  private async handle(request: HttpRequest): Promise<HttpResponse> {
    this.requests.push(request);
    const endpointId = this.endpointIdFor(request);
    if (!endpointId) {
      throw new Error(`FixtureTransport: request URL ${request.url} is not a WB registry endpoint`);
    }
    const scripted = this.nextScript(endpointId);
    if (scripted) {
      return {
        status: scripted.status,
        body: typeof scripted.body === 'string' ? Buffer.from(scripted.body, 'utf8') : scripted.body ?? Buffer.alloc(0),
        retrievedAt: this.now(),
        ...(scripted.headers ? { headers: scripted.headers } : {}),
      };
    }
    const spec = WB_ENDPOINTS[endpointId];
    const body = await readFile(join(this.root, spec.fixtureDir, 'sample.json'));
    this.fileHits.add(endpointId);
    return {
      status: 200,
      body,
      retrievedAt: this.now(),
      headers: { 'content-type': 'application/json' },
    };
  }

  private nextScript(endpointId: string): FixtureScript | undefined {
    const queue = this.scripts?.[endpointId as keyof typeof WB_ENDPOINTS];
    if (!queue || queue.length === 0) return undefined;
    const index = this.cursor.get(endpointId) ?? 0;
    const script = queue[index];
    this.cursor.set(endpointId, index + 1);
    if (script !== undefined && !ALLOWED_FIXTURE_STATUSES.has(script.status)) {
      throw new Error(`FixtureTransport: scripted status ${script.status} is not an allowed WB response rehearsal`);
    }
    return script;
  }

  private endpointIdFor(request: HttpRequest): keyof typeof WB_ENDPOINTS | undefined {
    const requestUrl = new URL(request.url);
    return (Object.keys(WB_ENDPOINTS) as (keyof typeof WB_ENDPOINTS)[]).find((id) => {
      const spec = WB_ENDPOINTS[id];
      const candidate = new URL(spec.url);
      return requestUrl.origin === candidate.origin && requestUrl.pathname === candidate.pathname;
    });
  }
}
