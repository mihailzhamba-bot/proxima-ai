"use client";

import * as React from "react";
import { cn } from "@/lib/utils";

export const COUNT_UP_DURATION_MS = 400;

type CountUpProps = React.HTMLAttributes<HTMLSpanElement> & {
  value: number;
  durationMs?: number;
};

/** Число появляется count-up'ом 300-500ms; SSR и prefers-reduced-motion — сразу конечное значение (R08). */
export function CountUp({ value, durationMs = COUNT_UP_DURATION_MS, className, ...props }: CountUpProps) {
  const ref = React.useRef<HTMLSpanElement>(null);

  React.useEffect(() => {
    const node = ref.current;
    if (!node) {
      return;
    }
    const duration = Math.min(500, Math.max(300, durationMs));
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      node.textContent = String(value);
      return;
    }
    let frame = 0;
    const start = performance.now();
    const tick = (now: number) => {
      const progress = Math.min(1, (now - start) / duration);
      const eased = 1 - (1 - progress) ** 3;
      node.textContent = String(Math.round(value * eased));
      if (progress < 1) {
        frame = requestAnimationFrame(tick);
      }
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [value, durationMs]);

  return (
    <span ref={ref} className={cn("tabular-nums", className)} {...props}>
      {value}
    </span>
  );
}
