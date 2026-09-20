import type { Metadata } from "next";
import { AnomaliesBlock } from "@/components/brief/anomalies";
import { BriefSummaryBlock } from "@/components/brief/brief-summary";
import { BriefVerdict } from "@/components/brief/brief-verdict";
import { Digest } from "@/components/brief/digest";
import { SignalRow } from "@/components/brief/signal-row";
import { SectionErrorBoundary } from "@/components/ui/section-error";
import { getDataProvider, type BriefVariant } from "@/lib/data";

export const metadata: Metadata = {
  title: "Бриф",
};

type BriefPageProps = {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
};

export default async function BriefPage({ searchParams }: BriefPageProps) {
  const params = await searchParams;
  const variant: BriefVariant = params.view === "quiet" ? "quiet" : "daily";
  const provider = getDataProvider();
  const [baseBrief, summary] = await Promise.all([provider.getBrief(variant), provider.getSummary(variant)]);
  // До первого успешного прогона сводки экран не пустой, а с пометкой. Признак
  // берётся из статуса сводки, чтобы brief_current не читался второй раз (AD-9).
  const brief =
    summary.status === "no-brief"
      ? {
          ...baseBrief,
          digest: [
            ...baseBrief.digest,
            {
              id: "postgres-brief-pending",
              tone: "neutral" as const,
              text: "Сводка ещё не считается: ждём первый утренний прогон",
            },
          ],
        }
      : baseBrief;
  const firstCritical = brief.signals[0];

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6">
      <SectionErrorBoundary title="Итог дня">
        <BriefVerdict
          dateIso={brief.dateIso}
          criticalCount={brief.signals.length}
          attentionCount={brief.attentionCount}
          firstCriticalId={firstCritical?.id}
        />
      </SectionErrorBoundary>
      <SectionErrorBoundary title="Вчера против нормы">
        <BriefSummaryBlock summary={summary} />
      </SectionErrorBoundary>
      <SectionErrorBoundary title="Аномалии">
        {/* Story 4.3: signals[] брифа по SKU и категории; статус и цифры - те же, что у сводки (AD-9). */}
        <AnomaliesBlock summary={summary} demo={provider.mode === "fixtures"} />
      </SectionErrorBoundary>
      {brief.signals.length > 0 && (
        <SectionErrorBoundary title="Критичные сигналы">
          <section aria-label="Критичные сигналы" className="border-t border-border">
            {brief.signals.map((signal, index) => (
              <SignalRow key={signal.id} signal={signal} anchorId={index === 0} />
            ))}
          </section>
        </SectionErrorBoundary>
      )}
      <SectionErrorBoundary title="Дайджест">
        <Digest items={brief.digest} />
      </SectionErrorBoundary>
    </div>
  );
}
