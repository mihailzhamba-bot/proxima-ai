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
