import { Badge } from "@/components/ui/badge";
import { FxBadge } from "@/components/ui/fx-badge";
import type { BriefSignal, SignalHypothesis } from "@/lib/data/view-model";
import { formatRub } from "@/lib/format/rub";

const RISK_HINTS: Record<BriefSignal["riskLevel"], string> = {
  R0: "обратимо, решение не требует согласования",
  R1: "обратимо, влияет на один товар или кампанию",
  R2: "влияет на юнит-экономику позиции",
  R3: "необратимо или затрагивает весь кабинет",
};

function MetaCell({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-1">
      <dt className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">{label}</dt>
      <dd className="text-sm">{children}</dd>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="flex flex-col gap-1.5">
      <h3 className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">{title}</h3>
      {children}
    </section>
  );
}

function refLabels(signal: BriefSignal, hypothesis: SignalHypothesis): string {
  const labels = hypothesis.sourceRefIds
    .map((id) => signal.sourceRefs.find((ref) => ref.id === id)?.label)
    .filter((label): label is string => Boolean(label));
  return labels.join(" · ");
}

/**
 * Развёрнутая карточка сигнала (PA-38): период, причина + альтернативы, рекомендация,
 * R-уровень, «что неизвестно» и SourceRef на каждый факт. Решение принимает AM — кнопок здесь нет,
 * они приходят с Decision Inbox (PA-51).
 */
export function SignalDetail({ signal }: { signal: BriefSignal }) {
  return (
    <div className="flex flex-col gap-5 border-b border-border bg-muted/40 px-4 py-4 text-sm">
      <dl className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <MetaCell label="С чем сравнили">
          <span className="flex items-center gap-1.5 font-mono text-[13px] tabular-nums">
            {signal.period}
            <FxBadge />
          </span>
        </MetaCell>
        <MetaCell label="Стоимость молчания">
          <span className="flex items-center gap-1.5 font-mono text-[13px] tabular-nums">
            {formatRub(signal.costEstimate)}
            <span className="font-sans text-muted-foreground">/ день</span>
            <FxBadge />
          </span>
        </MetaCell>
        <MetaCell label="Уровень риска">
          <span className="flex flex-wrap items-center gap-1.5">
            <Badge variant="outline" className="font-mono">
              {signal.riskLevel}
            </Badge>
            <span className="text-muted-foreground">{RISK_HINTS[signal.riskLevel]}</span>
          </span>
        </MetaCell>
      </dl>

      <Section title="Предполагаемая причина">
        <p>{signal.primaryCause.text}</p>
        <p className="font-mono text-xs text-muted-foreground">{refLabels(signal, signal.primaryCause)}</p>
      </Section>

      <Section title="Альтернативы">
        <ul className="flex flex-col gap-2">
          {signal.alternatives.map((alternative) => (
            <li key={alternative.id} className="flex flex-col gap-0.5">
              <span className="text-muted-foreground">{alternative.text}</span>
              <span className="font-mono text-xs text-muted-foreground">
                {refLabels(signal, alternative)}
              </span>
            </li>
          ))}
        </ul>
      </Section>

      <Section title="Рекомендация">
        <p>{signal.recommendation}</p>
      </Section>

      <Section title="Что неизвестно">
        <ul className="flex flex-col gap-2">
          {signal.unknowns.map((unknown) => (
            <li key={unknown.id} className="flex flex-col gap-0.5">
              <span>{unknown.question}</span>
              <span className="text-xs text-muted-foreground">{unknown.whyItMatters}</span>
            </li>
          ))}
        </ul>
      </Section>

      <Section title="Источники">
        <ul className="flex flex-col border-t border-border">
          {signal.sourceRefs.map((ref) => (
            <li
              key={ref.id}
              className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5 border-b border-border py-1.5"
            >
              <span className="font-medium">{ref.label}</span>
              <span className="font-mono text-xs tabular-nums text-muted-foreground">{ref.period}</span>
              <span className="text-xs text-muted-foreground">{ref.source}</span>
            </li>
          ))}
        </ul>
      </Section>
    </div>
  );
}
