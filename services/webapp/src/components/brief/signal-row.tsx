import { ChevronRight } from "lucide-react";
import { SignalDetail } from "@/components/brief/signal-detail";
import { FxBadge } from "@/components/ui/fx-badge";
import type { BriefSignal } from "@/lib/data/types";
import { formatRub } from "@/lib/format/rub";
import { gyrDotClass } from "@/lib/gyr";
import { cn } from "@/lib/utils";

type SignalRowProps = {
  signal: BriefSignal;
  anchorId?: boolean;
};

/**
 * Critical-строка брифа: свёрнутая — 36px, GYR-полоса 3px слева, ₽-оценка mono справа.
 * Раскрывается в полную карточку сигнала (PA-50) нативным details — без клиентского JS,
 * чтобы строка сканирования брифа осталась плотной, а детали были в одном клике.
 */
export function SignalRow({ signal, anchorId }: SignalRowProps) {
  return (
    <details id={anchorId ? signal.id : undefined} className="group scroll-mt-4">
      <summary
        className={cn(
          "relative flex h-9 cursor-pointer list-none items-center gap-3 border-b border-border pl-4 pr-2",
          "focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-primary",
          "[&::-webkit-details-marker]:hidden",
        )}
      >
        <span aria-hidden="true" className={cn("absolute inset-y-0 left-0 w-[3px]", gyrDotClass(signal.status))} />
        <ChevronRight
          aria-hidden="true"
          className="size-3.5 shrink-0 text-muted-foreground transition-transform group-open:rotate-90 motion-reduce:transition-none"
        />
        <span className="min-w-0 flex-1 truncate text-sm" title={`${signal.title} · ${signal.cause}`}>
          <span className="font-medium">{signal.title}</span>
          <span className="text-muted-foreground"> · {signal.cause}</span>
        </span>
        <span className="flex shrink-0 items-center gap-1.5 font-mono text-sm tabular-nums">
          {formatRub(signal.costEstimate)}
          <FxBadge />
        </span>
      </summary>
      <SignalDetail signal={signal} />
    </details>
  );
}
