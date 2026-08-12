import { constants } from 'node:fs';
import { link, lstat, mkdir, open, realpath, unlink } from 'node:fs/promises';
import { basename, dirname, extname, isAbsolute, join, relative, resolve, sep } from 'node:path';
import { createHash, randomUUID } from 'node:crypto';

import {
  MANAGED_OPEN_FLAGS,
  UnsafePathError,
  assertManagedFile,
  ensureManagedPrivateDir,
  openManagedDirectory,
  openManagedFile,
  readManagedFile,
} from '../imported/path-safety.js';
import { sha256 } from './manifest.js';
import { IntakeError } from './types.js';

const PRIVATE_MASK = 0o077;
const XLSX_ZIP_SIGNATURE = Buffer.from([0x50, 0x4b, 0x03, 0x04]);

function isWithin(boundary: string, target: string): boolean {
  const path = relative(boundary, target);
  return path === '' || (!isAbsolute(path) && path !== '..' && !path.startsWith(`..${sep}`));
}

async function assertPrivateDirectory(path: string): Promise<string> {
  const info = await lstat(path);
  if (info.isSymbolicLink() || !info.isDirectory() || (info.mode & PRIVATE_MASK) !== 0) {
    throw new IntakeError('UNSAFE_STORAGE', 'storage root must be a private real directory');
  }
  return realpath(path);
}

export async function preparePrivateStore(storeRoot: string, repositoryRoot: string): Promise<string> {
  const resolvedStore = resolve(storeRoot);
  const resolvedRepository = resolve(repositoryRoot);
  if (isWithin(resolvedRepository, resolvedStore)) {
    throw new IntakeError('STORAGE_INSIDE_REPOSITORY', 'storage root must be outside the repository');
  }
  await mkdir(resolvedStore, { recursive: true, mode: 0o700 });
  const [realStore, realRepository] = await Promise.all([assertPrivateDirectory(resolvedStore), realpath(resolvedRepository)]);
  if (isWithin(realRepository, realStore)) {
    throw new IntakeError('STORAGE_INSIDE_REPOSITORY', 'storage root must be outside the repository');
  }
  return realStore;
}

export function objectPath(storeRoot: string, contentSha256: string): string {
  return join(storeRoot, 'objects', 'sha256', contentSha256.slice(0, 2), contentSha256);
}

export function manifestPath(storeRoot: string, contentSha256: string): string {
  return join(storeRoot, 'manifests', 'sha256', contentSha256.slice(0, 2), `${contentSha256}.json`);
}

async function fsyncDirectory(path: string, boundary: string): Promise<void> {
  const handle = await openManagedDirectory(path, boundary);
  try {
    await handle.sync();
  } finally {
    await handle.close();
  }
}

async function writeAll(handle: Awaited<ReturnType<typeof open>>, data: Buffer): Promise<void> {
  let offset = 0;
  while (offset < data.length) {
    const { bytesWritten } = await handle.write(data, offset, data.length - offset, null);
    if (bytesWritten <= 0) throw new Error('failed to persist raw input');
    offset += bytesWritten;
  }
}

export interface StreamedInput {
  contentSha256: string;
  contentSize: number;
  temporaryPath: string;
}

export async function streamXlsxToPrivateTemp(inputPath: string, storeRoot: string): Promise<StreamedInput> {
  if (extname(inputPath).toLowerCase() !== '.xlsx') {
    throw new IntakeError('INPUT_NOT_XLSX', 'manual intake accepts only .xlsx files');
  }
  const lexicalInput = resolve(inputPath);
  const inputInfo = await lstat(lexicalInput);
  if (inputInfo.isSymbolicLink() || !inputInfo.isFile()) {
    throw new IntakeError('UNSAFE_INPUT', 'input must be a regular non-symlink file');
  }

  const temporaryDirectory = join(storeRoot, 'tmp');
  await ensureManagedPrivateDir(temporaryDirectory, storeRoot);
  const temporaryPath = join(temporaryDirectory, `${randomUUID()}.tmp`);
  const source = await open(lexicalInput, constants.O_RDONLY | (constants.O_NOFOLLOW ?? 0));
  let destination: Awaited<ReturnType<typeof openManagedFile>> | undefined;
  try {
    const sourceInfo = await source.stat();
    if (!sourceInfo.isFile()) throw new IntakeError('UNSAFE_INPUT', 'input must be a regular file');
    destination = await openManagedFile(temporaryPath, storeRoot, MANAGED_OPEN_FLAGS.createExclusive);
    const hash = createHash('sha256');
    const buffer = Buffer.allocUnsafe(64 * 1024);
    const prefix: Buffer[] = [];
    let contentSize = 0;
    for (;;) {
      const { bytesRead } = await source.read(buffer, 0, buffer.length, null);
      if (bytesRead === 0) break;
      const chunk = Buffer.from(buffer.subarray(0, bytesRead));
      if (contentSize < XLSX_ZIP_SIGNATURE.length) {
        prefix.push(chunk.subarray(0, XLSX_ZIP_SIGNATURE.length - contentSize));
      }
      hash.update(chunk);
      await writeAll(destination, chunk);
      contentSize += bytesRead;
    }
    await destination.sync();
    const firstBytes = Buffer.concat(prefix);
    if (contentSize === 0 || !firstBytes.equals(XLSX_ZIP_SIGNATURE)) {
      throw new IntakeError('INPUT_NOT_XLSX', 'input does not have an XLSX ZIP signature');
    }
    return { contentSha256: hash.digest('hex'), contentSize, temporaryPath };
  } finally {
    await destination?.close();
    await source.close();
  }
}

async function assertExistingObject(path: string, storeRoot: string, expectedSha256: string, expectedSize: number): Promise<void> {
  await assertManagedFile(path, storeRoot);
  const [info, bytes] = await Promise.all([lstat(path), readManagedFile(path, storeRoot)]);
  if (!info.isFile() || (info.mode & PRIVATE_MASK) !== 0 || info.size !== expectedSize || sha256(bytes) !== expectedSha256) {
    throw new IntakeError('ARTIFACT_CHECKSUM_MISMATCH', 'existing artifact failed integrity verification');
  }
}

export async function publishRawObject(
  temporaryPath: string,
  storeRoot: string,
  contentSha256: string,
  contentSize: number,
): Promise<'created' | 'existing'> {
  const finalPath = objectPath(storeRoot, contentSha256);
  const finalDirectory = dirname(finalPath);
  await ensureManagedPrivateDir(finalDirectory, storeRoot);
  try {
    await link(temporaryPath, finalPath);
    await fsyncDirectory(finalDirectory, storeRoot);
    await assertExistingObject(finalPath, storeRoot, contentSha256, contentSize);
    return 'created';
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code !== 'EEXIST') throw error;
    await assertExistingObject(finalPath, storeRoot, contentSha256, contentSize);
    return 'existing';
  }
}

export async function assertPublishedArtifactIntegrity(
  storeRoot: string,
  contentSha256: string,
  contentSize: number,
): Promise<boolean> {
  const publishedManifestPath = manifestPath(storeRoot, contentSha256);
  try {
    await lstat(publishedManifestPath);
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === 'ENOENT') return false;
    throw error;
  }
  await assertManagedFile(publishedManifestPath, storeRoot);
  const manifestInfo = await lstat(publishedManifestPath);
  if ((manifestInfo.mode & PRIVATE_MASK) !== 0) {
    throw new IntakeError('UNSAFE_STORAGE', 'manifest has unsafe permissions');
  }
  try {
    await assertExistingObject(objectPath(storeRoot, contentSha256), storeRoot, contentSha256, contentSize);
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === 'ENOENT') {
      throw new IntakeError('ARTIFACT_CHECKSUM_MISMATCH', 'published manifest has no raw artifact');
    }
    throw error;
  }
  return true;
}

export async function publishManifest(
  temporaryPath: string,
  finalPath: string,
  expectedBytes: Buffer,
  storeRoot: string,
): Promise<'created' | 'existing'> {
  await ensureManagedPrivateDir(dirname(finalPath), storeRoot);
  try {
    await link(temporaryPath, finalPath);
    await fsyncDirectory(dirname(finalPath), storeRoot);
    await assertManagedFile(finalPath, storeRoot);
    const info = await lstat(finalPath);
    if ((info.mode & PRIVATE_MASK) !== 0) throw new IntakeError('UNSAFE_STORAGE', 'manifest has unsafe permissions');
    return 'created';
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code !== 'EEXIST') throw error;
    const current = await readManagedFile(finalPath, storeRoot);
    if (!current.equals(expectedBytes)) {
      throw new IntakeError('MANIFEST_CONFLICT', 'existing artifact has conflicting immutable metadata');
    }
    return 'existing';
  }
}

export async function createPrivateTempFile(storeRoot: string, name: string, bytes: Buffer): Promise<string> {
  const tempDirectory = join(storeRoot, 'tmp');
  await ensureManagedPrivateDir(tempDirectory, storeRoot);
  const path = join(tempDirectory, `.${basename(name)}.${randomUUID()}.tmp`);
  const handle = await openManagedFile(path, storeRoot, MANAGED_OPEN_FLAGS.createExclusive);
  try {
    await writeAll(handle, bytes);
    await handle.sync();
  } finally {
    await handle.close();
  }
  return path;
}

export async function removePrivateTemp(path: string): Promise<void> {
  await unlink(path).catch((error: NodeJS.ErrnoException) => {
    if (error.code !== 'ENOENT') throw error;
  });
}

export function sourceFileBasename(path: string): string {
  return basename(path);
}

export function isUnsafePathError(error: unknown): boolean {
  return error instanceof UnsafePathError;
}
