import type { Metadata } from "next";
import { BriefVerdict } from "@/components/brief/brief-verdict";
import { Digest } from "@/components/brief/digest";
import { SignalRow } from "@/components/brief/signal-row";
import { SectionErrorBoundary } from "@/components/ui/section-error";
import { getBrief, type BriefVariant } from "@/lib/fixtures/brief";

export const metadata: Metadata = {
  title: "Бриф",
};

type BriefPageProps = {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
};

export default async function BriefPage({ searchParams }: BriefPageProps) {
  const params = await searchParams;
  const variant: BriefVariant = params.view === "quiet" ? "quiet" : "daily";
  const brief = getBrief(variant);
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
