import { SIGNAL_WINDOW_DAYS, type SignalWindow } from './types.js';

const MOSCOW_OFFSET_MS = 3 * 60 * 60 * 1000;

function isoDateFromMoscowInstant(now: Date): string {
  return new Date(now.getTime() + MOSCOW_OFFSET_MS).toISOString().slice(0, 10);
}

function shiftDate(isoDate: string, days: number): string {
  const instant = new Date(`${isoDate}T00:00:00Z`);
  instant.setUTCDate(instant.getUTCDate() + days);
  return instant.toISOString().slice(0, 10);
}

export function completedSignalWindow(now: Date): SignalWindow {
  const today = isoDateFromMoscowInstant(now);
  const to = shiftDate(today, -1);
  return { from: shiftDate(to, -(SIGNAL_WINDOW_DAYS - 1)), to };
}

export function moscowWindowBounds(window: SignalWindow): { from: string; to: string } {
  return {
    from: `${window.from}T00:00:00+03:00`,
    to: `${window.to}T23:59:59.999+03:00`,
  };
}

export function isInsideWindow(value: string, window: SignalWindow): boolean {
  const instant = new Date(value);
  if (Number.isNaN(instant.getTime())) return false;
  const date = isoDateFromMoscowInstant(instant);
  return date >= window.from && date <= window.to;
}
