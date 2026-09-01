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
      hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false,
    }).formatToParts(now);
  } catch {
    return MSK_UTC_OFFSET_MINUTES;
  }
  const field = (type: Intl.DateTimeFormatPartTypes): number => {
    const raw = parts.find((part) => part.type === type)?.value ?? '';
    return Number(raw === '24' ? '00' : raw);
  };
  const year = field('year');
  const month = field('month');
  const day = field('day');
  const hour = field('hour');
  const minute = field('minute');
  const second = field('second');
  if ([year, month, day, hour, minute, second].some((value) => !Number.isSafeInteger(value))) {
    return MSK_UTC_OFFSET_MINUTES;
  }
  const wallAsUtc = Date.UTC(year, month - 1, day, hour, minute, second);
  const truncatedNow = Math.floor(now.getTime() / 1000) * 1000;
  return Math.round((wallAsUtc - truncatedNow) / 60_000);
}
