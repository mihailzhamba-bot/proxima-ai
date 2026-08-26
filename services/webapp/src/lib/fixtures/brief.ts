/*
 * Structural fixtures для утреннего брифа (PA-49/PA-50, fixtures-first 2026-08-25).
 * Обезличено: fixture-* идентификаторы, структурные суммы без привязки к боевому кабинету (DEC-006).
 */

import type { GyrStatus } from "@/lib/gyr";

export type BriefVariant = "daily" | "quiet";

export type BriefSignal = {
  id: string;
  status: GyrStatus;
  title: string;
  cause: string;
  /** «Стоимость молчания», ₽/день — оценка потока, пока сигнал не обработан. */
  costEstimate: number;
};

export type BriefDigestItem = {
  id: string;
  tone: GyrStatus;
  text: string;
};

export type BriefData = {
  variant: BriefVariant;
  dateIso: string;
  /** Critical-строки брифа; рендерятся SignalRow. */
  signals: readonly BriefSignal[];
  attentionCount: number;
  digest: readonly BriefDigestItem[];
  dataMode: "fixtures";
};

const DAILY_SIGNALS: readonly BriefSignal[] = [
  {
    id: "fixture-brief-signal-oos",
    status: "red",
    title: "Хит выкупается в ноль",
    cause: "маржа после логистики ушла в минус",
    costEstimate: 41200,
  },
  {
    id: "fixture-brief-signal-cpc",
    status: "red",
    title: "Ставка РК перегрета",
    cause: "CPM вырос при падающей выкупаемости",
    costEstimate: 12800,
  },
];

const QUIET_DIGEST_EXTRA: readonly BriefDigestItem[] = [
  {
    id: "fixture-brief-digest-fresh",
    tone: "neutral",
    text: "Свежесть данных — 4 часа, следующий сбор ночью",
  },
];

const BASE_DIGEST: readonly BriefDigestItem[] = [
  {
    id: "fixture-brief-digest-orders",
    tone: "green",
    text: "Заказы за сутки держатся выше недельного уровня",
  },
  {
    id: "fixture-brief-digest-feedback",
    tone: "yellow",
    text: "Три отзыва про размер ждут ответа до вечера",
  },
];

function moscowDateIso(now: Date = new Date()): string {
  return new Intl.DateTimeFormat("sv-SE", { timeZone: "Europe/Moscow" }).format(now);
}

/** Геттер брифа: daily — редакционный день с critical-строками, quiet — «критичных нет» (R06.1). */
export function getBrief(variant: BriefVariant = "daily"): BriefData {
  if (variant === "quiet") {
    return {
      variant,
      dateIso: moscowDateIso(),
      signals: [],
      attentionCount: 3,
      digest: [...BASE_DIGEST, ...QUIET_DIGEST_EXTRA],
      dataMode: "fixtures",
    };
  }
  return {
    variant,
    dateIso: moscowDateIso(),
    signals: DAILY_SIGNALS,
    attentionCount: 5,
    digest: BASE_DIGEST,
    dataMode: "fixtures",
  };
}
