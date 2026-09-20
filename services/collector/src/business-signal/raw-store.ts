import { constants } from 'node:fs';
import { createHash, randomUUID } from 'node:crypto';
import { link, lstat, mkdir, open, readFile, realpath, unlink } from 'node:fs/promises';
import { dirname, isAbsolute, join, relative, resolve, sep } from 'node:path';

import { canonicalJson } from '../intake/manifest.js';
import { BusinessSignalError, type SignalSource } from './types.js';

const PRIVATE_MASK = 0o077;

function isWithin(boundary: string, target: string): boolean {
  const path = relative(boundary, target);
  return path === '' || (!isAbsolute(path) && path !== '..' && !path.startsWith(`..${sep}`));
}

async function ensurePrivateDirectory(path: string): Promise<void> {
  await mkdir(path, { recursive: true, mode: 0o700 });
  const info = await lstat(path);
  if (!info.isDirectory() || info.isSymbolicLink() || (info.mode & PRIVATE_MASK) !== 0) {
    throw new BusinessSignalError('RAW_STORE_UNSAFE', 'raw store directories must be private and cannot be symlinks');
  }
}

async function fsyncDirectory(path: string): Promise<void> {
  const handle = await open(path, constants.O_RDONLY | (constants.O_DIRECTORY ?? 0) | (constants.O_NOFOLLOW ?? 0));
  try { await handle.sync(); } finally { await handle.close(); }
}

async function publishExact(tempPath: string, finalPath: string, expected: Buffer): Promise<void> {
  await ensurePrivateDirectory(dirname(finalPath));
  try {
    await link(tempPath, finalPath);
    await fsyncDirectory(dirname(finalPath));
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code !== 'EEXIST') throw error;
  }
  const info = await lstat(finalPath);
  if (!info.isFile() || info.isSymbolicLink() || (info.mode & PRIVATE_MASK) !== 0 || !(await readFile(finalPath)).equals(expected)) {
    throw new BusinessSignalError('RAW_ARTIFACT_CONFLICT', 'existing raw artifact differs from expected bytes');
  }
}

export interface RawHttpArtifact {
  contentSha256: string;
  contentSize: number;
  objectLocator: string;
  manifestSha256: string;
}

export class BusinessSignalRawStore {
  private constructor(private readonly root: string) {}

  static async open(root: string, repositoryRoot: string): Promise<BusinessSignalRawStore> {
    const resolvedRoot = resolve(root);
    const resolvedRepository = await realpath(repositoryRoot);
    if (isWithin(resolvedRepository, resolvedRoot)) throw new BusinessSignalError('RAW_STORE_UNSAFE', 'raw store must be outside Git');
    await ensurePrivateDirectory(resolvedRoot);
    const actualRoot = await realpath(resolvedRoot);
    if (isWithin(resolvedRepository, actualRoot)) throw new BusinessSignalError('RAW_STORE_UNSAFE', 'raw store must be outside Git');
    return new BusinessSignalRawStore(actualRoot);
  }

  async persist(input: {
    runId: string;
    source: SignalSource;
    stage: string;
    pageSequence: number;
    endpointPath: string;
    httpStatus: number;
    retrievedAt: Date;
    responseHeaders: Record<string, string>;
    body: Buffer;
  }): Promise<RawHttpArtifact> {
    const contentSha256 = createHash('sha256').update(input.body).digest('hex');
    const tempDirectory = join(this.root, 'tmp');
    await ensurePrivateDirectory(tempDirectory);
    const tempPath = join(tempDirectory, `${randomUUID()}.tmp`);
    const handle = await open(tempPath, constants.O_CREAT | constants.O_EXCL | constants.O_WRONLY | (constants.O_NOFOLLOW ?? 0), 0o600);
    try {
      await handle.writeFile(input.body);
      await handle.sync();
    } finally {
      await handle.close();
    }
    const objectPath = join(this.root, 'objects', 'sha256', contentSha256.slice(0, 2), contentSha256);
    try {
      await publishExact(tempPath, objectPath, input.body);
    } finally {
      await unlink(tempPath).catch((error: NodeJS.ErrnoException) => { if (error.code !== 'ENOENT') throw error; });
    }
    const objectLocator = `artifact://business-signal/sha256/${contentSha256}`;
    const manifest = Buffer.from(`${canonicalJson({
      schema_version: 2,
      run_id: input.runId,
      source: input.source,
      stage: input.stage,
      page_sequence: input.pageSequence,
      endpoint_path: input.endpointPath,
      http_status: input.httpStatus,
      response_headers: input.responseHeaders,
      retrieved_at: input.retrievedAt.toISOString(),
      content_sha256: contentSha256,
      content_size: input.body.length,
      object_locator: objectLocator,
    })}\n`);
    const manifestSha256 = createHash('sha256').update(manifest).digest('hex');
    const manifestTemp = join(tempDirectory, `${randomUUID()}.manifest.tmp`);
    const manifestHandle = await open(manifestTemp, constants.O_CREAT | constants.O_EXCL | constants.O_WRONLY | (constants.O_NOFOLLOW ?? 0), 0o600);
    try { await manifestHandle.writeFile(manifest); await manifestHandle.sync(); } finally { await manifestHandle.close(); }
    const manifestPath = join(this.root, 'manifests', input.runId, input.source, `${input.stage}-${input.pageSequence}.json`);
    try { await publishExact(manifestTemp, manifestPath, manifest); } finally {
      await unlink(manifestTemp).catch((error: NodeJS.ErrnoException) => { if (error.code !== 'ENOENT') throw error; });
    }
    return { contentSha256, contentSize: input.body.length, objectLocator, manifestSha256 };
  }
}
