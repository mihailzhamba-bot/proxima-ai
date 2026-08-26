import { describe, expect, it } from "vitest";
import { GYR_STATUSES, isGyrStatus } from "@/lib/gyr";
import { getBrief, type BriefSignal } from "@/lib/fixtures/brief";

const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/;

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
