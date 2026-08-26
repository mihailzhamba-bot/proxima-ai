import { CountUp } from "@/components/brief/count-up";
import { FxBadge } from "@/components/ui/fx-badge";

type BriefVerdictProps = {
  dateIso: string;
  criticalCount: number;
  attentionCount: number;
  firstCriticalId?: string;
};

function briefDateLabel(iso: string): string {
  return new Intl.DateTimeFormat("ru-RU", {
    weekday: "long",
    day: "numeric",
    month: "long",
    year: "numeric",
    timeZone: "UTC",
  }).format(new Date(`${iso}T12:00:00Z`));
}

function plural(n: number, one: string, few: string, many: string): string {
  const mod10 = n % 10;
  const mod100 = n % 100;
  if (mod10 === 1 && mod100 !== 11) return one;
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return few;
  return many;
}

/** Шапка брифа: дата mono + вердикт-строка; якорь на «критичных» прыгает к первой critical-строке (A01). */
export function BriefVerdict({ dateIso, criticalCount, attentionCount, firstCriticalId }: BriefVerdictProps) {
  return (
    <header className="flex flex-col gap-1.5">
      <time dateTime={dateIso} className="font-mono text-xs uppercase tracking-wide text-muted-foreground">
        {briefDateLabel(dateIso)}
      </time>
      <p className="flex flex-wrap items-center gap-x-2 text-lg font-semibold tracking-tight">
        {criticalCount > 0 && firstCriticalId ? (
          <>
            <a
              href={`#${firstCriticalId}`}
              className="rounded-sm text-primary underline-offset-4 hover:underline focus-visible:outline-2 focus-visible:outline-primary"
            >
              <CountUp value={criticalCount} aria-label={`Критичных сигналов: ${criticalCount}`} />{" "}
              {plural(criticalCount, "критичный", "критичных", "критичных")}
            </a>
            <span aria-hidden="true" className="text-muted-foreground">
              /
            </span>
            <span className="font-normal text-muted-foreground">
              <CountUp value={attentionCount} /> внимания
            </span>
          </>
        ) : (
          <span>Критичных нет</span>
        )}
        <FxBadge className="ml-1" />
      </p>
    </header>
  );
}
