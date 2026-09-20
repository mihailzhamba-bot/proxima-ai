import * as React from "react";
import { cn } from "@/lib/utils";
import { gyrChipClass, isGyrStatus, type GyrStatus } from "@/lib/gyr";

type BadgeVariant = "default" | "outline" | "muted";

const VARIANTS: Record<BadgeVariant, string> = {
  default: "bg-primary text-primary-foreground",
  outline: "border border-border text-foreground",
  muted: "bg-muted text-muted-foreground",
};

export function Badge({
  className,
  variant = "default",
  ...props
}: React.HTMLAttributes<HTMLSpanElement> & { variant?: BadgeVariant }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium",
        VARIANTS[variant],
        className,
      )}
      {...props}
    />
  );
}

/** Чип статуса GYR: контрастная заливка статусным цветом. */
export function GyrBadge({
  status,
  className,
  children,
  ...props
}: React.HTMLAttributes<HTMLSpanElement> & { status: GyrStatus }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold",
        gyrChipClass(status),
        className,
      )}
      {...props}
    >
      {children ?? gyStatusLabel(status)}
    </span>
  );
}

const LABELS: Record<GyrStatus, string> = {
  green: "Норма",
  yellow: "Внимание",
  red: "Критично",
  neutral: "Нет данных",
};

export function gyStatusLabel(status: GyrStatus): string {
  return LABELS[status];
}

export function asGyrStatusOrNeutral(value: unknown): GyrStatus {
  return isGyrStatus(value) ? value : "neutral";
}
