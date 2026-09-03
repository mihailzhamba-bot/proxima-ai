import { describe, expect, it } from "vitest";
import { GYR_STATUSES, isGyrStatus } from "@/lib/gyr";
import { RISK_LEVELS, type SignalHypothesis } from "@/lib/data/view-model";
import { getBrief, getSummary, type BriefSignal } from "@/lib/fixtures/brief";

const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/;
const MONEY_STRING = /^-?[0-9]+\.[0-9]{2}$/;

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
});
