import * as React from "react";
import { cn } from "@/lib/utils";
import { FX_BADGE_LABEL, fxBadgeClass } from "@/lib/fx";

/** Маркер демо-цифры (fixtures): ставится рядом с каждым числом из lib/fixtures. */
export function FxBadge({ className, ...props }: React.HTMLAttributes<HTMLSpanElement>) {
  return (
    <span className={cn(fxBadgeClass(), className)} {...props}>
      {FX_BADGE_LABEL}
    </span>
  );
}
