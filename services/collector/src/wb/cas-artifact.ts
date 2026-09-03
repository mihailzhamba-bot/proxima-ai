import { constants } from 'node:fs';
import { createHash } from 'node:crypto';
import { link, lstat, mkdir, open, readFile, realpath, unlink } from 'node:fs/promises';
import { dirname, isAbsolute, join, relative, resolve, sep } from 'node:path';

import { canonicalJson } from '../intake/manifest.js';

const SHA256 = /^[0-9a-f]{64}$/;
const PRIVATE_MASK = 0o077;

export type CasArtifactSource = 'official_wb_statistics';
export type CasArtifactEndpoint = 'statistics.orders' | 'statistics.sales';

export interface ImportedCasManifest {
  readonly schema_version: 1;
  readonly source: CasArtifactSource;
  readonly endpoint_id: CasArtifactEndpoint;
  readonly endpoint_path: string;
  readonly http_status: 200;
  readonly response_headers: Record<string, string>;
  readonly retrieved_at: string;
  readonly content_sha256: string;
  readonly content_size: number;
  readonly object_locator: string;
}

function isWithin(boundary: string, target: string): boolean {
  const path = relative(boundary, target);
  return path === '' || (!isAbsolute(path) && path !== '..' && !path.startsWith(`..${sep}`));
}

async function privateDirectory(path: string): Promise<void> {
  await mkdir(path, { recursive: true, mode: 0o700 });
  const info = await lstat(path);
  if (!info.isDirectory() || info.isSymbolicLink() || (info.mode & PRIVATE_MASK) !== 0) {
    throw new Error('CAS directories must be private and cannot be symlinks');
  }
}

async function publish(tempPath: string, finalPath: string, expected: Buffer): Promise<void> {
  await privateDirectory(dirname(finalPath));
  try { await link(tempPath, finalPath); }
  catch (error) { if ((error as NodeJS.ErrnoException).code !== 'EEXIST') throw error; }
  const info = await lstat(finalPath);
  if (!info.isFile() || info.isSymbolicLink() || (info.mode & PRIVATE_MASK) !== 0 || !(await readFile(finalPath)).equals(expected)) {
    throw new Error(`CAS conflict at ${finalPath}`);
  }
}

function endpointFromName(file: string): CasArtifactEndpoint {
  const name = file.toLowerCase();
  if (name.includes('order')) return 'statistics.orders';
  if (name.includes('sale')) return 'statistics.sales';
  throw new Error('cannot infer WB endpoint: file name must contain orders or sales');
}

function endpointPath(endpoint: CasArtifactEndpoint): string {
  return endpoint === 'statistics.orders' ? '/api/v1/supplier/orders' : '/api/v1/supplier/sales';
}

export async function importCasArtifact(input: {
  file: string;
  rawRoot: string;
  repositoryRoot: string;
  retrievedAt: Date;
  source: CasArtifactSource;
}): Promise<ImportedCasManifest> {
  if (!Number.isFinite(input.retrievedAt.getTime())) throw new Error('--retrieved-at must be a valid ISO timestamp');
  const root = resolve(input.rawRoot);
  const repository = await realpath(input.repositoryRoot);
  if (isWithin(repository, root)) throw new Error('CAS root must stay outside Git');
  await privateDirectory(root);
  const body = await readFile(input.file);
  const contentSha256 = createHash('sha256').update(body).digest('hex');
  const endpointId = endpointFromName(input.file);
  const objectLocator = `artifact://business-signal/sha256/${contentSha256}`;
  const manifest: ImportedCasManifest = {
    schema_version: 1,
    source: input.source,
    endpoint_id: endpointId,
    endpoint_path: endpointPath(endpointId),
    http_status: 200,
    response_headers: {},
    retrieved_at: input.retrievedAt.toISOString(),
    content_sha256: contentSha256,
    content_size: body.length,
    object_locator: objectLocator,
  };
  const manifestBody = Buffer.from(`${canonicalJson(manifest)}\n`);
  const temp = join(root, 'tmp');
  await privateDirectory(temp);
  const nonce = `${process.pid}-${Date.now()}-${Math.random().toString(16).slice(2)}`;
  const objectTemp = join(temp, `${nonce}.object`);
  const manifestTemp = join(temp, `${nonce}.manifest`);
  const writePrivate = async (path: string, value: Buffer): Promise<void> => {
    const handle = await open(path, constants.O_CREAT | constants.O_EXCL | constants.O_WRONLY | (constants.O_NOFOLLOW ?? 0), 0o600);
    try { await handle.writeFile(value); await handle.sync(); } finally { await handle.close(); }
  };
  await writePrivate(objectTemp, body);
  await writePrivate(manifestTemp, manifestBody);
  try {
    await publish(objectTemp, join(root, 'objects', 'sha256', contentSha256.slice(0, 2), contentSha256), body);
    await publish(manifestTemp, join(root, 'imports', `${contentSha256}.json`), manifestBody);
  } finally {
    await unlink(objectTemp).catch(() => undefined);
    await unlink(manifestTemp).catch(() => undefined);
  }
  return manifest;
}

export async function readImportedCasArtifact(rawRoot: string, sha: string): Promise<{ manifest: ImportedCasManifest; body: Buffer; manifestSha256: string }> {
  if (!SHA256.test(sha)) throw new Error(`invalid artifact sha256 ${sha}`);
  const manifestBody = await readFile(join(resolve(rawRoot), 'imports', `${sha}.json`));
  const manifest = JSON.parse(manifestBody.toString('utf8')) as ImportedCasManifest;
  if (manifest.content_sha256 !== sha || manifest.object_locator !== `artifact://business-signal/sha256/${sha}`) throw new Error(`CAS manifest mismatch for ${sha}`);
  if (manifest.endpoint_id !== 'statistics.orders' && manifest.endpoint_id !== 'statistics.sales') throw new Error(`unsupported CAS endpoint for ${sha}`);
  const body = await readFile(join(resolve(rawRoot), 'objects', 'sha256', sha.slice(0, 2), sha));
  if (createHash('sha256').update(body).digest('hex') !== sha || body.length !== manifest.content_size) throw new Error(`CAS object mismatch for ${sha}`);
  return { manifest, body, manifestSha256: createHash('sha256').update(manifestBody).digest('hex') };
}
