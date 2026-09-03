import assert from 'node:assert/strict';
import test from 'node:test';

import { mskDay, mskInstant, mskToday } from '../src/wb/msk-day.js';

function withTimeZone<T>(zone: string | undefined, run: () => T): T {
  const previous = process.env.TZ;
  if (zone === undefined) delete process.env.TZ;
  else process.env.TZ = zone;
  try {
    return run();
  } finally {
    if (previous === undefined) delete process.env.TZ;
    else process.env.TZ = previous;
  }
}

test('mskDay: dispatch acceptance values (Story 1.1)', () => {
  assert.equal(mskDay('2026-08-29T23:30:00Z'), '2026-08-30');
  assert.equal(mskDay('2026-08-29T20:59:59Z'), '2026-08-29');
});

test('mskDay: midnight boundary in both directions', () => {
  assert.equal(mskDay('2026-08-29T21:00:00Z'), '2026-08-30');
  assert.equal(mskDay('2026-08-29T20:59:59.999Z'), '2026-08-29');
  assert.equal(mskDay('2026-01-01T00:00:00Z'), '2026-01-01');
  assert.equal(mskDay('2025-12-31T21:00:00Z'), '2026-01-01');
});

test('mskDay: explicit offsets are honoured', () => {
  assert.equal(mskDay('2026-08-30T00:30:00+03:00'), '2026-08-30');
  assert.equal(mskDay('2026-08-29T23:30:00+03:00'), '2026-08-29');
});

test('mskDay: WB zoneless timestamps are Moscow wall clock, not runtime-zone time', () => {
  withTimeZone(undefined, () => assert.equal(mskDay('2026-08-30T05:51:52'), '2026-08-30'));
  withTimeZone('Asia/Kamchatka', () => assert.equal(mskDay('2026-08-30T05:51:52'), '2026-08-30'));
  withTimeZone('America/New_York', () => assert.equal(mskDay('2026-08-30T02:00:00'), '2026-08-30'));
  withTimeZone('America/New_York', () => assert.equal(mskDay('2026-08-30T00:30:00Z'), '2026-08-30'));
});

test('mskDay: date-only input is already a Moscow calendar day', () => {
  assert.equal(mskDay('2026-08-30'), '2026-08-30');
});

test('mskDay: Date input behaves like an instant', () => {
  assert.equal(mskDay(new Date('2026-08-29T23:30:00Z')), '2026-08-30');
  assert.equal(mskDay(new Date('2026-08-29T20:59:59Z')), '2026-08-29');
});

test('mskDay: rejects invalid input instead of guessing', () => {
  assert.throws(() => mskDay('not-a-date'), RangeError);
  assert.throws(() => mskDay(''), RangeError);
});

test('mskToday is the Moscow day regardless of the runtime zone', () => {
  withTimeZone('UTC', () => assert.equal(mskToday(new Date('2026-08-29T21:30:00Z')), '2026-08-30'));
  withTimeZone('Asia/Kamchatka', () => assert.equal(mskToday(new Date('2026-08-29T21:30:00Z')), '2026-08-30'));
  withTimeZone('America/New_York', () => assert.equal(mskToday(new Date('2026-08-29T21:30:00Z')), '2026-08-30'));
});

test('mskDay agrees with Intl for the Moscow zone', () => {
  const instant = new Date('2026-08-29T21:30:00Z');
  const expected = new Intl.DateTimeFormat('en-CA', { timeZone: 'Europe/Moscow', dateStyle: 'short' }).format(instant);
  assert.equal(mskDay(instant), expected);
});

test('mskInstant: zoneless WB text becomes a fixed +03:00 instant, anything else is rejected', () => {
  assert.equal(mskInstant('2026-08-17T06:48:49'), '2026-08-17T06:48:49+03:00');
  assert.equal(mskInstant('2026-08-17T06:48:49.5'), '2026-08-17T06:48:49.5+03:00');
  assert.equal(Date.parse(mskInstant('2026-08-29T23:30:00')), Date.parse('2026-08-29T20:30:00Z'));
  assert.equal(mskDay(mskInstant('2026-08-29T23:30:00')), '2026-08-29');
  assert.throws(() => mskInstant('2026-08-17T06:48:49Z'), RangeError);
  assert.throws(() => mskInstant('2026-08-17T06:48:49+03:00'), RangeError);
  assert.throws(() => mskInstant('2026-08-17'), RangeError);
  assert.throws(() => mskInstant(''), RangeError);
});
