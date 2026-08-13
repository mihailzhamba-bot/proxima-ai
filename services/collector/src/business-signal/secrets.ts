import { constants } from 'node:fs';
import { open } from 'node:fs/promises';

import { BusinessSignalError } from './types.js';

const TOKEN_CATEGORY_BITS: Record<number, string> = {
  1: 'content',
  2: 'analytics',
  3: 'prices',
  4: 'marketplace',
  5: 'statistics',
  6: 'promotion',
  7: 'feedbacks',
  9: 'buyer_chat',
  10: 'supplies',
  11: 'returns',
  12: 'documents',
  13: 'finance',
  16: 'users',
};
const READ_ONLY_BIT = 30;

export async function readPrivateFile(path: string, label: string): Promise<Buffer> {
  let handle;
  try {
    handle = await open(path, constants.O_RDONLY | (constants.O_NOFOLLOW ?? 0));
  } catch {
    throw new BusinessSignalError('SECRET_UNSAFE', `${label} must be a private regular file with mode 0600`);
  }
  try {
    const info = await handle.stat();
    if (!info.isFile() || (info.mode & 0o077) !== 0) {
      throw new BusinessSignalError('SECRET_UNSAFE', `${label} must be a private regular file with mode 0600`);
    }
    return await handle.readFile();
  } finally {
    await handle.close();
  }
}

export async function readPrivateSecret(path: string, label: string): Promise<string> {
  const value = (await readPrivateFile(path, label)).toString('utf8').trim();
  if (!value || /\s/.test(value)) throw new BusinessSignalError('SECRET_INVALID', `${label} must contain one value`);
  return value;
}

function decodeJwtPayload(token: string): Record<string, unknown> {
  const parts = token.split('.');
  if (parts.length !== 3 || !parts[1]) throw new BusinessSignalError('TOKEN_INVALID', 'WB token must be a JWT');
  try {
    const result: unknown = JSON.parse(Buffer.from(parts[1], 'base64url').toString('utf8'));
    if (!result || typeof result !== 'object' || Array.isArray(result)) throw new Error('payload');
    return result as Record<string, unknown>;
  } catch {
    throw new BusinessSignalError('TOKEN_INVALID', 'WB token payload is invalid');
  }
}

export function assertLeastPrivilegeToken(
  token: string,
  requiredCategory: 'statistics' | 'analytics' | 'finance',
  now = new Date(),
  options: { allowReadWrite?: boolean } = {},
): void {
  const payload = decodeJwtPayload(token);
  if (typeof payload.s !== 'number' || !Number.isSafeInteger(payload.s)) {
    throw new BusinessSignalError('TOKEN_INVALID', 'WB token scope claim is missing');
  }
  const scopes = payload.s;
  const granted = Object.entries(TOKEN_CATEGORY_BITS)
    .filter(([bit]) => (scopes & (1 << Number(bit))) !== 0)
    .map(([, category]) => category);
  const isReadOnly = (scopes & (1 << READ_ONLY_BIT)) !== 0;
  if ((!isReadOnly && !options.allowReadWrite) || granted.length !== 1 || granted[0] !== requiredCategory) {
    const access = options.allowReadWrite ? 'grant only its category' : 'be READ-only and grant only its category';
    throw new BusinessSignalError('TOKEN_SCOPE_INVALID', `WB ${requiredCategory} token must ${access}`);
  }
  if (typeof payload.exp !== 'number' || payload.exp * 1000 <= now.getTime()) {
    throw new BusinessSignalError('TOKEN_EXPIRED', `WB ${requiredCategory} token is expired`);
  }
}
