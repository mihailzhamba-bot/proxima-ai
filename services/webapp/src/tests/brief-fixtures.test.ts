import { readFileSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { GYR_STATUSES, isGyrStatus } from "@/lib/gyr";
import type { SignalV1 } from "@/lib/contracts/signal";
import { RISK_LEVELS, type SignalHypothesis } from "@/lib/data/view-model";
import { FIXTURE_BRIEF_SIGNALS, getBrief, getSummary, type BriefSignal } from "@/lib/fixtures/brief";

const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/;
const MONEY_STRING = /^-?[0-9]+\.[0-9]{2}$/;

// src/tests -> src -> webapp -> services -> repo root
const REPO_ROOT = fileURLToPath(new URL("../../../..", import.meta.url));

function expectHypothesisGrounded(hypothesis: SignalHypothesis, signal: BriefSignal) {
  expect(hypothesis.id.startsWith("fixture-")).toBe(true);
  expect(hypothesis.text.length).toBeGreaterThan(0);
  expect(hypothesis.sourceRefIds.length).toBeGreaterThan(0);
  for (const refId of hypothesis.sourceRefIds) {
    expect(signal.sourceRefs.some((ref) => ref.id === refId)).toBe(true);
  }
}

function expectValidSignal(signal: BriefSignal) {
  expect(signal.id.startsWith("fixture-")).toBe(true);
  expect(isGyrStatus(signal.status)).toBe(true);
  expect(signal.title.length).toBeGreaterThan(0);
  expect(signal.cause.length).toBeGreaterThan(0);
  expect(Number.isFinite(signal.costEstimate)).toBe(true);
  expect(signal.costEstimate).toBeGreaterThan(0);
}

describe("getBrief — шов провайдера брифа", () => {
  it("ежедневный вариант: 2 критичных / 5 внимания (утверждённая копия брифа)", () => {
    const brief = getBrief();
    expect(brief.variant).toBe("daily");
    expect(brief.signals.length).toBe(2);
    expect(brief.attentionCount).toBe(5);
  });

  it("форма стабильна: дата ISO, режим fixtures, дайджест 2-3 пункта", () => {
    const brief = getBrief();
    expect(brief.dataMode).toBe("fixtures");
    expect(brief.dateIso).toMatch(ISO_DATE);
    expect(new Date(`${brief.dateIso}T00:00:00Z`).getUTCFullYear()).toBeGreaterThan(2025);
    expect(brief.digest.length).toBeGreaterThanOrEqual(2);
    expect(brief.digest.length).toBeLessThanOrEqual(3);
  });

  it("каждый сигнал обезличен и полон: fixture-id, GYR-статус, причина, ₽-оценка", () => {
    for (const signal of getBrief().signals) {
      expectValidSignal(signal);
    }
  });

  it("карточка сигнала укомплектована по PA-38: период, R-уровень, рекомендация, trust", () => {
    for (const signal of getBrief().signals) {
      expect(signal.period.length).toBeGreaterThan(0);
      expect(RISK_LEVELS).toContain(signal.riskLevel);
      expect(signal.trust).toBe("unreleased");
      expect(signal.recommendation.length).toBeGreaterThan(0);
    }
  });

  it("причина и 2-3 альтернативы опираются на объявленные источники", () => {
    for (const signal of getBrief().signals) {
      expectHypothesisGrounded(signal.primaryCause, signal);
      expect(signal.alternatives.length).toBeGreaterThanOrEqual(2);
      expect(signal.alternatives.length).toBeLessThanOrEqual(3);
      for (const alternative of signal.alternatives) {
        expectHypothesisGrounded(alternative, signal);
      }
    }
  });

  it("«что неизвестно» непусто и объясняет, почему вопрос меняет решение", () => {
    for (const signal of getBrief().signals) {
      expect(signal.unknowns.length).toBeGreaterThan(0);
      for (const unknown of signal.unknowns) {
        expect(unknown.id.startsWith("fixture-")).toBe(true);
        expect(unknown.question.length).toBeGreaterThan(0);
        expect(unknown.whyItMatters.length).toBeGreaterThan(0);
      }
    }
  });

  it("каждый SourceRef несёт данные + период + источник (PA-38)", () => {
    for (const signal of getBrief().signals) {
      expect(signal.sourceRefs.length).toBeGreaterThan(0);
      for (const ref of signal.sourceRefs) {
        expect(ref.id.startsWith("fixture-")).toBe(true);
        expect(ref.label.length).toBeGreaterThan(0);
        expect(ref.period.length).toBeGreaterThan(0);
        expect(ref.source.length).toBeGreaterThan(0);
      }
    }
  });

  it("каждый пункт дайджеста: fixture-id, тон из GYR, непустой текст", () => {
    for (const item of getBrief().digest) {
      expect(item.id.startsWith("fixture-")).toBe(true);
      expect(GYR_STATUSES).toContain(item.tone);
      expect(item.text.length).toBeGreaterThan(0);
    }
  });

  it("тихий вариант: критичных нет, дайджест остаётся (R06.1)", () => {
    const quiet = getBrief("quiet");
    expect(quiet.variant).toBe("quiet");
    expect(quiet.signals).toHaveLength(0);
    expect(quiet.digest.length).toBeGreaterThanOrEqual(2);
    expect(quiet.attentionCount).toBeGreaterThanOrEqual(0);
  });
});

/*
 * Проводной контракт signal v1 (contracts/signal.schema.json) без Ajv - в webapp
 * его нет, а новые зависимости запрещены. Проверка структурная и ведётся по самой
 * схеме: набор ключей (additionalProperties: false), enum'ы, шаблон денег AD-10,
 * minItems у source_refs, шаблон ключей и форма записей detection_data. Полная
 * jsonschema-валидация примеров - гейт `make contracts` (Python).
 */
type JsonSchema = {
  required: string[];
  properties: Record<string, JsonSchema & Record<string, unknown>>;
  additionalProperties?: boolean | (JsonSchema & Record<string, unknown>);
  enum?: unknown[];
  pattern?: string;
  minItems?: number;
  anyOf?: (JsonSchema & Record<string, unknown>)[];
  propertyNames?: { pattern: string };
};

function loadSignalSchema(): JsonSchema {
  return JSON.parse(readFileSync(join(REPO_ROOT, "contracts", "signal.schema.json"), "utf8")) as JsonSchema;
}

function expectSignalMatchesContract(signal: SignalV1, schema: JsonSchema) {
  const { properties } = schema;
  expect(schema.additionalProperties).toBe(false);
  expect(Object.keys(signal).sort()).toEqual([...schema.required].sort());
  expect(properties.scenario_code!.enum).toContain(signal.scenario_code);
  expect(properties.trust_marking!.enum).toContain(signal.trust_marking);
  for (const key of ["signal_id", "snapshot_id", "tenant_id", "created_at"] as const) {
    expect(signal[key].length).toBeGreaterThan(0);
  }
  expect(signal.rub_assessment).not.toBeNull();
  const money = properties.rub_assessment!.anyOf![1]!;
  expect(signal.rub_assessment!.value_rub).toMatch(new RegExp(money.properties.value_rub!.pattern!));
  expect(money.properties.method!.enum).toContain(signal.rub_assessment!.method);
  expect(signal.source_refs.length).toBeGreaterThanOrEqual(properties.source_refs!.minItems!);
  for (const ref of signal.source_refs) {
    expect(ref.length).toBeGreaterThan(0);
  }
  const keyPattern = new RegExp(properties.detection_data!.propertyNames!.pattern);
  const entrySchema = properties.detection_data!.additionalProperties as JsonSchema;
  for (const [key, entry] of Object.entries(signal.detection_data)) {
    expect(key, key).toMatch(keyPattern);
    expect(Object.keys(entry).sort(), key).toEqual([...entrySchema.required].sort());
    expect(typeof entry.is_unknown, key).toBe("boolean");
    if (entry.is_unknown) {
      expect(entry.value, key).toBeNull();
    } else {
      expect(entry.value, key).not.toBeNull();
      if (Array.isArray(entry.value)) {
        expect(new Set(entry.value).size, key).toBe(entry.value.length);
        expect(entry.value.length, key).toBeGreaterThan(0);
        for (const item of entry.value) {
          expect(["orders", "revenue"], key).toContain(item);
        }
      } else {
        expect(["number", "string", "boolean"], key).toContain(typeof entry.value);
      }
    }
  }
}

describe("FIXTURE_BRIEF_SIGNALS — образец signals[] брифа в проводной форме (Story 4.3)", () => {
  const schema = loadSignalSchema();

  it("каждый сигнал обезличен (fixture-id) и держит контракт signal v1 по схеме", () => {
    expect(FIXTURE_BRIEF_SIGNALS.length).toBeGreaterThanOrEqual(3);
    for (const signal of FIXTURE_BRIEF_SIGNALS) {
      expect(signal.signal_id.startsWith("fixture-")).toBe(true);
      expect(signal.tenant_id.startsWith("fixture-")).toBe(true);
      expect(signal.snapshot_id.startsWith("fixture-")).toBe(true);
      expectSignalMatchesContract(signal, schema);
    }
  });

  it("порядок - по деньгам под риском по убыванию (Story 4.2), при равных - глубже падение раньше", () => {
    const money = FIXTURE_BRIEF_SIGNALS.map((signal) => Number(signal.rub_assessment!.value_rub));
    for (let index = 1; index < money.length; index += 1) {
      expect(money[index]!).toBeLessThanOrEqual(money[index - 1]!);
    }
    const deepest = (signal: SignalV1) =>
      Math.min(
        ...(["orders_deviation_pct", "revenue_deviation_pct"] as const)
          .map((key) => signal.detection_data[key]?.value)
          .filter((value): value is number => typeof value === "number"),
      );
    for (let index = 1; index < FIXTURE_BRIEF_SIGNALS.length; index += 1) {
      const previous = FIXTURE_BRIEF_SIGNALS[index - 1]!;
      const current = FIXTURE_BRIEF_SIGNALS[index]!;
      if (previous.rub_assessment!.value_rub === current.rub_assessment!.value_rub) {
        expect(deepest(previous)).toBeLessThanOrEqual(deepest(current));
      }
    }
  });

  it("оба уровня, ровно один SKU с категорией UNKNOWN, рост не сигнал (только падения в triggered_by)", () => {
    const levels = FIXTURE_BRIEF_SIGNALS.map((signal) => signal.detection_data.level?.value);
    expect(levels).toContain("sku");
    expect(levels).toContain("subject");
    const unknownSubjects = FIXTURE_BRIEF_SIGNALS.filter((signal) => signal.detection_data.subject_name?.is_unknown === true);
    expect(unknownSubjects).toHaveLength(1);
    expect(unknownSubjects[0]!.source_refs.some((ref) => ref.endsWith("/is_unknown"))).toBe(true);
    for (const signal of FIXTURE_BRIEF_SIGNALS) {
      const triggered = signal.detection_data.triggered_by?.value as string[];
      expect(triggered.length).toBeGreaterThan(0);
      for (const metricName of triggered) {
        const deviation = signal.detection_data[`${metricName}_deviation_pct`]?.value;
        expect(typeof deviation === "number" && deviation < 0, `${signal.signal_id}:${metricName}`).toBe(true);
      }
    }
  });
});

describe("getSummary — структурный образец сводки «вчера против нормы»", () => {
  it("форма совпадает с проводным payload: деньги строками AD-10, отклонение числом", () => {
    const summary = getSummary();
    expect(summary.status).toBe("ok");
    expect(summary.briefDay).toMatch(ISO_DATE);
    expect(summary.orders?.actual).toBe(27);
    expect(summary.orders?.norm).toMatch(MONEY_STRING);
    expect(summary.orders?.deviationPct).toBe(-21.7);
    expect(summary.revenue?.actual).toMatch(MONEY_STRING);
    expect(summary.revenue?.norm).toMatch(MONEY_STRING);
    expect(summary.revenue?.deviationPct).toBe(18.9);
    expect(summary.normProgress).toEqual({ sampleDays: 14, windowDays: 14 });
    expect(summary.dataStatus?.stale).toBe(false);
  });

  it("аномалии дня - из FIXTURE_BRIEF_SIGNALS в их порядке; quiet - без аномалий (Story 4.3)", () => {
    const daily = getSummary("daily");
    expect(daily.anomalies.map((anomaly) => anomaly.id)).toEqual(FIXTURE_BRIEF_SIGNALS.map((signal) => signal.signal_id));
    expect(daily.briefDay).toBe(FIXTURE_BRIEF_SIGNALS[0]!.detection_data.evaluation_day?.value);
    expect(getSummary("quiet").anomalies).toEqual([]);
  });
});
