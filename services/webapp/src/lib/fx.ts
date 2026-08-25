export const FX_BADGE_LABEL = "FX";

export function fxBadgeClass(): string {
  return [
    "inline-flex items-center rounded-sm border border-border bg-muted px-1.5 py-px",
    "font-mono text-[10px] font-medium uppercase tracking-wide text-muted-foreground",
  ].join(" ");
}
