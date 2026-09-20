import { Skeleton } from "@/components/ui/skeleton";

type FutureBlockShape = "chart" | "sku" | "source";

type FutureBlockProps = {
  title: string;
  note: string;
  shape: FutureBlockShape;
  tag?: string;
};

export function FutureBlock({ title, note, shape, tag = "PA-52" }: FutureBlockProps) {
  return (
    <div className="h-full rounded-md border border-border bg-card p-4">
      <div className="flex items-baseline justify-between gap-2">
        <p className="text-sm font-medium text-foreground">{title}</p>
        <span className="font-mono text-xs uppercase tracking-wide text-muted-foreground">
          {tag}
        </span>
      </div>
      <p className="mt-1 text-sm text-muted-foreground">{note}</p>
      <div className="mt-4">
        {shape === "chart" ? <ChartShape /> : null}
        {shape === "sku" ? <SkuShape /> : null}
        {shape === "source" ? <SourceShape /> : null}
      </div>
    </div>
  );
}

function ChartShape() {
  return (
    <div>
      <div className="flex h-24 items-end gap-1.5" aria-hidden>
        <Skeleton className="h-10 flex-1" />
        <Skeleton className="h-16 flex-1" />
        <Skeleton className="h-8 flex-1" />
        <Skeleton className="h-20 flex-1" />
        <Skeleton className="h-12 flex-1" />
        <Skeleton className="h-24 flex-1" />
        <Skeleton className="h-14 flex-1" />
        <Skeleton className="h-9 flex-1" />
        <Skeleton className="h-18 flex-1" />
        <Skeleton className="h-16 flex-1" />
        <Skeleton className="h-11 flex-1" />
        <Skeleton className="h-20 flex-1" />
      </div>
      <div className="mt-2 flex items-center gap-3 font-mono text-xs text-muted-foreground">
        <span className="rounded-sm border border-border px-1.5 py-0.5">7д</span>
        <span className="rounded-sm border border-border px-1.5 py-0.5">28д</span>
        <span className="rounded-sm border border-border px-1.5 py-0.5">90д</span>
      </div>
    </div>
  );
}

function SkuShape() {
  return (
    <div className="flex flex-col gap-2" aria-hidden>
      {[0, 1, 2, 3].map((row) => (
        <div key={row} className="flex items-center gap-2">
          <Skeleton className="h-4 w-1 rounded-full" />
          <Skeleton className="h-3 flex-1" />
          <Skeleton className="h-3 w-14" />
        </div>
      ))}
    </div>
  );
}

function SourceShape() {
  return (
    <div className="flex flex-col gap-2" aria-hidden>
      {[0, 1, 2].map((row) => (
        <div key={row} className="flex items-center gap-2">
          <Skeleton className="h-3 flex-1" />
          <Skeleton className="h-3 w-28 rounded-sm" />
        </div>
      ))}
      <p className="mt-1 font-mono text-xs text-muted-foreground">SHA-256</p>
    </div>
  );
}
