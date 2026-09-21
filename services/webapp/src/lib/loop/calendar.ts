/** UTC+3 Moscow calendar; the pilot does not use the host timezone. */
export function lastFullMoscowDay(now: Date): string {
  return new Date(now.getTime() + 3 * 3_600_000 - 86_400_000).toISOString().slice(0, 10);
}
export function moscowDayAt(time: Date): string {
  return new Date(time.getTime() + 3 * 3_600_000).toISOString().slice(0, 10);
}
