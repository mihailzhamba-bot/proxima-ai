import { createHash } from 'node:crypto';

import type { WbEndpointId } from './registry.js';

export interface WbArtifact {
  readonly endpointId: WbEndpointId;
  readonly httpStatus: number;
  readonly contentSha256: string;
  readonly contentSize: number;
  readonly objectLocator: string;
  readonly retrievedAt: Date;
}

export interface WbArtifactSinkInput {
  readonly endpointId: WbEndpointId;
  readonly url: string;
  readonly httpStatus: number;
  readonly responseHeaders: Readonly<Record<string, string>>;
  readonly body: Buffer;
  readonly retrievedAt: Date;
  readonly attempt: number;
}

/**
 * Receives every raw WB response, including 4xx/5xx, before the HTTP status is
 * inspected (same order as business-signal/http.ts). The DB-backed
 * implementation (`WbArtifactSink`, CAS + `wb_raw_artifacts`) arrives in Story 1.3.
 */
export interface ArtifactSink {
  store(input: WbArtifactSinkInput): Promise<WbArtifact>;
}

/** In-memory implementation for tests; keeps only digests, never the payload. */
export class InMemoryArtifactSink implements ArtifactSink {
  readonly artifacts: WbArtifact[] = [];

  async store(input: WbArtifactSinkInput): Promise<WbArtifact> {
    const contentSha256 = createHash('sha256').update(input.body).digest('hex');
    const artifact: WbArtifact = {
      endpointId: input.endpointId,
      httpStatus: input.httpStatus,
      contentSha256,
      contentSize: input.body.length,
      objectLocator: `memory://wb/${input.endpointId}/${contentSha256}`,
      retrievedAt: input.retrievedAt,
    };
    this.artifacts.push(artifact);
    return artifact;
  }
}
