import type { DataProvider } from "@/lib/data/provider";
import type { BriefData, BriefSummary, BriefVariant, Metric } from "@/lib/data/view-model";
import { getBrief, getSummary } from "@/lib/fixtures/brief";
import { getMetrics } from "@/lib/fixtures/metrics";

/** Демо-источник: структурные обезличенные fixtures (DEC-006, экран под плашкой unreleased). */
export function createFixturesProvider(): DataProvider {
  return {
    mode: "fixtures",
    supportsMetrics: true,
    getBrief(variant: BriefVariant): Promise<BriefData> {
      return Promise.resolve(getBrief(variant));
    },
    getSummary(variant: BriefVariant = "daily"): Promise<BriefSummary> {
      return Promise.resolve(getSummary(variant));
    },
    getMetrics(): Promise<readonly Metric[]> {
      return Promise.resolve(getMetrics());
    },
  };
}
