import { ChevronRight } from "lucide-react";
import { SignalDetail } from "@/components/brief/signal-detail";
import { FxBadge } from "@/components/ui/fx-badge";
import type { BriefSignal } from "@/lib/data/view-model";
import { formatRub } from "@/lib/format/rub";
import { type GyrStatus, gyrDotClass } from "@/lib/gyr";
import { cn } from "@/lib/utils";

type SignalRowShellProps = {
  /** Ключ строки; становится DOM-id только у якорной строки (A01), чтобы id не дублировались. */
  id: string;
  status: GyrStatus;
  anchorId?: boolean;
  /** Свёрнутая строка слева: заголовок, усекается многоточием. */
  title: React.ReactNode;
  /** Полный текст заголовка для title-подсказки усечённой строки. */
  titleHint?: string;
  /** Свёрнутая строка справа: ₽-оценка mono и бейджи. */
  trailing: React.ReactNode;
  /** Раскрытие строки. */
  children: React.ReactNode;
};

/**
 * Каркас строки брифа (PA-49): свёрнутая — 36px, GYR-полоса 3px слева, mono справа.
 * Раскрывается нативным details — без клиентского JS, чтобы строка сканирования
 * брифа осталась плотной, а детали были в одном клике. Общий для critical-строк
 * редакционного брифа и строк аномалий детектора (Story 4.3).
 */
export function SignalRowShell({ id, status, anchorId, title, titleHint, trailing, children }: SignalRowShellProps) {
  return (
    <details id={anchorId ? id : undefined} data-signal-id={id} className="group scroll-mt-4">
      <summary
        className={cn(
          "relative flex h-9 cursor-pointer list-none items-center gap-3 border-b border-border pl-4 pr-2",
          "focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-primary",
          "[&::-webkit-details-marker]:hidden",
        )}
      >
        <span aria-hidden="true" className={cn("absolute inset-y-0 left-0 w-[3px]", gyrDotClass(status))} />
        <ChevronRight
          aria-hidden="true"
          className="size-3.5 shrink-0 text-muted-foreground transition-transform group-open:rotate-90 motion-reduce:transition-none"
        />
        <span className="min-w-0 flex-1 truncate text-sm" title={titleHint}>
          {title}
        </span>
        <span className="flex shrink-0 items-center gap-1.5 font-mono text-sm tabular-nums">{trailing}</span>
      </summary>
      {children}
    </details>
  );
}

type SignalRowProps = {
  signal: BriefSignal;
  anchorId?: boolean;
};

/** Critical-строка редакционного брифа: заголовок · причина, ₽-оценка с FX; раскрытие - карточка сигнала (PA-50). */
export function SignalRow({ signal, anchorId }: SignalRowProps) {
  return (
    <SignalRowShell
      id={signal.id}
      status={signal.status}
      anchorId={anchorId}
      titleHint={`${signal.title} · ${signal.cause}`}
      title={
        <>
          <span className="font-medium">{signal.title}</span>
          <span className="text-muted-foreground"> · {signal.cause}</span>
        </>
      }
      trailing={
        <>
          {formatRub(signal.costEstimate)}
          <FxBadge />
        </>
      }
    >
      <SignalDetail signal={signal} />
    </SignalRowShell>
  );
}
