import { describe, expect, it } from "vitest";
import { formatRub, formatRubCompact, formatRubPrecise } from "@/lib/format/rub";

describe("formatRub", () => {
  it("форматирует целые суммы с ₽ и разделителями ru-RU", () => {
    expect(formatRub(1234567)).toMatch(/1\s234\s567/);
    expect(formatRub(1234567)).toContain("₽");
    expect(formatRub(0)).toContain("0");
  });

  it("отрицательные суммы сохраняют знак", () => {
    expect(formatRub(-4200)).toContain("-");
  });

  it("бросает на нечисловых значениях вместо тихой лжи", () => {
    expect(() => formatRub(Number.NaN)).toThrow(TypeError);
    expect(() => formatRub(Number.POSITIVE_INFINITY)).toThrow(TypeError);
  });
});

describe("formatRubPrecise", () => {
  it("показывает копейки", () => {
    expect(formatRubPrecise(1234.5)).toMatch(/1\s234,50/);
  });
});

describe("formatRubCompact", () => {
  it("миллионы компактно", () => {
    expect(formatRubCompact(1_250_000)).toContain("млн");
  });

  it("десятки тысяч - в тысячи", () => {
    expect(formatRubCompact(145_000)).toContain("тыс.");
  });

  it("малые суммы - как есть", () => {
    expect(formatRubCompact(9500)).not.toContain("тыс.");
  });
});
