import { createHash } from 'node:crypto';
import { readFile } from 'node:fs/promises';
import { createRequire } from 'node:module';
import { resolve } from 'node:path';

import { Ajv2020 } from 'ajv/dist/2020.js';

import {
  IntakeError,
  MANUAL_EXPORT_RETRIEVAL_MODE,
  OFFICIAL_WB_MANUAL_SOURCE,
  UNPARSED_PARSER_VERSION,
  type ManualWbXlsxMetadata,
  type SourceArtifactManifest,
} from './types.js';

const ID_PATTERN = /^[a-z0-9][a-z0-9._:-]{7,127}$/;
const TENANT_PATTERN = /^[a-z0-9][a-z0-9_-]{2,63}$/;
const DATASET_PATTERN = /^[a-z][a-z0-9_]{2,63}$/;
const SHA256_PATTERN = /^[0-9a-f]{64}$/;
const ISO_DATE_PATTERN = /^\d{4}-\d{2}-\d{2}$/;
const require = createRequire(import.meta.url);
const addFormats = require('ajv-formats') as typeof import('ajv-formats').default;

function canonicalize(value: unknown): string {
  if (value === null || typeof value !== 'object') return JSON.stringify(value);
  if (Array.isArray(value)) return `[${value.map(canonicalize).join(',')}]`;
  const record = value as Record<string, unknown>;
  return `{${Object.keys(record).sort().map((key) => `${JSON.stringify(key)}:${canonicalize(record[key])}`).join(',')}}`;
}

export function canonicalJson(value: unknown): string {
  return canonicalize(value);
}

export function sha256(value: string | Buffer): string {
  return createHash('sha256').update(value).digest('hex');
}

function isIsoDate(value: string): boolean {
  if (!ISO_DATE_PATTERN.test(value)) return false;
  const parsed = new Date(`${value}T00:00:00.000Z`);
  return !Number.isNaN(parsed.getTime()) && parsed.toISOString().startsWith(value);
}

function isIsoDateTime(value: string): boolean {
  if (!/^\d{4}-\d{2}-\d{2}T.*(?:Z|[+-]\d{2}:\d{2})$/.test(value) || !isIsoDate(value.slice(0, 10))) return false;
  return !Number.isNaN(new Date(value).getTime());
}

export function assertManualWbXlsxMetadata(metadata: ManualWbXlsxMetadata): void {
  if (!TENANT_PATTERN.test(metadata.tenantId)) throw new IntakeError('METADATA_INVALID', 'tenant ID is invalid');
  if (!DATASET_PATTERN.test(metadata.dataset)) throw new IntakeError('METADATA_INVALID', 'dataset is invalid');
  if (!isIsoDate(metadata.periodFrom) || !isIsoDate(metadata.periodTo) || metadata.periodFrom > metadata.periodTo) {
    throw new IntakeError('METADATA_INVALID', 'period is invalid');
  }
  if (!isIsoDateTime(metadata.dataAsOf) || !isIsoDateTime(metadata.retrievedAt)) {
    throw new IntakeError('METADATA_INVALID', 'date-time metadata is invalid');
  }
  if (
    !metadata.sourceSchemaVersion.trim()
    || metadata.sourceSchemaVersion !== metadata.sourceSchemaVersion.trim()
    || metadata.sourceSchemaVersion.length > 64
  ) {
    throw new IntakeError('METADATA_INVALID', 'source schema version is invalid');
  }
}

function attemptId(contentSha256: string, metadata: ManualWbXlsxMetadata): string {
  const fingerprint = sha256(canonicalJson({ content_sha256: contentSha256, ...metadata }));
  return `attempt:sha256:${fingerprint}`;
}

export function createManualWbXlsxManifest(
  contentSha256: string,
  contentSize: number,
  metadata: ManualWbXlsxMetadata,
): SourceArtifactManifest {
  assertManualWbXlsxMetadata(metadata);
  if (!SHA256_PATTERN.test(contentSha256) || !Number.isSafeInteger(contentSize) || contentSize <= 0) {
    throw new IntakeError('METADATA_INVALID', 'content identity is invalid');
  }
  const artifactId = `artifact:sha256:${contentSha256}`;
  const result: SourceArtifactManifest = {
    schema_version: 1,
    artifact_id: artifactId,
    tenant_id: metadata.tenantId,
    source: OFFICIAL_WB_MANUAL_SOURCE,
    dataset: metadata.dataset,
    content_sha256: contentSha256,
    content_size: contentSize,
    period: { from: metadata.periodFrom, to: metadata.periodTo, timezone: 'Europe/Moscow' },
    data_as_of: metadata.dataAsOf,
    retrieved_at: metadata.retrievedAt,
    parser_version: UNPARSED_PARSER_VERSION,
    source_schema_version: metadata.sourceSchemaVersion,
    provenance: {
      acquisition_attempt_id: attemptId(contentSha256, metadata),
      retrieval_mode: MANUAL_EXPORT_RETRIEVAL_MODE,
    },
    locator: `artifact://sha256/${contentSha256}`,
  };
  if (!ID_PATTERN.test(result.artifact_id) || !ID_PATTERN.test(result.provenance.acquisition_attempt_id)) {
    throw new IntakeError('METADATA_INVALID', 'derived identity is invalid');
  }
  return result;
}

let validatorPromise: Promise<(manifest: SourceArtifactManifest) => void> | undefined;

async function loadManifestValidator(): Promise<(manifest: SourceArtifactManifest) => void> {
  const schemaPath = resolve(import.meta.dirname, '../../../../contracts/source-artifact.schema.json');
  const schema = JSON.parse(await readFile(schemaPath, 'utf8')) as object;
  const ajv = new Ajv2020({ allErrors: true, strict: true });
  addFormats(ajv);
  const validate = ajv.compile<SourceArtifactManifest>(schema);
  return (manifest) => {
    if (!validate(manifest)) {
      throw new IntakeError('METADATA_INVALID', `manifest violates source-artifact contract: ${ajv.errorsText(validate.errors)}`);
    }
  };
}

export async function assertSourceArtifactContract(manifest: SourceArtifactManifest): Promise<void> {
  validatorPromise ??= loadManifestValidator();
  (await validatorPromise)(manifest);
}

export function canonicalManifestBytes(manifest: SourceArtifactManifest): Buffer {
  return Buffer.from(`${canonicalJson(manifest)}\n`, 'utf8');
}
