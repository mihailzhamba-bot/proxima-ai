import { TriangleAlert } from "lucide-react";

/**
 * DEC-006: пока M1 release pointer не двигается, все экраны webapp несут
 * явную пометку unreleased и источник данных.
 */
export function UnreleasedBanner({ dataMode = "fixtures" }: { dataMode?: "fixtures" | "staging" }) {
  return (
    <div
      role="note"
      className="flex items-center gap-2 border-b border-border bg-muted/60 px-4 py-1.5 text-xs text-muted-foreground lg:px-6"
    >
      <TriangleAlert className="size-3.5 shrink-0" aria-hidden="true" />
      <span>
        <strong className="font-semibold text-foreground">unreleased</strong> · данные: {dataMode} ·
        стейджинг-контур, M1 release pointer не двигается (DEC-006)
      </span>
    </div>
  );
}
