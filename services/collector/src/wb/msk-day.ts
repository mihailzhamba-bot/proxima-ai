const MSK_UTC_OFFSET_MINUTES = 180;
const ZONELESS_DATETIME = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?$/;
const ZONELESS_DATE = /^\d{4}-\d{2}-\d{2}$/;

/**
 * The single place that converts an instant into a Europe/Moscow calendar day
 * (AD-7). WB `date`/`lastChangeDate` arrive as Moscow wall-clock text without a
 * zone, so zoneless input is read as Moscow time, never as the runtime zone.
 */
export function mskDay(value: string | Date, now: Date = new Date()): string {
  if (value instanceof Date) return moscowDate(value.getTime(), now);
  if (typeof value !== 'string') throw new RangeError(`mskDay: unsupported input ${JSON.stringify(value)}`);
  if (ZONELESS_DATE.test(value)) return value;
  if (ZONELESS_DATETIME.test(value)) return value.slice(0, 10);
  const instant = Date.parse(value);
  if (Number.isNaN(instant)) throw new RangeError(`mskDay: invalid instant ${JSON.stringify(value)}`);
  return moscowDate(instant, now);
}

export function mskToday(now: Date = new Date()): string {
  return moscowDate(now.getTime(), now);
}

/**
 * Zoneless WB wall-clock text (`2026-08-17T06:48:49`) as an unambiguous
 * instant: the same text with the fixed Moscow offset. Moscow has had no DST
 * since 2014, so the mapping is bijective and a stored `last_change_at` can be
 * turned back into a WB `dateFrom` cursor (Story 1.5 --resume). Input that
 * already carries a zone or has another shape is rejected, never guessed.
 */
export function mskInstant(value: string): string {
  if (typeof value !== 'string' || !ZONELESS_DATETIME.test(value)) {
    throw new RangeError(`mskInstant: expected zoneless Moscow datetime, got ${JSON.stringify(value)}`);
  }
  return `${value}+03:00`;
}

function moscowDate(epochMilliseconds: number, now: Date): string {
  return new Date(epochMilliseconds + moscowOffsetMinutes(now) * 60_000).toISOString().slice(0, 10);
}

/**
 * Europe/Moscow offset in minutes east of UTC, taken from the runtime zone
 * database on purpose: if Moscow ever reintroduces DST, only this helper has
 * to notice.
 */
function moscowOffsetMinutes(now: Date): number {
  let parts: Intl.DateTimeFormatPart[];
  try {
    parts = new Intl.DateTimeFormat('en-US', {
      timeZone: 'Europe/Moscow',
      year: 'numeric', month: '2-digit', day: '2-digit',
      hour: '2-digit', minute: '2-digit', second: '2-digit', hourCycle: 'h23',
    }).formatToParts(now);
  } catch {
    return MSK_UTC_OFFSET_MINUTES;
  }
  const field = (type: Intl.DateTimeFormatPartTypes): number =>
    Number(parts.find((part) => part.type === type)?.value ?? '');
  const year = field('year');
  const month = field('month');
  const day = field('day');
  // An engine that ignores `hourCycle` and renders midnight as hour 24 keeps
  // the calendar day of the instant, so only the hour is folded back to 0.
  // Nothing else may be rewritten: a blanket `'24' -> '00'` on every part
  // also zeroed minute :24 and the 24th day of the month, shifting the
  // sampled offset by 24 minutes or a full day (KF-3).
  const hour = field('hour') % 24;
  const minute = field('minute');
  const second = field('second');
  if ([year, month, day, hour, minute, second].some((value) => !Number.isSafeInteger(value))) {
    return MSK_UTC_OFFSET_MINUTES;
  }
  const wallAsUtc = Date.UTC(year, month - 1, day, hour, minute, second);
  const truncatedNow = Math.floor(now.getTime() / 1000) * 1000;
  return Math.round((wallAsUtc - truncatedNow) / 60_000);
}
