import { cn } from "@/lib/utils";

type SparklineProps = {
  points: readonly number[];
  width?: number;
  height?: number;
  className?: string;
};

function buildPath(points: readonly number[], width: number, height: number): string {
  const min = Math.min(...points);
  const max = Math.max(...points);
  const span = max - min;
  const pad = 2;
  const usableHeight = height - pad * 2;
  const stepX = points.length > 1 ? width / (points.length - 1) : 0;

  return points
    .map((point, index) => {
      const x = index * stepX;
      const normalized = span === 0 ? 0.5 : (point - min) / span;
      const y = pad + (1 - normalized) * usableHeight;
      return `${index === 0 ? "M" : "L"}${x.toFixed(2)},${y.toFixed(2)}`;
    })
    .join(" ");
}

/** Статичный спарклайн: inline SVG без библиотек; тренд читает дельта, поэтому aria-hidden. */
export function Sparkline({ points, width = 120, height = 36, className }: SparklineProps) {
  if (points.length < 2) {
    return null;
  }

  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      preserveAspectRatio="none"
      aria-hidden="true"
      className={cn("h-9 w-[120px] text-muted-foreground", className)}
      data-testid="sparkline"
    >
      <path
        d={buildPath(points, width, height)}
        fill="none"
        stroke="currentColor"
        strokeWidth={1.5}
        strokeLinecap="round"
        strokeLinejoin="round"
        vectorEffect="non-scaling-stroke"
      />
    </svg>
  );
}
