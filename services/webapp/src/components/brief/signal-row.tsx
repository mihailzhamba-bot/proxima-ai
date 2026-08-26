import { FxBadge } from "@/components/ui/fx-badge";
import { formatRub } from "@/lib/format/rub";
import type { BriefSignal } from "@/lib/fixtures/brief";
import { gyrDotClass } from "@/lib/gyr";
import { cn } from "@/lib/utils";

type SignalRowProps = {
  signal: BriefSignal;
  anchorId?: boolean;
};

/** Полноширинная critical-строка брифа: 36px, GYR-полоса 3px слева, ₽-оценка mono справа; статична. */
export function SignalRow({ signal, anchorId }: SignalRowProps) {
  return (
    <div
      id={anchorId ? signal.id : undefined}
      className="group relative flex h-9 scroll-mt-4 items-center gap-3 border-b border-border pl-4 pr-2"
    >
      <span aria-hidden="true" className={cn("absolute inset-y-0 left-0 w-[3px]", gyrDotClass(signal.status))} />
      <span className="min-w-0 flex-1 truncate text-sm" title={`${signal.title} · ${signal.cause}`}>
        <span className="font-medium">{signal.title}</span>
        <span className="text-muted-foreground"> · {signal.cause}</span>
      </span>
      <span className="flex shrink-0 items-center gap-1.5 font-mono text-sm tabular-nums">
        {formatRub(signal.costEstimate)}
        <FxBadge />
      </span>
    </div>
  );
}
