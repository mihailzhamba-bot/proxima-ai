import assert from 'node:assert/strict';
import test from 'node:test';

import type { Pool } from 'pg';

import { RunLedger } from '../src/wb/run-ledger.js';

test('run-ledger: empty provenance is stored as NULL', async () => {
  const inserts: unknown[][] = [];
  const client = {
    async query(text: string, values?: unknown[]) {
      if (text.startsWith('INSERT INTO collector_runs')) inserts.push(values ?? []);
      return { rows: [], rowCount: 1 };
    },
    release() {},
  };
  const pool = { async connect() { return client; } } as unknown as Pool;
  const ledger = new RunLedger(pool);

  await ledger.open({ tenantId: 'tenant-test', kind: 'collect', gitSha: '', imageId: '' });
  await ledger.open({ tenantId: 'tenant-test', kind: 'collect', gitSha: 'abc', imageId: 'sha256:def' });

  assert.equal(inserts.length, 2);
  assert.deepEqual(inserts[0]?.slice(4, 6), [null, null]);
  assert.deepEqual(inserts[1]?.slice(4, 6), ['abc', 'sha256:def']);
});
