import assert from 'node:assert/strict';
import test from 'node:test';

import {
  assertSourceArtifactContract,
  createManualWbXlsxManifest,
  type ManualWbXlsxMetadata,
} from '../src/index.js';

const metadata: ManualWbXlsxMetadata = {
  tenantId: 'synthetic_tenant',
  dataset: 'orders',
  periodFrom: '2026-08-11',
  periodTo: '2026-08-11',
  dataAsOf: '2026-08-11T21:00:00Z',
  retrievedAt: '2026-08-12T04:00:00Z',
  sourceSchemaVersion: 'synthetic-v1',
};

test('emits a deterministic source-artifact manifest that validates against Draft 2020-12', async () => {
  const checksum = 'a'.repeat(64);
  const first = createManualWbXlsxManifest(checksum, 1024, metadata);
  const second = createManualWbXlsxManifest(checksum, 1024, metadata);
  assert.deepEqual(first, second);
  assert.equal(first.artifact_id, `artifact:sha256:${checksum}`);
  assert.equal(first.parser_version, '0.0.0');
  await assertSourceArtifactContract(first);
});

test('rejects invalid metadata before a manifest can be created', () => {
  assert.throws(
    () => createManualWbXlsxManifest('b'.repeat(64), 12, { ...metadata, periodFrom: '2026-08-12', periodTo: '2026-08-11' }),
    { name: 'IntakeError', code: 'METADATA_INVALID' },
  );
});
