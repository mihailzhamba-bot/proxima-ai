import assert from 'node:assert/strict';
import { chmod, lstat, mkdir, mkdtemp, readFile, readdir, symlink, unlink, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import test from 'node:test';

import { objectPath, manifestPath } from '../src/intake/content-store.js';
import { intakeManualWbXlsx } from '../src/intake/manual-wb-xlsx.js';
import { sha256 } from '../src/intake/manifest.js';
import type { IntakeFailurePoint, ManualWbXlsxMetadata } from '../src/intake/types.js';

const structuralZipFixture = Buffer.concat([
  Buffer.from([0x50, 0x4b, 0x03, 0x04]),
  Buffer.from('synthetic-xlsx-structure-only', 'utf8'),
]);

const metadata: ManualWbXlsxMetadata = {
  tenantId: 'synthetic_tenant',
  dataset: 'orders',
  periodFrom: '2026-08-11',
  periodTo: '2026-08-11',
  dataAsOf: '2026-08-11T21:00:00Z',
  retrievedAt: '2026-08-12T04:00:00Z',
  sourceSchemaVersion: 'synthetic-v1',
};

interface TestPaths {
  repositoryRoot: string;
  inputPath: string;
  storeRoot: string;
}

async function createPaths(): Promise<TestPaths> {
  const root = await mkdtemp(join(tmpdir(), 'proxima-intake-test-'));
  const repositoryRoot = join(root, 'repository');
  const storeRoot = join(root, 'private-store');
  await mkdir(repositoryRoot, { mode: 0o700 });
  const inputPath = join(root, 'synthetic.xlsx');
  await writeFile(inputPath, structuralZipFixture, { mode: 0o600 });
  return { repositoryRoot, inputPath, storeRoot };
}

function options(paths: TestPaths) {
  return {
    ...paths,
    metadata,
  };
}

test('stores exact synthetic bytes before publishing a contract-valid manifest and is idempotent', async () => {
  const paths = await createPaths();
  const checksum = sha256(structuralZipFixture);
  const first = await intakeManualWbXlsx(options(paths));
  const second = await intakeManualWbXlsx(options(paths));

  assert.deepEqual(first, {
    artifactId: `artifact:sha256:${checksum}`,
    contentSha256: checksum,
    locator: `artifact://sha256/${checksum}`,
    state: 'created',
  });
  assert.deepEqual(second, { ...first, state: 'existing' });
  assert.deepEqual(await readFile(objectPath(paths.storeRoot, checksum)), structuralZipFixture);
  const manifest = JSON.parse(await readFile(manifestPath(paths.storeRoot, checksum), 'utf8')) as Record<string, unknown>;
  assert.equal(manifest.content_sha256, checksum);
  assert.equal(manifest.content_size, structuralZipFixture.length);
  assert.equal(manifest.parser_version, '0.0.0');
  assert.equal((await lstat(objectPath(paths.storeRoot, checksum))).mode & 0o077, 0);
  assert.equal((await lstat(manifestPath(paths.storeRoot, checksum))).mode & 0o077, 0);
});

for (const point of [
  'after_temp_durable',
  'after_raw_published',
  'before_manifest_published',
  'after_manifest_published',
] as const satisfies readonly IntakeFailurePoint[]) {
  test(`recovers deterministically after a forced crash at ${point}`, async () => {
    const paths = await createPaths();
    const checksum = sha256(structuralZipFixture);
    await assert.rejects(
      intakeManualWbXlsx({
        ...options(paths),
        hooks: { at: (current) => { if (current === point) throw new Error('synthetic crash'); } },
      }),
      /synthetic crash/,
    );
    const rawExists = await lstat(objectPath(paths.storeRoot, checksum)).then(() => true, () => false);
    const manifestExists = await lstat(manifestPath(paths.storeRoot, checksum)).then(() => true, () => false);
    assert.equal(rawExists, point !== 'after_temp_durable');
    assert.equal(manifestExists, point === 'after_manifest_published');
    const retry = await intakeManualWbXlsx(options(paths));
    assert.equal(retry.state, point === 'after_manifest_published' ? 'existing' : 'created');
    assert.deepEqual(await readFile(objectPath(paths.storeRoot, checksum)), structuralZipFixture);
    assert.deepEqual(await readdir(join(paths.storeRoot, 'tmp')), []);
  });
}

test('rejects conflicting metadata without modifying immutable raw or manifest bytes', async () => {
  const paths = await createPaths();
  const checksum = sha256(structuralZipFixture);
  await intakeManualWbXlsx(options(paths));
  const beforeRaw = await readFile(objectPath(paths.storeRoot, checksum));
  const beforeManifest = await readFile(manifestPath(paths.storeRoot, checksum));
  await assert.rejects(
    intakeManualWbXlsx({ ...options(paths), metadata: { ...metadata, retrievedAt: '2026-08-12T05:00:00Z' } }),
    { name: 'IntakeError', code: 'MANIFEST_CONFLICT' },
  );
  assert.deepEqual(await readFile(objectPath(paths.storeRoot, checksum)), beforeRaw);
  assert.deepEqual(await readFile(manifestPath(paths.storeRoot, checksum)), beforeManifest);
});

test('rejects invalid metadata before creating any raw object', async () => {
  const paths = await createPaths();
  const checksum = sha256(structuralZipFixture);
  await assert.rejects(
    intakeManualWbXlsx({ ...options(paths), metadata: { ...metadata, dataAsOf: '2026-02-30T21:00:00Z' } }),
    { name: 'IntakeError', code: 'METADATA_INVALID' },
  );
  const exists = await lstat(objectPath(paths.storeRoot, checksum)).then(() => true, () => false);
  assert.equal(exists, false);
});

test('fails closed if a published manifest exists without its verified raw object', async () => {
  const paths = await createPaths();
  const checksum = sha256(structuralZipFixture);
  await intakeManualWbXlsx(options(paths));
  await unlink(objectPath(paths.storeRoot, checksum));
  await assert.rejects(
    intakeManualWbXlsx(options(paths)),
    { name: 'IntakeError', code: 'ARTIFACT_CHECKSUM_MISMATCH' },
  );
});

test('rejects repository-local storage, unsafe storage permissions, symlink input and invalid XLSX bytes', async () => {
  const paths = await createPaths();
  await assert.rejects(
    intakeManualWbXlsx({ ...options(paths), storeRoot: join(paths.repositoryRoot, 'raw') }),
    { name: 'IntakeError', code: 'STORAGE_INSIDE_REPOSITORY' },
  );

  await mkdir(paths.storeRoot, { mode: 0o700 });
  await chmod(paths.storeRoot, 0o755);
  await assert.rejects(intakeManualWbXlsx(options(paths)), { name: 'IntakeError', code: 'UNSAFE_STORAGE' });

  const safePaths = await createPaths();
  const inputLink = join(safePaths.repositoryRoot, 'input.xlsx');
  await symlink(safePaths.inputPath, inputLink);
  await assert.rejects(
    intakeManualWbXlsx({ ...options(safePaths), inputPath: inputLink }),
    { name: 'IntakeError', code: 'UNSAFE_INPUT' },
  );

  const invalidPaths = await createPaths();
  await writeFile(invalidPaths.inputPath, Buffer.from('not-a-workbook'), { mode: 0o600 });
  await assert.rejects(
    intakeManualWbXlsx(options(invalidPaths)),
    { name: 'IntakeError', code: 'INPUT_NOT_XLSX' },
  );
});
