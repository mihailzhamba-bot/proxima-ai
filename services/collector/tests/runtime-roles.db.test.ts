// Database tests run only inside tools/pg_local_roundtrip.sh against a
// disposable PostgreSQL 16 provisioned by infra/bootstrap/provision-runtime-roles.sh
// (AD-11 / AD-12). Connections use the production LOGIN roles directly: no
// SET ROLE, no superuser. Without the harness env the file skips.
import assert from 'node:assert/strict';
import test from 'node:test';

import { Client } from 'pg';

const DSN_COLLECTOR = process.env.PROXIMA_TEST_DSN_COLLECTOR ?? '';
const DSN_SANDBOX = process.env.PROXIMA_TEST_DSN_SANDBOX ?? '';

const ready = DSN_COLLECTOR !== '' && DSN_SANDBOX !== '';

/** Rewrites the database name of a URI without touching credentials. */
function withDatabase(dsn: string, database: string): string {
  const parsed = new URL(dsn);
  parsed.pathname = `/${database}`;
  return parsed.toString();
}

test('collector role connects and serves SELECT 1', { skip: ready ? false : 'PROXIMA_TEST_DSN_COLLECTOR not set (run via tools/pg_local_roundtrip.sh)' }, async () => {
  const client = new Client({ connectionString: DSN_COLLECTOR });
  await client.connect();
  try {
    const result = await client.query<{ ok: number; user: string; db: string }>(
      'SELECT 1 AS ok, current_user AS user, current_database() AS db',
    );
    assert.equal(result.rows[0]?.ok, 1);
    assert.equal(result.rows[0]?.user, 'proxima_collector');
    assert.equal(result.rows[0]?.db, 'proxima');
  } finally {
    await client.end();
  }
});

test('sandbox role cannot connect to the main database', { skip: ready ? false : 'PROXIMA_TEST_DSN_SANDBOX not set (run via tools/pg_local_roundtrip.sh)' }, async () => {
  const client = new Client({ connectionString: withDatabase(DSN_SANDBOX, 'proxima') });
  await assert.rejects(client.connect(), (error: unknown) => {
    const message = error instanceof Error ? error.message : String(error);
    if (!/permission denied for database|does not have CONNECT privilege/i.test(message)) {
      throw new Error(`expected CONNECT rejection for proxima_sandbox, got: ${message}`);
    }
    return true;
  });
  await client.end().catch(() => undefined);
});

test('sandbox role cannot connect to the maintenance database', { skip: ready ? false : 'PROXIMA_TEST_DSN_SANDBOX not set (run via tools/pg_local_roundtrip.sh)' }, async () => {
  const client = new Client({ connectionString: withDatabase(DSN_SANDBOX, 'postgres') });
  await assert.rejects(client.connect(), (error: unknown) => {
    const message = error instanceof Error ? error.message : String(error);
    if (!/permission denied for database|does not have CONNECT privilege/i.test(message)) {
      throw new Error(`expected CONNECT rejection for proxima_sandbox, got: ${message}`);
    }
    return true;
  });
  await client.end().catch(() => undefined);
});

test('sandbox role connects to its test copy', { skip: ready ? false : 'PROXIMA_TEST_DSN_SANDBOX not set (run via tools/pg_local_roundtrip.sh)' }, async () => {
  const client = new Client({ connectionString: DSN_SANDBOX });
  await client.connect();
  try {
    const result = await client.query<{ user: string; db: string }>(
      'SELECT current_user AS user, current_database() AS db',
    );
    assert.equal(result.rows[0]?.user, 'proxima_sandbox');
    assert.equal(result.rows[0]?.db, 'proxima_test');
  } finally {
    await client.end();
  }
});
