import { constants } from 'node:fs';
import { lstat, open, rename, unlink } from 'node:fs/promises';
import { basename, dirname, join } from 'node:path';
import { randomUUID } from 'node:crypto';

import { Pool } from 'pg';

import { readPrivateFile, readPrivateSecret } from './secrets.js';
import { BusinessSignalError } from './types.js';

export async function privateDatabasePool(databaseUrlFile: string): Promise<Pool> {
  const connectionString = await readPrivateSecret(databaseUrlFile, 'PostgreSQL URL file');
  return new Pool({ connectionString, max: 2, application_name: 'proxima-business-signal' });
}

export async function readFounderChatId(path: string): Promise<bigint> {
  let bytes: Buffer;
  try { bytes = await readPrivateFile(path, 'founder chat source'); } catch (error) {
    if (error instanceof BusinessSignalError) throw new BusinessSignalError('CHAT_CONFIG_UNSAFE', 'founder chat source must be a private regular file with mode 0600');
    throw error;
  }
  let payload: unknown;
  try { payload = JSON.parse(bytes.toString('utf8')); } catch {
    throw new BusinessSignalError('CHAT_CONFIG_INVALID', 'founder chat source is invalid JSON');
  }
  if (!payload || typeof payload !== 'object' || Array.isArray(payload) || Object.keys(payload).length !== 1) {
    throw new BusinessSignalError('CHAT_CONFIG_INVALID', 'founder chat source must contain only chat_id');
  }
  const value = (payload as Record<string, unknown>).chat_id;
  if ((typeof value !== 'number' && typeof value !== 'string') || !/^-?\d+$/.test(String(value)) || BigInt(String(value)) === 0n) {
    throw new BusinessSignalError('CHAT_CONFIG_INVALID', 'founder chat_id must be a non-zero integer');
  }
  return BigInt(String(value));
}

export async function writeFounderChatId(path: string, chatId: bigint): Promise<void> {
  if (chatId === 0n) throw new BusinessSignalError('CHAT_CONFIG_INVALID', 'founder chat_id must be non-zero');
  try {
    const current = await lstat(path);
    if (!current.isFile() || current.isSymbolicLink() || (current.mode & 0o077) !== 0) {
      throw new BusinessSignalError('CHAT_CONFIG_UNSAFE', 'existing founder chat source must be a private regular file');
    }
  } catch (error) {
    if (!(error && typeof error === 'object' && 'code' in error && error.code === 'ENOENT')) throw error;
  }

  const temporary = join(dirname(path), `.${basename(path)}.${randomUUID()}.tmp`);
  const handle = await open(temporary, constants.O_WRONLY | constants.O_CREAT | constants.O_EXCL | (constants.O_NOFOLLOW ?? 0), 0o600);
  try {
    await handle.writeFile(`${JSON.stringify({ chat_id: chatId.toString() })}\n`, 'utf8');
    await handle.sync();
  } catch (error) {
    await handle.close();
    await unlink(temporary).catch(() => {});
    throw error;
  }
  await handle.close();
  try {
    await rename(temporary, path);
  } catch (error) {
    await unlink(temporary).catch(() => {});
    throw error;
  }
}
