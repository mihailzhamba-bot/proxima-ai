// Story 4.0 (AD-19) fixture-level tests, no PostgreSQL: the nmId writer's two
// pure functions on the anonymised 30.08 fixtures (301 orders / 295 sales,
// 97 nmIds in the union) and on synthetic rows for the fail-closed rules.
// The gate `order-counts: per-nm sums vs cabinet` (tools/verify_nm_daily.py)
// runs this file: the per-nmId sums of summarizeNmDaily must equal
// summarizeCabinetDaily on every day for each of the six columns.
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { join } from 'node:path';
import test from 'node:test';

import { Decimal } from 'decimal.js';

import { summarizeCabinetDaily, type LatestObservationRow } from '../src/facts/cabinet-daily.js';
import { checkPerNmSumsVsCabinet, nmIdOf, summarizeNmDaily, summarizeNmSubjects, type NmDailyFact } from '../src/facts/nm-daily.js';
import { sha256 } from '../src/intake/manifest.js';
import { DEFAULT_FIXTURE_ROOT } from '../src/wb/fixture-transport.js';
import { mskInstant } from '../src/wb/msk-day.js';

const RUN = '00000000-0000-4000-8000-000000000001';
const EMPTY = 'c'.repeat(64);
const FLOOR = '2026-08-17';
const RUN_DAY = '2026-08-30';
const FIXTURE_DAYS = 13;
const FIXTURE_NM_IDS = 97;
const COLUMNS = ['ordersCount', 'cancelledCount', 'salesCount', 'returnsCount', 'revenueRub', 'forpayRub'] as const;

type Payload = Record<string, unknown> & { lastChangeDate: string };

async function fixtureRows(): Promise<{ rows: LatestObservationRow[]; ordersSha: string; salesSha: string }> {
  const orders = await readFile(join(DEFAULT_FIXTURE_ROOT, 'statistics/orders/sample.json'));
  const sales = await readFile(join(DEFAULT_FIXTURE_ROOT, 'statistics/sales/sample.json'));
  const ordersSha = sha256(orders);
  const salesSha = sha256(sales);
  const rows: LatestObservationRow[] = [
    ...(JSON.parse(orders.toString('utf8')) as Payload[]).map((payload) => ({ kind: 'order' as const, key: String(payload.srid), lastChangeAt: mskInstant(payload.lastChangeDate), runId: RUN, contentSha256: ordersSha, payload })),
    ...(JSON.parse(sales.toString('utf8')) as Payload[]).map((payload) => ({ kind: 'sale' as const, key: String(payload.saleID), lastChangeAt: mskInstant(payload.lastChangeDate), runId: RUN, contentSha256: salesSha, payload })),
  ];
  return { rows, ordersSha, salesSha };
}

function row(kind: 'order' | 'sale', key: string, lastChangeDate: string, payload: Record<string, unknown>, contentSha256 = 'a'.repeat(64)): LatestObservationRow {
  const base = { nmId: 12345001, subject: 'subject-1', category: 'category-1', brand: 'brand-1', supplierArticle: 'sku-1', date: '2026-08-18T10:00:00' };
  const full = kind === 'order' ? { ...base, srid: key, isCancel: false, ...payload } : { ...base, saleID: key, finishedPrice: '10.00', forPay: '8.00', ...payload };
  return { kind, key, lastChangeAt: mskInstant(lastChangeDate), runId: RUN, contentSha256, payload: full };
}

function sumBy(facts: readonly NmDailyFact[]): Map<string, Record<(typeof COLUMNS)[number], Decimal>> {
  const sums = new Map<string, Record<(typeof COLUMNS)[number], Decimal>>();
  for (const fact of facts) {
    const day = sums.get(fact.calendarDay) ?? { ordersCount: new Decimal(0), cancelledCount: new Decimal(0), salesCount: new Decimal(0), returnsCount: new Decimal(0), revenueRub: new Decimal(0), forpayRub: new Decimal(0) };
    for (const column of COLUMNS) day[column] = day[column].plus(fact[column]);
    sums.set(fact.calendarDay, day);
  }
  return sums;
}

test('nm-daily: per-nm sums vs cabinet - every day, all six columns, on the 30.08 fixtures', async () => {
  const { rows, ordersSha, salesSha } = await fixtureRows();
  const cabinet = summarizeCabinetDaily(rows, FLOOR, RUN_DAY, [EMPTY]);
  const facts = summarizeNmDaily(rows, FLOOR, RUN_DAY, [EMPTY]);
  assert.equal(cabinet.length, FIXTURE_DAYS);
  assert.equal(facts.length, FIXTURE_DAYS * FIXTURE_NM_IDS, 'one row per versioned day x nmId, zeros included');
  assert.equal(new Set(facts.map((fact) => `${fact.calendarDay}|${fact.nmId}`)).size, facts.length, '(day, nmId) is unique');
  const sums = sumBy(facts);
  for (const day of cabinet) {
    const perNm = sums.get(day.calendarDay);
    assert.ok(perNm, `nm rows exist for ${day.calendarDay}`);
    for (const column of COLUMNS) {
      assert.equal(perNm[column].toFixed(2), new Decimal(day[column]).toFixed(2), `${day.calendarDay} ${column}: per-nm sum equals the cabinet value`);
    }
  }
  const total = [...sums.values()].reduce((acc, day) => { for (const column of COLUMNS) acc[column] = acc[column].plus(day[column]); return acc; });
  assert.deepEqual(
    Object.fromEntries(COLUMNS.map((column) => [column, total[column].toFixed(2)])),
    { ordersCount: '255.00', cancelledCount: '45.00', salesCount: '292.00', returnsCount: '2.00', revenueRub: '277569.02', forpayRub: '222240.77' },
    'fixture totals 2026-08-17..29 (orders without isCancel, S sales with finishedPrice/forPay, R returns)',
  );
  // Evidence: a zero cell carries the run's artifacts like a zero cabinet day; a
  // non-zero cell carries the hashes of the responses its observations came from.
  const zero = facts.filter((fact) => COLUMNS.every((column) => new Decimal(fact[column]).isZero()));
  assert.ok(zero.length > 0, 'the fixtures leave some (day, nmId) cells without observations');
  for (const fact of zero) assert.deepEqual(fact.evidenceSha256, [EMPTY]);
  for (const fact of facts.filter((fact) => !zero.includes(fact))) {
    assert.ok(fact.evidenceSha256.length >= 1 && fact.evidenceSha256.every((sha) => sha === ordersSha || sha === salesSha), 'evidence of a non-zero cell is the orders/sales response hash');
  }
  // Ordered by day, then nmId - a stable shape for the bulk insert and for diffs.
  const ordered = [...facts].sort((a, b) => (a.calendarDay === b.calendarDay ? a.nmId - b.nmId : a.calendarDay < b.calendarDay ? -1 : 1));
  assert.deepEqual(facts.map((fact) => `${fact.calendarDay}|${fact.nmId}`), ordered.map((fact) => `${fact.calendarDay}|${fact.nmId}`));
});

test('nm-daily: one dictionary version per nmId of orders UNION sales on the fixtures', async () => {
  const { rows, ordersSha, salesSha } = await fixtureRows();
  const subjects = summarizeNmSubjects(rows);
  assert.equal(subjects.length, FIXTURE_NM_IDS);
  assert.deepEqual(subjects.map((subject) => subject.nmId), [...subjects.map((subject) => subject.nmId)].sort((a, b) => a - b), 'sorted by nmId');
  assert.equal(new Set(subjects.map((subject) => subject.nmId)).size, FIXTURE_NM_IDS);
  for (const subject of subjects) {
    assert.match(subject.subjectName, /^subject-\d+$/);
    assert.match(subject.categoryName, /^category-\d+$/);
    assert.match(subject.brand, /^brand-\d+$/);
    assert.match(subject.supplierArticle, /^sku-\d+$/);
    assert.ok(subject.evidenceSha256 === ordersSha || subject.evidenceSha256 === salesSha);
    assert.ok(!Number.isNaN(Date.parse(subject.lastChangeAt)));
  }
  // The dictionary and the daily rows are built from the same rows, so their nmId sets agree.
  const factNmIds = new Set(summarizeNmDaily(rows, FLOOR, RUN_DAY, [EMPTY]).map((fact) => fact.nmId));
  assert.deepEqual([...factNmIds].sort((a, b) => a - b), subjects.map((subject) => subject.nmId));
});

test('nm-daily: dictionary winner - greatest lastChangeDate, then order before sale, then greater key', () => {
  // A later sale beats an earlier order.
  let versions = summarizeNmSubjects([
    row('order', 'o-1', '2026-08-18T10:00:00', { subject: 'subject-old' }),
    row('sale', 'S-1', '2026-08-19T10:00:00', { subject: 'subject-new', brand: 'brand-new' }),
  ]);
  assert.equal(versions.length, 1);
  assert.deepEqual([versions[0]?.subjectName, versions[0]?.brand, versions[0]?.lastChangeAt], ['subject-new', 'brand-new', '2026-08-19T10:00:00+03:00']);
  // Equal instants: the order wins over the sale.
  versions = summarizeNmSubjects([
    row('sale', 'S-1', '2026-08-19T10:00:00', { subject: 'subject-sale' }),
    row('order', 'o-1', '2026-08-19T10:00:00', { subject: 'subject-order' }),
  ]);
  assert.equal(versions[0]?.subjectName, 'subject-order');
  // Equal instants and kind: the greater key wins.
  versions = summarizeNmSubjects([
    row('order', 'o-2', '2026-08-19T10:00:00', { subject: 'subject-two' }),
    row('order', 'o-10', '2026-08-19T10:00:00', { subject: 'subject-ten' }),
  ]);
  assert.equal(versions[0]?.subjectName, 'subject-two', 'string comparison: "o-2" > "o-10"');
  // The winner's instant may arrive as UTC text (the SQL loader) or with the Moscow offset.
  versions = summarizeNmSubjects([
    { ...row('order', 'o-1', '2026-08-19T10:00:00', { subject: 'subject-msk' }) },
    { ...row('sale', 'S-1', '2026-08-19T10:00:00', { subject: 'subject-utc' }), lastChangeAt: '2026-08-19T07:00:01.000Z' },
  ]);
  assert.equal(versions[0]?.subjectName, 'subject-utc', '07:00:01Z is one second after 10:00:00+03:00');
});

test('nm-daily: fail-closed on nmId, WB_SCHEMA_DRIFT on a missing dictionary key, empty string is a literal', () => {
  const rows = [row('order', 'o-1', '2026-08-18T10:00:00', {})];
  for (const nmId of [undefined, 0, -5, 1.5, '12345001', null]) {
    const bad = [{ ...rows[0]!, payload: { ...rows[0]!.payload, nmId } }];
    assert.throws(() => summarizeNmSubjects(bad), RangeError, `nmId ${String(nmId)} fails the dictionary`);
    assert.throws(() => summarizeNmDaily(bad, FLOOR, RUN_DAY, [EMPTY]), RangeError, `nmId ${String(nmId)} fails the daily rows`);
    assert.throws(() => nmIdOf(bad[0]!), RangeError);
  }
  for (const field of ['subject', 'category', 'brand', 'supplierArticle']) {
    const { [field]: _dropped, ...withoutField } = rows[0]!.payload;
    assert.throws(() => summarizeNmSubjects([{ ...rows[0]!, payload: withoutField }]), (error: unknown) => (error as { code?: string }).code === 'WB_SCHEMA_DRIFT', `missing ${field} is drift`);
    assert.throws(() => summarizeNmSubjects([{ ...rows[0]!, payload: { ...withoutField, [field]: null } }]), (error: unknown) => (error as { code?: string }).code === 'WB_SCHEMA_DRIFT', `null ${field} is drift`);
  }
  const empty = summarizeNmSubjects([row('order', 'o-1', '2026-08-18T10:00:00', { brand: '' })]);
  assert.equal(empty[0]?.brand, '', 'an empty brand is a visible literal group, not an error');
  // Only the winning observation's dictionary keys are read: an older row without them does not fail the run.
  const older = summarizeNmSubjects([
    { ...row('order', 'o-0', '2026-08-01T10:00:00', {}), payload: { nmId: 12345001, srid: 'o-0', date: '2026-08-01T10:00:00' } },
    row('order', 'o-1', '2026-08-18T10:00:00', { subject: 'subject-current' }),
  ]);
  assert.equal(older[0]?.subjectName, 'subject-current');
  // Daily rows keep the cabinet's fail-closed date and evidence checks.
  assert.throws(() => summarizeNmDaily([{ ...rows[0]!, payload: { ...rows[0]!.payload, date: 17 } }], FLOOR, RUN_DAY, [EMPTY]), RangeError);
  assert.throws(() => summarizeNmDaily([{ ...rows[0]!, contentSha256: 'nope' }], FLOOR, RUN_DAY, [EMPTY]), RangeError);
  assert.throws(() => summarizeNmDaily(rows, RUN_DAY, FLOOR, [EMPTY]), RangeError, 'floor after run day');
});

test('nm-daily: observations outside [floor, run_day) shape the dictionary but not the counts', () => {
  const rows = [
    row('order', 'o-early', '2026-08-10T10:00:00', { date: '2026-08-10T10:00:00', nmId: 12345001 }),
    row('order', 'o-run-day', '2026-08-23T10:00:00', { date: '2026-08-23T10:00:00', nmId: 12345002 }),
    row('sale', 'S-in', '2026-08-22T10:00:00', { date: '2026-08-22T10:00:00', nmId: 12345003, finishedPrice: 12.5, forPay: 10 }),
    row('sale', 'R-in', '2026-08-22T11:00:00', { date: '2026-08-22T11:00:00', nmId: 12345003, finishedPrice: 99, forPay: 99 }),
    row('order', 'o-cancel', '2026-08-21T10:00:00', { date: '2026-08-21T10:00:00', nmId: 12345003, isCancel: true }),
  ];
  const facts = summarizeNmDaily(rows, '2026-08-21', '2026-08-23', [EMPTY]);
  assert.equal(facts.length, 2 * 3, 'two days x three nmIds');
  const at = (day: string, nmId: number): NmDailyFact => { const fact = facts.find((item) => item.calendarDay === day && item.nmId === nmId); assert.ok(fact); return fact; };
  assert.deepEqual(at('2026-08-22', 12345003), { calendarDay: '2026-08-22', nmId: 12345003, ordersCount: 0, cancelledCount: 0, salesCount: 1, returnsCount: 1, revenueRub: '12.50', forpayRub: '10.00', evidenceSha256: ['a'.repeat(64)] });
  assert.deepEqual(at('2026-08-21', 12345003), { calendarDay: '2026-08-21', nmId: 12345003, ordersCount: 0, cancelledCount: 1, salesCount: 0, returnsCount: 0, revenueRub: '0.00', forpayRub: '0.00', evidenceSha256: ['a'.repeat(64)] });
  for (const [day, nmId] of [['2026-08-21', 12345001], ['2026-08-22', 12345001], ['2026-08-21', 12345002], ['2026-08-22', 12345002]] as const) {
    assert.deepEqual(at(day, nmId), { calendarDay: day, nmId, ordersCount: 0, cancelledCount: 0, salesCount: 0, returnsCount: 0, revenueRub: '0.00', forpayRub: '0.00', evidenceSha256: [EMPTY] }, `${day} ${nmId} is a zero row with the run evidence`);
  }
  assert.equal(summarizeNmSubjects(rows).length, 3, 'every nmId of the rows gets a dictionary version, whatever its day');
});

test('nm-daily: per_nm_sums_vs_cabinet result shape from the check rows', async () => {
  const queries: { text: string; values: readonly unknown[] }[] = [];
  type CheckClient = Parameters<typeof checkPerNmSumsVsCabinet>[0];
  const fake = (rows: object[]): CheckClient => ({
    query: async (text: string, values?: readonly unknown[]) => { queries.push({ text, values: values ?? [] }); return { rows, rowCount: rows.length }; },
  }) as unknown as CheckClient;
  const columns = ['orders_count', 'cancelled_count', 'sales_count', 'returns_count', 'revenue_rub', 'forpay_rub'];
  const days = ['2026-08-28', '2026-08-29'];
  const clean = days.flatMap((day) => columns.map((column) => ({ calendar_day: day, column_name: column, cabinet: '1', per_nm_sum: '1', mismatch: false })));
  const pass = await checkPerNmSumsVsCabinet(fake(clean), { tenantId: 'amirova-test', runId: RUN });
  assert.deepEqual(pass, { check: 'per_nm_sums_vs_cabinet', status: 'PASS', days_checked: 2, mismatches: [] });
  assert.deepEqual(queries[0]?.values, ['amirova-test', RUN]);
  assert.match(queries[0]?.text ?? '', /FROM fact_nm_daily\s+WHERE tenant_id = \$1 AND run_id = \$2/, 'with a run id the base table of the run is checked');
  assert.match(queries[0]?.text ?? '', /FROM fact_cabinet_daily c/);
  const broken = clean.map((item, index) => (index === 4 ? { ...item, cabinet: '10.00', per_nm_sum: '9.50', mismatch: true } : item));
  const mismatch = await checkPerNmSumsVsCabinet(fake(broken), { tenantId: 'amirova-test' });
  assert.deepEqual(mismatch, { check: 'per_nm_sums_vs_cabinet', status: 'MISMATCH', days_checked: 2, mismatches: [{ calendar_day: '2026-08-28', column: 'revenue_rub', cabinet: '10.00', per_nm_sum: '9.50' }] });
  assert.deepEqual(queries[1]?.values, ['amirova-test']);
  assert.match(queries[1]?.text ?? '', /FROM fact_nm_daily_current\s+WHERE tenant_id = \$1\s+GROUP BY/, 'without a run id the _current views are checked');
  assert.match(queries[1]?.text ?? '', /FROM fact_cabinet_daily_current c/);
  await assert.rejects(() => checkPerNmSumsVsCabinet(fake([{ calendar_day: '2026-08-28', column_name: 'orders', cabinet: '1', per_nm_sum: '1', mismatch: false }]), { tenantId: 'amirova-test' }), RangeError);
});
