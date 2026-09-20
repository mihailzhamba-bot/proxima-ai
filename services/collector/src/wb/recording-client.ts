import { randomUUID } from 'node:crypto';

import type { Pool } from 'pg';

import { BusinessSignalRawStore } from '../business-signal/raw-store.js';
import { filterResponseHeaders } from '../business-signal/http.js';
import type { SignalSource } from '../business-signal/types.js';
import type { ArtifactSink, WbArtifact, WbArtifactSinkInput } from './artifact-sink.js';
import { wbEndpoint } from './registry.js';

export class WbArtifactSink implements ArtifactSink {
  constructor(private readonly tenantId: string, private readonly runId: string, private readonly rawStore: BusinessSignalRawStore, private readonly pool: Pool) {}

  async store(input: WbArtifactSinkInput): Promise<WbArtifact> {
    const responseHeaders = filterResponseHeaders(Object.entries(input.responseHeaders));
    const endpointPath = new URL(input.url).pathname;
    const source = `official_wb_${wbEndpoint(input.endpointId).token}` as SignalSource;
    const raw = await this.rawStore.persist({
      runId: this.runId, source, stage: input.endpointId, pageSequence: input.sequence,
      endpointPath, httpStatus: input.httpStatus, retrievedAt: input.retrievedAt, responseHeaders, body: input.body,
    });
    const client = await this.pool.connect();
    try {
      await client.query("SELECT set_config('proxima.tenant_id', $1, false)", [this.tenantId]);
      await client.query(
        'INSERT INTO wb_raw_artifacts (artifact_id, tenant_id, run_id, endpoint_id, endpoint_path, http_status, response_headers, content_sha256, content_size, object_locator, manifest_sha256, retrieved_at, attempt) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)',
        [randomUUID(), this.tenantId, this.runId, input.endpointId, endpointPath, input.httpStatus, JSON.stringify(responseHeaders), raw.contentSha256, raw.contentSize, raw.objectLocator, raw.manifestSha256, input.retrievedAt, input.sequence],
      );
    } finally {
      try {
        await client.query('RESET proxima.tenant_id');
        client.release();
      } catch (error) {
        client.release(error as Error);
        throw error;
      }
    }
    return { endpointId: input.endpointId, httpStatus: input.httpStatus, contentSha256: raw.contentSha256, contentSize: raw.contentSize, objectLocator: raw.objectLocator, retrievedAt: input.retrievedAt };
  }
}
