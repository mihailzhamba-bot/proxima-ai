/* UI-only fixture presentation types; boundary types are generated in contracts/. */
import type { GyrStatus } from "@/lib/gyr";
export type DataMode = "fixtures" | "postgres";
export type TrustMarker = "unreleased";
export type RiskLevel = "R0" | "R1" | "R2" | "R3";
export const RISK_LEVELS: readonly RiskLevel[] = ["R0", "R1", "R2", "R3"];
export type SourceRef = { id: string; label: string; period: string; source: string };
export type SignalHypothesis = { id: string; text: string; sourceRefIds: readonly string[] };
export type SignalUnknown = { id: string; question: string; whyItMatters: string };
export type BriefSignal = { id: string; status: GyrStatus; title: string; cause: string; period: string; costEstimate: number; riskLevel: RiskLevel; trust: TrustMarker; primaryCause: SignalHypothesis; alternatives: readonly SignalHypothesis[]; unknowns: readonly SignalUnknown[]; recommendation: string; sourceRefs: readonly SourceRef[] };
export type BriefVariant = "daily" | "quiet";
export type BriefDigestItem = { id: string; tone: GyrStatus; text: string };
export type BriefData = { variant: BriefVariant; dateIso: string; signals: readonly BriefSignal[]; attentionCount: number; digest: readonly BriefDigestItem[]; dataMode: DataMode };
export type MetricId = "signals" | "revenue-day" | "orders-day" | "oos-risks" | "freshness";
export type MetricFormat = "count" | "rub-compact" | "clock";
export type Metric = { id: MetricId; label: string; value: number | null; format: MetricFormat; status: GyrStatus | null; deltaPercent: number | null; deltaGoodWhen: "up" | "down" | null; points: readonly number[] };
