/*
 * Метрическая полоса (R05): структурные обезличенные данные для 5 карточек.
 * PA-50 подменит провайдер живыми данными — форма FixtureMetric остаётся.
 * Значения структурные (DEC-006: unreleased, fixtures-режим).
 */

import type { GyrStatus } from "@/lib/gyr";

export type MetricId = "signals" | "revenue-day" | "orders-day" | "oos-risks" | "freshness";

export type MetricFormat = "count" | "rub-compact" | "clock";

export type FixtureMetric = {
  id: MetricId;
  label: string;
  value: number | null;
  format: MetricFormat;
  status: GyrStatus | null;
  deltaPercent: number | null;
  deltaGoodWhen: "up" | "down" | null;
  points: readonly number[];
};

const SIGNAL_POINTS = [
  4, 3, 5, 4, 6, 5, 4, 3, 4, 2, 3, 4, 5, 3, 2, 3, 4, 3, 2, 3, 4, 3, 2, 3, 2, 3, 2, 2, 3, 2,
];

const REVENUE_POINTS = [
  812, 845, 790, 868, 902, 874, 915, 889, 934, 921, 958, 942, 987, 963, 1001, 978, 1024, 996,
  1042, 1018, 1063, 1047, 1081, 1059, 1096, 1072, 1113, 1088, 1124, 1102,
];

const ORDER_POINTS = [
  318, 327, 305, 336, 348, 341, 355, 349, 362, 358, 371, 365, 380, 374, 388, 381, 395, 389,
  402, 396, 411, 404, 417, 409, 423, 415, 429, 421, 434, 428,
];

function buildMetrics(): readonly FixtureMetric[] {
  return [
    {
      id: "signals",
      label: "Сигналы",
      value: 2,
      format: "count",
      status: "red",
      deltaPercent: -33.3,
      deltaGoodWhen: "down",
      points: SIGNAL_POINTS,
    },
    {
      id: "revenue-day",
      label: "Выручка / день",
      value: 1_234_567,
      format: "rub-compact",
      status: null,
      deltaPercent: 8.4,
      deltaGoodWhen: "up",
      points: REVENUE_POINTS,
    },
    {
      id: "orders-day",
      label: "Заказы / день",
      value: 412,
      format: "count",
      status: null,
      deltaPercent: 5.1,
      deltaGoodWhen: "up",
      points: ORDER_POINTS,
    },
    {
      id: "oos-risks",
      label: "OOS-риски",
      value: null,
      format: "count",
      status: null,
      deltaPercent: null,
      deltaGoodWhen: null,
      points: [],
    },
    {
      id: "freshness",
      label: "Свежесть данных",
      value: 6 * 60 + 12,
      format: "clock",
      status: "green",
      deltaPercent: null,
      deltaGoodWhen: null,
      points: [],
    },
  ];
}

export const getMetrics = Object.assign(buildMetrics, { dataMode: "fixtures" } as const);
