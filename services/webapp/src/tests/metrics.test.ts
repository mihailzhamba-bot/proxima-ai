import { describe, expect, it } from "vitest";
import { getMetrics } from "@/lib/fixtures/metrics";

/*
 * Шов lib/fixtures (spec PA-49): форма данных метрической полосы стабильна.
 * Ожидания берутся из спецификации, не из реализации: 5 карточек,
 * 30 точек спарклайна, одна карточка без данных.
 */

describe("getMetrics", () => {
  const metrics = getMetrics();

  it("ровно пять карточек в порядке спецификации", () => {
    expect(metrics.map((m) => m.id)).toEqual([
      "signals",
      "revenue-day",
      "orders-day",
      "oos-risks",
      "freshness",
    ]);
  });

  it("метки карточек — русские строки из спецификации", () => {
    const labels = metrics.map((m) => m.label);
    expect(labels).toEqual([
      "Сигналы",
      "Выручка / день",
      "Заказы / день",
      "OOS-риски",
      "Свежесть данных",
    ]);
  });

  it("карточка со спарклайном несёт ровно 30 точек", () => {
    for (const metric of metrics) {
      if (metric.points.length > 0) {
        expect(metric.points).toHaveLength(30);
      }
    }
  });

  it("ровно одна карточка без данных (R05.1), и это OOS-риски", () => {
    const empty = metrics.filter((m) => m.value === null);
    expect(empty).toHaveLength(1);
    expect(empty[0]?.id).toBe("oos-risks");
  });

  it("карточки без данных не рисуют спарклайн и дельту", () => {
    for (const metric of metrics) {
      if (metric.value === null) {
        expect(metric.points).toEqual([]);
        expect(metric.deltaPercent).toBeNull();
      }
    }
  });

  it("дельты — конечные числа в процентах либо null", () => {
    for (const metric of metrics) {
      if (metric.deltaPercent !== null) {
        expect(Number.isFinite(metric.deltaPercent)).toBe(true);
      }
    }
  });

  it("провайдер помечает режим данных fixtures (DEC-006)", () => {
    expect(getMetrics.dataMode).toBe("fixtures");
  });
});
