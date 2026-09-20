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

/**
 * Emulates an engine that ignores `hourCycle` and renders midnight as hour 24
 * (ICU pattern `k`): the hour part becomes `24`, the calendar day stays the
 * day of the instant. Restored in `finally`; the file runs in its own process.
 */
function withHour24Midnight<T>(run: () => T): T {
  const real = Intl.DateTimeFormat;
  class Hour24DateTimeFormat extends real {
    override formatToParts(date?: Date | number): Intl.DateTimeFormatPart[] {
      return super.formatToParts(date).map((part) =>
        part.type === 'hour' && part.value === '00' ? { ...part, value: '24' } : part,
      );
    }
  }
  Intl.DateTimeFormat = Hour24DateTimeFormat as typeof Intl.DateTimeFormat;
  try {
    return run();
  } finally {
    Intl.DateTimeFormat = real;
  }
}

/**
 * Pinned `now` values for the offset sampling: the suite must never depend on
 * the wall clock it happens to run at. The set includes the instants that used
 * to poison the sampled offset (KF-3): minute :24, second :24 and the 24th day
 * of the month, plus Moscow midnight itself.
 */
const PINNED_CLOCKS = [
  '2026-08-29T21:00:00Z', // Moscow midnight
  '2026-09-07T10:24:30Z', // minute :24 -> old code sampled 156 min instead of 180
  '2026-09-07T10:10:24Z', // second :24
  '2026-09-24T10:00:00Z', // 24th day -> old code sampled a day (and more) back
  '2026-12-31T23:59:59.999Z',
].map((iso) => new Date(iso));

test('mskDay: dispatch acceptance values (Story 1.1)', () => {
  assert.equal(mskDay('2026-08-29T23:30:00Z'), '2026-08-30');
  assert.equal(mskDay('2026-08-29T20:59:59Z'), '2026-08-29');
});

test('mskDay: midnight boundary in both directions', () => {
  for (const now of PINNED_CLOCKS) {
    const at = `now=${now.toISOString()}`;
    assert.equal(mskDay('2026-08-29T21:00:00Z', now), '2026-08-30', at);
    assert.equal(mskDay('2026-08-29T20:59:59.999Z', now), '2026-08-29', at);
    assert.equal(mskDay('2026-01-01T00:00:00Z', now), '2026-01-01', at);
    assert.equal(mskDay('2025-12-31T21:00:00Z', now), '2026-01-01', at);
  }
});

test('mskToday/mskDay: a "24" in any part of the formatted `now` must not shift the offset (KF-3)', () => {
  assert.equal(mskToday(new Date('2026-09-07T10:24:30Z')), '2026-09-07');
  assert.equal(mskToday(new Date('2026-09-07T20:24:00Z')), '2026-09-07'); // 23:24 MSK
  assert.equal(mskToday(new Date('2026-09-07T21:24:00Z')), '2026-09-08'); // 00:24 MSK
  assert.equal(mskToday(new Date('2026-09-24T10:00:00Z')), '2026-09-24');
  assert.equal(mskToday(new Date('2026-09-23T21:00:00Z')), '2026-09-24'); // Moscow midnight on the 24th
  assert.equal(mskDay(new Date('2026-08-29T21:00:00Z'), new Date('2026-09-24T10:24:24Z')), '2026-08-30');
});

test('mskDay: midnight rendered as hour 24 folds to the same Moscow day', () => {
  const midnight = new Date('2026-08-29T21:00:00Z');
  withHour24Midnight(() => {
    assert.equal(mskToday(midnight), '2026-08-30');
    assert.equal(mskDay('2026-08-29T21:00:00Z', midnight), '2026-08-30');
    assert.equal(mskDay('2026-08-29T20:59:59.999Z', midnight), '2026-08-29');
  });
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
