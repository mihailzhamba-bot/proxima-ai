export const GYR_STATUSES = ["green", "yellow", "red", "neutral"] as const;

export type GyrStatus = (typeof GYR_STATUSES)[number];

export function isGyrStatus(value: unknown): value is GyrStatus {
  return typeof value === "string" && (GYR_STATUSES as readonly string[]).includes(value);
}

const CHIP_CLASSES: Record<GyrStatus, string> = {
  green: "bg-status-green text-status-green-foreground",
  yellow: "bg-status-yellow text-status-yellow-foreground",
  red: "bg-status-red text-status-red-foreground",
  neutral: "bg-status-neutral text-status-neutral-foreground",
};

const DOT_CLASSES: Record<GyrStatus, string> = {
  green: "bg-status-green",
  yellow: "bg-status-yellow",
  red: "bg-status-red",
  neutral: "bg-status-neutral",
};

export function gyrChipClass(status: GyrStatus): string {
  return CHIP_CLASSES[status];
}

export function gyrDotClass(status: GyrStatus): string {
  return DOT_CLASSES[status];
}

export type GyrCounters = Record<"red" | "yellow" | "green", number>;

export function totalSignals(counters: GyrCounters): number {
  return counters.red + counters.yellow + counters.green;
}
