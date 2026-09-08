import { AnomalyRow } from "@/components/brief/anomaly-row";
import { WarningLine, numbersWarning } from "@/components/brief/brief-summary";
import type { BriefAnomaly, BriefSummary } from "@/lib/data/view-model";

/*
 * Блок «Аномалии» на /brief (Story 4.3): `signals[]` брифа в разрезе SKU и
 * категории. Компонент только показывает; состояние берётся из статуса сводки
 * (AD-9, правило показа цифр уже применил провайдер):
 *  - ok с аномалиями - два раздела, порядок строк = порядок `signals[]`;
 *  - ok без аномалий - «критичных нет»;
 *  - insufficient - «норма копится: N/14 дней»;
 *  - blocked - блок скрыт, показана причина «данных за день нет»
 *    (нет версии за evaluation_day, определение Story 2.4);
 *  - stale - предупреждение сводки (AC 1.11);
 *  - no-brief - блока нет: пометку «сводка ещё не считается» несёт дайджест.
 */

export const NO_ANOMALIES_TEXT = "Критичных нет";
export const BLOCKED_TEXT = "Аномалии: данных за день нет";

function Heading() {
  return <h2 className="font-mono text-xs uppercase tracking-wide text-muted-foreground">Аномалии</h2>;
}

function Block({ children }: { children: React.ReactNode }) {
  return (
    <section aria-label="Аномалии" className="flex flex-col gap-2 border-t border-border pt-4">
      <Heading />
      {children}
    </section>
  );
}

function AnomalySection({
  title,
  label,
  rows,
  emptyText,
  demo,
}: {
  title: string;
  label: string;
  rows: readonly BriefAnomaly[];
  emptyText: string;
  demo: boolean;
}) {
  return (
    <section aria-label={label} className="flex flex-col gap-1">
      <h3 className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{title}</h3>
      {rows.length === 0 ? (
        <p className="text-sm text-muted-foreground">{emptyText}</p>
      ) : (
        <div className="border-t border-border">
          {rows.map((anomaly) => (
            <AnomalyRow key={anomaly.id} anomaly={anomaly} demo={demo} />
          ))}
        </div>
      )}
    </section>
  );
}

type AnomaliesBlockProps = {
  summary: BriefSummary;
  /** Цифры из fixtures несут FX-бейдж (ADR-0004); у живых цифр его нет. */
  demo?: boolean;
};

export function AnomaliesBlock({ summary, demo = false }: AnomaliesBlockProps) {
  if (summary.status === "no-brief") {
    return null;
  }
  if (summary.status === "blocked") {
    // Блок скрыт, причина показана (AC Story 4.3).
    return <WarningLine>{BLOCKED_TEXT}</WarningLine>;
  }
  if (summary.status !== "ok") {
    return (
      <Block>
        <WarningLine>{numbersWarning(summary.status, summary.normProgress, summary.dataStatus)}</WarningLine>
      </Block>
    );
  }
  if (summary.anomalies.length === 0) {
    return (
      <Block>
        <p className="text-sm">{NO_ANOMALIES_TEXT}</p>
      </Block>
    );
  }
  // Разрезы - фильтр без пересортировки: внутри каждого порядок payload (деньги по убыванию).
  const skuRows = summary.anomalies.filter((anomaly) => anomaly.level === "sku");
  const subjectRows = summary.anomalies.filter((anomaly) => anomaly.level === "subject");
  return (
    <Block>
      <AnomalySection
        title="По SKU"
        label="Аномалии по SKU"
        rows={skuRows}
        emptyText="по SKU аномалий нет"
        demo={demo}
      />
      <AnomalySection
        title="По категориям"
        label="Аномалии по категориям"
        rows={subjectRows}
        emptyText="по категориям аномалий нет"
        demo={demo}
      />
    </Block>
  );
}
