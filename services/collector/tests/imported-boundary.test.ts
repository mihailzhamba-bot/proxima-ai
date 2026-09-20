import assert from 'node:assert/strict';
import { mkdir, mkdtemp, symlink } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import test from 'node:test';

import {
  AuthRequiredError,
  UnsafePathError,
  attachSecondaryError,
  ensureManagedPrivateDir,
  errorDiagnostic,
  redactValue,
} from '../src/index.js';

test('keeps the primary auth error and redacts its secondary diagnostic', () => {
  const primary = new AuthRequiredError('authentication required');
  attachSecondaryError(primary, new Error('token=synthetic-secret'));
  assert.equal(errorDiagnostic(primary).error_code, 'AUTH_REQUIRED');
  assert.equal(errorDiagnostic(primary).secondary?.[0]?.message, 'token=<REDACTED>');
});

test('redacts nested secret-shaped values', () => {
  assert.deepEqual(
    redactValue({ token: 'synthetic', nested: { email: 'synthetic@example.test' } }),
    { token: '<REDACTED>', nested: { email: '<REDACTED>' } },
  );
});

test('rejects a symlink inside a managed private boundary', async () => {
  const root = await mkdtemp(join(tmpdir(), 'proxima-boundary-'));
  const external = await mkdtemp(join(tmpdir(), 'proxima-external-'));
  await mkdir(join(root, 'safe'), { mode: 0o700 });
  await symlink(external, join(root, 'safe', 'escape'));
  await assert.rejects(
    ensureManagedPrivateDir(join(root, 'safe', 'escape', 'child'), root),
    UnsafePathError,
  );
});
