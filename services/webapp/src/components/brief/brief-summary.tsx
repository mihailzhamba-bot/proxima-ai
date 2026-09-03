import type { BriefSummary, SummaryStatus } from "@/lib/data/view-model";
import { type GyrStatus, gyrChipClass } from "@/lib/gyr";
import { formatRub } from "@/lib/format/rub";

/*
 * Блок «вчера против нормы» (AD-9, Story 2.5). Компонент только показывает:
 * значения/норму/отклонение уже посчитал control-plane, здесь нет бизнес-логики.
 * Цвет отклонения - по знаку через lib/gyr: упавшие продажи - красное,
 * выросшие - зелёное (для обеих метрик «больше» = лучше).
 */

function dayLabel(iso: string): string {
  const [, month, day] = iso.split("-");
  return `${day}.${month}`;
}

function timeLabel(isoMoment: string): string {
  return new Intl.DateTimeFormat("ru-RU", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "Europe/Moscow",
  }).format(new Date(isoMoment));
}

/** Норма приходит строкой AD-10: «34.50» -> «34,5», без лишних нулей. */
function normLabel(value: string): string {
  const parsed = Number(value);
  return parsed.toLocaleString("ru-RU", { maximumFractionDigits: 2 });
}

function deviationLabel(deviationPct: number): string {
  const sign = deviationPct > 0 ? "+" : deviationPct < 0 ? "−" : "";
  return `${sign}${Math.abs(deviationPct).toLocaleString("ru-RU", { minimumFractionDigits: 1, maximumFractionDigits: 1 })} %`;
}

/** Цвет по знаку отклонения (AC Story 2.5): минус - падение, плюс - рост, ноль - нейтрально. */
export function deviationGyr(deviationPct: number | null): GyrStatus {
  if (deviationPct === null || deviationPct === 0) {
    return "neutral";
  }
  return deviationPct > 0 ? "green" : "red";
}

function MetricLine({
  label,
  actual,
  norm,
  deviationPct,
}: {
  label: string;
  actual: string;
  norm: string;
  deviationPct: number;
}) {
  const gyr = deviationGyr(deviationPct);
  return (
    <p className="flex flex-wrap items-baseline gap-x-2 text-lg tracking-tight">
      <span className="font-medium">{label}</span>
      <span className="font-semibold">{actual}</span>
      <span className="text-muted-foreground">против нормы {norm}</span>
      <span className={`rounded-sm px-1.5 py-0.5 font-mono text-sm font-medium ${gyrChipClass(gyr)}`}>
        {deviationLabel(deviationPct)}
      </span>
    </p>
  );
}

function WarningLine({ children }: { children: React.ReactNode }) {
  return (
    <p role="note" className="rounded-sm bg-muted/60 px-2 py-1 text-sm text-muted-foreground">
      {children}
    </p>
  );
}

/** Текст-предупреждение вместо цифр; по AC 1.11 stale и пустой view звучат одинаково. */
function numbersWarning(status: SummaryStatus, normProgress: BriefSummary["normProgress"]): string {
  if (status === "insufficient") {
    return normProgress
      ? `Норма копится: ${normProgress.sampleDays}/${normProgress.windowDays} дней`
      : "Норма копится: окно неполное";
  }
  return "Сбор не проходил больше суток";
}

type BriefSummaryBlockProps = {
  summary: BriefSummary;
};

/** Сводка + строка статуса «Данные до <дата>, обновлено <время>». */
export function BriefSummaryBlock({ summary }: BriefSummaryBlockProps) {
  const { dataStatus } = summary;
  const noFreshData = dataStatus === null || dataStatus.stale;
  const showNumbers = summary.status === "ok" && !noFreshData;

  return (
    <section aria-label="Вчера против нормы" className="flex flex-col gap-2 border-t border-border pt-4">
      {showNumbers && summary.briefDay !== null ? (
        <h2 className="font-mono text-xs uppercase tracking-wide text-muted-foreground">
          {dayLabel(summary.briefDay)}: вчера против нормы
        </h2>
      ) : (
        <h2 className="font-mono text-xs uppercase tracking-wide text-muted-foreground">Вчера против нормы</h2>
      )}
      {showNumbers && summary.orders !== null && summary.revenue !== null ? (
        <>
          <MetricLine
            label="Заказы"
            actual={`${summary.orders.actual}`}
            norm={normLabel(summary.orders.norm ?? "")}
            deviationPct={summary.orders.deviationPct ?? 0}
          />
          <MetricLine
            label="Выручка"
            actual={formatRub(Number(summary.revenue.actual))}
            norm={`${formatRub(Number(summary.revenue.norm ?? "0"))}`}
            deviationPct={summary.revenue.deviationPct ?? 0}
          />
        </>
      ) : (
        <WarningLine>{numbersWarning(summary.status, summary.normProgress)}</WarningLine>
      )}
      {dataStatus !== null && !dataStatus.stale ? (
        <p className="text-xs text-muted-foreground">
          Данные до {dayLabel(dataStatus.lastFullDay)}, обновлено {timeLabel(dataStatus.collectedAt)}
        </p>
      ) : null}
    </section>
  );
}
