import { readFileSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

import type { BriefV1 } from "@/lib/contracts/brief";
import type { CabinetDailyV1 } from "@/lib/contracts/cabinet-daily";
import type { NormV1 } from "@/lib/contracts/norm";
import type { BriefWirePayload } from "@/lib/data/postgres-provider";

/*
 * Story 2.2: webapp читает те же контракты, что и control-plane (AD-9/AD-10).
 * Типы в @/lib/contracts сгенерированы `make codegen` из contracts/*.schema.json;
 * этот тест прибивает их к синтетическим примерам из contracts/examples/, чтобы
 * дрейф «схема -> сгенерированный тип -> потребитель» ловился typecheck'ом webapp.
 * Сами схемы дополнительно валидируются гейтом `make contracts` (Python).
 */

// src/tests -> src -> webapp -> services -> repo root
const REPO_ROOT = fileURLToPath(new URL("../../../..", import.meta.url));

function readExample(name: string): unknown {
  return JSON.parse(readFileSync(join(REPO_ROOT, "contracts", "examples", name), "utf8"));
}

const MONEY_STRING = /^-?[0-9]+\.[0-9]{2}$/;

describe("contract: cabinet-daily", () => {
  it("synthetic example satisfies the generated type", () => {
    const fact = readExample("cabinet-daily.synthetic.json") as CabinetDailyV1;
    expect(fact.schema_version).toBe(1);
    expect(fact.calendar_day).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    expect(fact.revenue_rub).toMatch(MONEY_STRING);
    expect(fact.forpay_rub).toMatch(MONEY_STRING);
    expect(fact.source_refs.length).toBeGreaterThanOrEqual(1);
  });
});

describe("contract: norm", () => {
  it("synthetic example satisfies the generated type", () => {
    const norm = readExample("norm.synthetic.json") as NormV1;
    expect(norm.window_days).toBe(14);
    expect(norm.sample_days).toBe(14);
    expect(norm.status).toBe("ok");
    expect(norm.value).toMatch(MONEY_STRING);
    expect(norm.source_refs.length).toBeGreaterThanOrEqual(1);
  });
});

describe("contract: brief", () => {
  it("synthetic example satisfies the generated type", () => {
    const brief = readExample("brief.synthetic.json") as BriefV1;
    expect(brief.evaluation_day).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    // norm and actual are nullable in the contract because a blocked or
    // insufficient day genuinely has none; the ok example must have both.
    expect(brief.actual).not.toBeNull();
    expect(brief.norm).not.toBeNull();
    expect(brief.actual!.revenue).toMatch(MONEY_STRING);
    expect(brief.norm!.revenue).toMatch(MONEY_STRING);
    expect(brief.norm!.window_days).toBe(14);
    expect(brief.signals.length).toBe(1);
    expect(brief.signals[0]?.rub_assessment?.value_rub).toMatch(MONEY_STRING);
    expect(brief.source_refs.length).toBeGreaterThanOrEqual(1);
  });

  it("money travels as strings with two decimals everywhere (AD-10)", () => {
    const brief = readExample("brief.synthetic.json") as BriefV1;
    expect(typeof brief.actual!.revenue).toBe("string");
    expect(typeof brief.norm!.revenue).toBe("string");
    expect(typeof brief.norm!.orders).toBe("string");
  });

  it("is the wire shape the postgres provider will decode (Story 2.4)", () => {
    const payload = readExample("brief.synthetic.json") as BriefWirePayload;
    expect(payload.schema_version).toBe(1);
  });
});
