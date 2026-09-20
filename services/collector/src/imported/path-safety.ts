import { constants } from 'node:fs';
import { lstat, mkdir, open, realpath, type FileHandle } from 'node:fs/promises';
import { isAbsolute, relative, resolve, sep } from 'node:path';

const PRIVATE_MASK = 0o077;

export class UnsafePathError extends Error {
  readonly code = 'UNSAFE_PATH';

  constructor(message: string) {
    super(message);
    this.name = 'UnsafePathError';
  }
}

function containedRelative(target: string, boundary: string): string {
  const resolvedBoundary = resolve(boundary);
  const resolvedTarget = resolve(target);
  const rel = relative(resolvedBoundary, resolvedTarget);
  if (rel === '..' || rel.startsWith(`..${sep}`) || isAbsolute(rel)) {
    throw new UnsafePathError(`Path is outside managed boundary: ${resolvedTarget}`);
  }
  return rel;
}

function isContainedRealPath(target: string, boundary: string): boolean {
  const rel = relative(boundary, target);
  return rel === '' || (!isAbsolute(rel) && rel !== '..' && !rel.startsWith(`..${sep}`));
}

async function checkedBoundary(boundary: string): Promise<{ lexical: string; real: string }> {
  const lexical = resolve(boundary);
  const info = await lstat(lexical);
  if (info.isSymbolicLink() || !info.isDirectory()) {
    throw new UnsafePathError(`Managed boundary must be a real directory: ${lexical}`);
  }
  return { lexical, real: await realpath(lexical) };
}

async function assertDirectoryComponent(path: string, realBoundary: string, requirePrivate: boolean): Promise<void> {
  const info = await lstat(path);
  if (info.isSymbolicLink() || !info.isDirectory()) {
    throw new UnsafePathError(`Managed path component is not a real directory: ${path}`);
  }
  if (requirePrivate && (info.mode & PRIVATE_MASK) !== 0) {
    throw new UnsafePathError(`Unsafe directory permissions at ${path}; expected mode 0700`);
  }
  const actual = await realpath(path);
  if (!isContainedRealPath(actual, realBoundary)) {
    throw new UnsafePathError(`Managed directory resolves outside boundary: ${path}`);
  }
}

export async function ensureManagedPrivateDir(path: string, boundary: string): Promise<void> {
  const checked = await checkedBoundary(boundary);
  const rel = containedRelative(path, checked.lexical);
  if (rel === '') return;
  let current = checked.lexical;
  for (const component of rel.split(sep).filter(Boolean)) {
    current = resolve(current, component);
    try {
      await assertDirectoryComponent(current, checked.real, true);
    } catch (error) {
      if ((error as NodeJS.ErrnoException).code !== 'ENOENT') throw error;
      await mkdir(current, { mode: 0o700 });
      await assertDirectoryComponent(current, checked.real, true);
    }
  }
}

export async function assertManagedDirectory(path: string, boundary: string): Promise<void> {
  const checked = await checkedBoundary(boundary);
  const rel = containedRelative(path, checked.lexical);
  let current = checked.lexical;
  for (const component of rel.split(sep).filter(Boolean)) {
    current = resolve(current, component);
    await assertDirectoryComponent(current, checked.real, false);
  }
}

export async function assertManagedFile(path: string, boundary: string): Promise<void> {
  const checked = await checkedBoundary(boundary);
  containedRelative(path, checked.lexical);
  const parent = resolve(path, '..');
  await assertManagedDirectory(parent, checked.lexical);
  const info = await lstat(path);
  if (info.isSymbolicLink() || !info.isFile()) {
    throw new UnsafePathError(`Managed file must be a regular non-symlink file: ${path}`);
  }
  const actual = await realpath(path);
  if (!isContainedRealPath(actual, checked.real)) {
    throw new UnsafePathError(`Managed file resolves outside boundary: ${path}`);
  }
}

export async function openManagedFile(
  path: string,
  boundary: string,
  flags: number,
  mode = 0o600,
): Promise<FileHandle> {
  await assertManagedDirectory(resolve(path, '..'), boundary);
  containedRelative(path, resolve(boundary));
  const noFollow = constants.O_NOFOLLOW ?? 0;
  return open(path, flags | noFollow, mode);
}

export async function openManagedDirectory(path: string, boundary: string): Promise<FileHandle> {
  await assertManagedDirectory(path, boundary);
  const noFollow = constants.O_NOFOLLOW ?? 0;
  const handle = await open(path, constants.O_RDONLY | noFollow);
  const info = await handle.stat();
  if (!info.isDirectory()) {
    await handle.close();
    throw new UnsafePathError(`Managed directory descriptor is not a directory: ${path}`);
  }
  return handle;
}

export const MANAGED_OPEN_FLAGS = {
  append: constants.O_WRONLY | constants.O_CREAT | constants.O_APPEND,
  createExclusive: constants.O_WRONLY | constants.O_CREAT | constants.O_EXCL,
  read: constants.O_RDONLY,
} as const;

export async function readManagedFile(path: string, boundary: string): Promise<Buffer> {
  await assertManagedFile(path, boundary);
  const handle = await openManagedFile(path, boundary, MANAGED_OPEN_FLAGS.read);
  try {
    const info = await handle.stat();
    if (!info.isFile()) throw new UnsafePathError(`Managed file descriptor is not regular: ${path}`);
    return await handle.readFile();
  } finally {
    await handle.close();
  }
}
