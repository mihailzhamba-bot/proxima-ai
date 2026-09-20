import { describe, expect, it } from "vitest";
import { FX_BADGE_LABEL, fxBadgeClass } from "@/lib/fx";
import { GYR_STATUSES, gyrChipClass } from "@/lib/gyr";

describe("fx badge token", () => {
  it("маркирует демо-цифры литерой FX из спецификации", () => {
    expect(FX_BADGE_LABEL).toBe("FX");
  });

  it("класс бейджа: muted-фон, mono, uppercase, 10px", () => {
    const cls = fxBadgeClass();
    expect(cls).toContain("bg-muted");
    expect(cls).toContain("text-muted-foreground");
    expect(cls).toContain("font-mono");
    expect(cls).toContain("uppercase");
    expect(cls).toContain("text-[10px]");
  });
});

describe("gyr chip class mapping", () => {
  it("каждый статус даёт и фон, и контрастный текст чипа", () => {
    for (const status of GYR_STATUSES) {
      const cls = gyrChipClass(status);
      expect(cls).toContain(`bg-status-${status}`);
      expect(cls).toContain(`text-status-${status}-foreground`);
    }
  });
});
