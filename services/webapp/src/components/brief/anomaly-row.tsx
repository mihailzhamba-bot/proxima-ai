import { deviationLabel, deviationGyr, normLabel } from "@/components/brief/brief-summary";
import { MetaCell, Section } from "@/components/brief/signal-detail";
import { SignalRowShell } from "@/components/brief/signal-row";
import { Badge } from "@/components/ui/badge";
import { FxBadge } from "@/components/ui/fx-badge";
import type { AnomalyMetric, BriefAnomaly, SummaryMetric } from "@/lib/data/view-model";
import { formatRub } from "@/lib/format/rub";
import { gyrChipClass } from "@/lib/gyr";
import { cn } from "@/lib/utils";

/*
 * Строка аномалии детектора на /brief (Story 4.3). Свёрнутая строка отвечает на
 * «куда смотреть первым»: nmId/артикул (или предмет), категория, отклонение в %,
 * `scenario_code` и `rub_assessment` mono справа. Раскрытие - цифры ряда и
 * `source_refs` (AD-1). Компонент только показывает: отклонения, деньги и порядок
 * посчитал control-plane (Story 4.1/4.2), здесь нет арифметики.
 */

/** Подпись предмета, когда у SKU нет строки словаря (D32): показывается явно, а не пустотой. */
export const UNKNOWN_SUBJECT_LABEL = "UNKNOWN";

const METRIC_LABELS: Record<AnomalyMetric, string> = {
  orders: "заказы",
  revenue: "выручка",
};

const LEVEL_LABELS: Record<BriefAnomaly["level"], string> = {
  sku: "SKU",
  subject: "категория",
};

const METHOD_LABELS: Record<NonNullable<BriefAnomaly["moneyMethod"]>, string> = {
  revenue: "по выручке",
  profit: "по прибыли",
};

/**
 * Отклонение свёрнутой строки: самое глубокое из падений, по которым ряд стал
 * кандидатом (`triggered_by`, D32); без них - самое глубокое из известных.
 * Выбор, не расчёт: числа приходят готовыми.
 */
export function headlineDeviation(anomaly: BriefAnomaly): { metric: AnomalyMetric; pct: number } | null {
  const known = (["orders", "revenue"] as const)
    .map((metric) => ({ metric, pct: anomaly[metric]?.deviationPct ?? null }))
    .filter((entry): entry is { metric: AnomalyMetric; pct: number } => entry.pct !== null);
  const triggered = known.filter((entry) => anomaly.triggeredBy.includes(entry.metric));
  const pool = triggered.length > 0 ? triggered : known;
  if (pool.length === 0) {
    return null;
  }
  return pool.reduce((deepest, entry) => (entry.pct < deepest.pct ? entry : deepest));
}

/** Заголовок строки текстом - для title-подсказки и тестов. */
export function anomalyTitle(anomaly: BriefAnomaly): string {
  const subject = anomaly.subjectName ?? UNKNOWN_SUBJECT_LABEL;
  if (anomaly.level === "sku") {
    const article = anomaly.supplierArticle === null ? "" : ` · ${anomaly.supplierArticle}`;
    return `${anomaly.nmId ?? "—"}${article} · ${subject}`;
  }
  const count = anomaly.skuCount === null ? "" : ` · ${anomaly.skuCount} SKU`;
  return `${subject}${count}`;
}

function moneyLabel(moneyAtRisk: string | null): string {
  return moneyAtRisk === null ? "—" : formatRub(Number(moneyAtRisk));
}

function SubjectLabel({ subjectName }: { subjectName: string | null }) {
  if (subjectName === null) {
    return <span className="font-mono text-muted-foreground">{UNKNOWN_SUBJECT_LABEL}</span>;
  }
  return <span>{subjectName}</span>;
}

function RowTitle({ anomaly }: { anomaly: BriefAnomaly }) {
  if (anomaly.level === "sku") {
    return (
      <>
        <span className="font-mono font-medium tabular-nums">{anomaly.nmId ?? "—"}</span>
        {anomaly.supplierArticle !== null ? (
          <span className="font-mono text-muted-foreground"> · {anomaly.supplierArticle}</span>
        ) : null}
        <span className="text-muted-foreground"> · </span>
        <SubjectLabel subjectName={anomaly.subjectName} />
      </>
    );
  }
  return (
    <>
      <span className="font-medium">
        <SubjectLabel subjectName={anomaly.subjectName} />
      </span>
      {anomaly.skuCount !== null ? (
        <span className="font-mono text-muted-foreground tabular-nums"> · {anomaly.skuCount} SKU</span>
      ) : null}
    </>
  );
}

function DeviationChip({ anomaly }: { anomaly: BriefAnomaly }) {
  const headline = headlineDeviation(anomaly);
  if (headline === null) {
    return <span className="font-sans text-xs text-muted-foreground">отклонение не названо</span>;
  }
  return (
    <span
      className={cn("rounded-sm px-1.5 py-0.5 font-mono text-xs font-medium", gyrChipClass(deviationGyr(headline.pct)))}
    >
      <span className="font-sans font-normal">{METRIC_LABELS[headline.metric]} </span>
      {deviationLabel(headline.pct)}
    </span>
  );
}

function MetricCell({ label, metric, money }: { label: string; metric: SummaryMetric | null; money: boolean }) {
  if (metric === null) {
    return <MetaCell label={label}>—</MetaCell>;
  }
  const actual = money ? formatRub(Number(metric.actual)) : `${metric.actual}`;
  const norm = metric.norm === null ? "—" : money ? formatRub(Number(metric.norm)) : normLabel(metric.norm);
  return (
    <MetaCell label={label}>
      <span className="flex flex-wrap items-baseline gap-x-1.5 font-mono text-[13px] tabular-nums">
        <span className="font-semibold">{actual}</span>
        <span className="font-sans text-muted-foreground">против нормы {norm}</span>
        {metric.deviationPct !== null ? (
          <span className={cn("rounded-sm px-1 py-px text-xs font-medium", gyrChipClass(deviationGyr(metric.deviationPct)))}>
            {deviationLabel(metric.deviationPct)}
          </span>
        ) : null}
      </span>
    </MetaCell>
  );
}

/** Раскрытие строки: цифры ряда, уровень, порог и `source_refs` (AD-1) на каждый факт. */
export function AnomalyDetail({ anomaly, demo }: { anomaly: BriefAnomaly; demo: boolean }) {
  return (
    <div className="flex flex-col gap-5 border-b border-border bg-muted/40 px-4 py-4 text-sm">
      <dl className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <MetricCell label="Заказы" metric={anomaly.orders} money={false} />
        <MetricCell label="Выручка" metric={anomaly.revenue} money />
        <MetaCell label="Деньги под риском">
          <span className="flex flex-wrap items-center gap-1.5 font-mono text-[13px] tabular-nums">
            {moneyLabel(anomaly.moneyAtRisk)}
            {anomaly.moneyMethod !== null ? (
              <span className="font-sans text-muted-foreground">{METHOD_LABELS[anomaly.moneyMethod]}</span>
            ) : null}
            {demo ? <FxBadge /> : null}
          </span>
        </MetaCell>
        <MetaCell label="Уровень">
          {LEVEL_LABELS[anomaly.level]}
          {anomaly.skuCount !== null ? (
            <span className="font-mono text-muted-foreground tabular-nums"> · {anomaly.skuCount} SKU</span>
          ) : null}
        </MetaCell>
        <MetaCell label="Порог тревоги">
          {anomaly.thresholdPct === null ? (
            <span className="text-muted-foreground">не применяется</span>
          ) : (
            <span className="font-mono text-[13px] tabular-nums">{deviationLabel(anomaly.thresholdPct)}</span>
          )}
        </MetaCell>
        <MetaCell label="Сценарий">
          <span className="flex flex-wrap items-center gap-1.5">
            <Badge variant="outline" className="font-mono">
              {anomaly.scenarioCode}
            </Badge>
            <span className="font-mono text-xs text-muted-foreground">{anomaly.trust}</span>
          </span>
        </MetaCell>
      </dl>

      <Section title="Источники">
        <ul className="flex flex-col border-t border-border">
          {anomaly.sourceRefs.map((ref) => (
            <li key={ref} className="border-b border-border py-1.5 font-mono text-xs break-all text-muted-foreground">
              {ref}
            </li>
          ))}
        </ul>
      </Section>
    </div>
  );
}

type AnomalyRowProps = {
  anomaly: BriefAnomaly;
  /** Цифры из fixtures несут FX-бейдж (ADR-0004); у живых цифр его нет. */
  demo?: boolean;
};

/** Строка аномалии: nmId/артикул · категория слева; отклонение %, scenario_code, ₽ mono справа. */
export function AnomalyRow({ anomaly, demo = false }: AnomalyRowProps) {
  return (
    <SignalRowShell
      id={anomaly.id}
      status="red"
      titleHint={anomalyTitle(anomaly)}
      title={<RowTitle anomaly={anomaly} />}
      trailing={
        <>
          <DeviationChip anomaly={anomaly} />
          <Badge variant="outline" className="font-mono text-[11px]">
            {anomaly.scenarioCode}
          </Badge>
          {moneyLabel(anomaly.moneyAtRisk)}
          {demo ? <FxBadge /> : null}
        </>
      }
    >
      <AnomalyDetail anomaly={anomaly} demo={demo} />
    </SignalRowShell>
  );
}
