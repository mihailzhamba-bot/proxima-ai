import { describe, expect, it } from "vitest";
import {
  gyrChipClass,
  gyrDotClass,
  isGyrStatus,
  totalSignals,
  type GyrCounters,
} from "@/lib/gyr";

describe("gyr", () => {
  it("распознаёт валидные статусы", () => {
    expect(isGyrStatus("green")).toBe(true);
    expect(isGyrStatus("yellow")).toBe(true);
    expect(isGyrStatus("red")).toBe(true);
    expect(isGyrStatus("neutral")).toBe(true);
  });

  it("отклоняет мусор", () => {
    expect(isGyrStatus("GREEN")).toBe(false);
    expect(isGyrStatus("")).toBe(false);
    expect(isGyrStatus(null)).toBe(false);
    expect(isGyrStatus(42)).toBe(false);
  });

  it("каждому статусу сопоставлены классы чипа и точки", () => {
    for (const status of ["green", "yellow", "red", "neutral"] as const) {
      expect(gyrChipClass(status)).toContain("bg-status-");
      expect(gyrDotClass(status)).toContain("bg-status-");
    }
  });

  it("totalSignals складывает счётчики", () => {
    const counters: GyrCounters = { red: 2, yellow: 5, green: 137 };
    expect(totalSignals(counters)).toBe(144);
  });
});
