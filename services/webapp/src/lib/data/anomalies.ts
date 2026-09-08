import type { SignalV1 } from "@/lib/contracts/signal";
import type { AnomalyLevel, AnomalyMetric, BriefAnomaly, SummaryMetric } from "@/lib/data/view-model";

/*
 * Проводной сигнал (signal v1, AD-10) -> строка блока «Аномалии» (Story 4.3).
 *
 * `detection_data` - словарь `{value, is_unknown}` по ключам детектора SCN-001
 * (`detector/signals.py`): `nm_id`, `supplier_article`, `subject_name` webapp берёт
 * отсюда, а не из фактов (AD-19). Здесь нет арифметики: экран не считает ни
 * отклонения, ни деньги - только читает уже посчитанное. Всё, что помечено
 * `is_unknown` или отсутствует, становится null: недостающее значение не
 * достраивается (fail-closed, «не выдумывать данные»).
 */

const MONEY = /^-?[0-9]+\.[0-9]{2}$/;
const METRICS: readonly AnomalyMetric[] = ["orders", "revenue"];

type Entry = { value?: unknown; is_unknown?: unknown };

function knownValue(data: SignalV1["detection_data"], key: string): unknown {
  const entry = data[key] as Entry | undefined;
  if (entry === undefined || entry.is_unknown !== false) {
    return null;
  }
  return entry.value ?? null;
}

function knownNumber(data: SignalV1["detection_data"], key: string): number | null {
  const value = knownValue(data, key);
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function knownInteger(data: SignalV1["detection_data"], key: string): number | null {
  const value = knownNumber(data, key);
  return value !== null && Number.isInteger(value) ? value : null;
}

function knownString(data: SignalV1["detection_data"], key: string): string | null {
  const value = knownValue(data, key);
  return typeof value === "string" && value.length > 0 ? value : null;
}

/** Деньги приходят строкой AD-10; число или строка другой формы - не деньги. */
function knownMoney(data: SignalV1["detection_data"], key: string): string | null {
  const value = knownString(data, key);
  return value !== null && MONEY.test(value) ? value : null;
}

/** Факт заказов детектор пишет целым, дробную сумму - строкой (см. `_int` в signals.py). */
function knownCount(data: SignalV1["detection_data"], key: string): number | string | null {
  const value = knownValue(data, key);
  if (typeof value === "number" && Number.isFinite(value)) {
    return value;
  }
  return typeof value === "string" && MONEY.test(value) ? value : null;
}

function isMetric(value: unknown): value is AnomalyMetric {
  return typeof value === "string" && (METRICS as readonly string[]).includes(value);
}

function triggeredBy(data: SignalV1["detection_data"]): readonly AnomalyMetric[] {
  const value = knownValue(data, "triggered_by");
  return Array.isArray(value) ? value.filter(isMetric) : [];
}

function metric(actual: number | string | null, norm: string | null, deviationPct: number | null): SummaryMetric | null {
  return actual === null ? null : { actual, norm, deviationPct };
}

function level(data: SignalV1["detection_data"], nmId: number | null): AnomalyLevel {
  const value = knownString(data, "level");
  if (value === "sku" || value === "subject") {
    return value;
  }
  // Уровень не назван: строка с nmId - SKU, без него - предмет.
  return nmId === null ? "subject" : "sku";
}

/** Одна строка экрана из одного сигнала; порядок и состав решает вызывающий код. */
export function anomalyFromSignal(signal: SignalV1): BriefAnomaly {
  const data = signal.detection_data;
  const nmId = knownInteger(data, "nm_id");
  return {
    id: signal.signal_id,
    scenarioCode: signal.scenario_code,
    level: level(data, nmId),
    nmId,
    supplierArticle: knownString(data, "supplier_article"),
    subjectName: knownString(data, "subject_name"),
    skuCount: knownInteger(data, "sku_count"),
    triggeredBy: triggeredBy(data),
    orders: metric(knownCount(data, "orders_actual"), knownMoney(data, "orders_norm_median"), knownNumber(data, "orders_deviation_pct")),
    revenue: metric(knownMoney(data, "revenue_actual"), knownMoney(data, "revenue_norm_median"), knownNumber(data, "revenue_deviation_pct")),
    moneyAtRisk: signal.rub_assessment === null ? null : signal.rub_assessment.value_rub,
    moneyMethod: signal.rub_assessment === null ? null : signal.rub_assessment.method,
    thresholdPct: knownNumber(data, "threshold_pct"),
    sourceRefs: [...signal.source_refs],
    trust: signal.trust_marking,
  };
}

/**
 * `signals[]` брифа -> строки блока в том же порядке (AC Story 4.3: порядок строк
 * = порядок `signals[]`; ранжирование по деньгам сделал control-plane, Story 4.2).
 */
export function anomaliesFromSignals(signals: readonly SignalV1[]): BriefAnomaly[] {
  return signals.map(anomalyFromSignal);
}
