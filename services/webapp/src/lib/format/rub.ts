const rubFormatter = new Intl.NumberFormat("ru-RU", {
  style: "currency",
  currency: "RUB",
  maximumFractionDigits: 0,
});

const rubFormatterPrecise = new Intl.NumberFormat("ru-RU", {
  style: "currency",
  currency: "RUB",
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

/** `1234567` -> `1 234 567 ₽` (без копеек, узкий пробел, ru-RU) */
export function formatRub(value: number): string {
  if (!Number.isFinite(value)) {
    throw new TypeError(`formatRub: value must be finite, got ${String(value)}`);
  }
  return rubFormatter.format(value);
}

/** `1234.5` -> `1 234,50 ₽` (с копейками) */
export function formatRubPrecise(value: number): string {
  if (!Number.isFinite(value)) {
    throw new TypeError(`formatRubPrecise: value must be finite, got ${String(value)}`);
  }
  return rubFormatterPrecise.format(value);
}

/** Компактные суммы для карточек: миллионы/тысячи. `1250000` -> `1,25 млн ₽` */
export function formatRubCompact(value: number): string {
  if (!Number.isFinite(value)) {
    throw new TypeError(`formatRubCompact: value must be finite, got ${String(value)}`);
  }
  const abs = Math.abs(value);
  if (abs >= 1_000_000) {
    return `${(value / 1_000_000).toLocaleString("ru-RU", { maximumFractionDigits: 2 })} млн ₽`;
  }
  if (abs >= 10_000) {
    return `${Math.round(value / 1_000).toLocaleString("ru-RU")} тыс. ₽`;
  }
  return formatRub(value);
}
