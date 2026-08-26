import { CircleDashed } from "lucide-react";
import { FxBadge } from "@/components/ui/fx-badge";
import { formatRubCompact } from "@/lib/format/rub";
import { gyrDotClass } from "@/lib/gyr";
import type { FixtureMetric } from "@/lib/fixtures/metrics";
import { Sparkline } from "@/components/metrics/sparkline";

function formatClock(totalMinutes: number): string {
  const hours = Math.floor(totalMinutes / 60) % 24;
  const minutes = totalMinutes % 60;
  return `${String(hours).padStart(2, "0")}:${String(minutes).padStart(2, "0")}`;
}

function formatValue(metric: FixtureMetric): string {
  switch (metric.format) {
    case "rub-compact":
      return formatRubCompact(metric.value ?? 0);
    case "clock":
      return formatClock(metric.value ?? 0);
    default:
      return (metric.value ?? 0).toLocaleString("ru-RU");
  }
}

function formatDelta(percent: number): string {
  const sign = percent > 0 ? "+" : percent < 0 ? "\u2212" : "";
  const arrow = percent > 0 ? "\u2191" : percent < 0 ? "\u2193" : "";
  const magnitude = Math.abs(percent).toLocaleString("ru-RU", {
    maximumFractionDigits: 1,
  });
  return `${arrow} ${sign}${magnitude}%`;
}

function deltaTone(metric: FixtureMetric): string {
  if (metric.deltaPercent === null || metric.deltaGoodWhen === null || metric.deltaPercent === 0) {
    return "text-muted-foreground";
  }
  const direction = metric.deltaPercent > 0 ? "up" : "down";
  return direction === metric.deltaGoodWhen ? "text-status-green" : "text-status-red";
}

/** Карточка метрики: число mono + FX-бейдж + дельта к 7 дням + статичный спарклайн (R05). */
export function MetricCard({ metric }: { metric: FixtureMetric }) {
  const hasData = metric.value !== null;

  return (
    <div
      className="flex items-start justify-between gap-3 rounded-lg border border-border bg-card p-4"
      data-testid={`metric-${metric.id}`}
    >
      <div className="flex min-w-0 flex-col">
        <span className="truncate text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
          {metric.label}
        </span>
        {hasData ? (
          <>
            <span className="mt-2 flex items-baseline gap-1.5">
              {metric.status !== null && (
                <span
                  aria-hidden="true"
                  className={`mb-1 size-1.5 shrink-0 rounded-full ${gyrDotClass(metric.status)}`}
                />
              )}
              <span className="font-mono text-[30px] leading-none font-medium tabular-nums text-foreground">
                {formatValue(metric)}
              </span>
              <FxBadge />
            </span>
            <span
              className={`mt-2 font-mono text-xs tabular-nums ${deltaTone(metric)}`}
              title="Сравнение с тем же днём прошлой недели"
            >
              {metric.deltaPercent === null ? "—" : formatDelta(metric.deltaPercent)}
              <span className="ml-1 font-sans text-muted-foreground">vs 7 дн</span>
            </span>
          </>
        ) : (
          <span className="mt-2 flex items-center gap-1.5 text-sm text-muted-foreground">
            <CircleDashed className="size-4 shrink-0" aria-hidden="true" />
            нет данных
          </span>
        )}
      </div>
      {hasData && metric.points.length > 0 && (
        <Sparkline points={metric.points} className="mt-1 max-[379px]:hidden" />
      )}
    </div>
  );
}
