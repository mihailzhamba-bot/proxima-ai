import { Check, ChevronRight, X } from "lucide-react";

const STEPS = [
  {
    key: "offer",
    title: "Предложение",
    body: "Proxima приносит решение и объясняет, зачем оно: поднять ставку, пополнить склад, поправить цену.",
  },
  {
    key: "decision",
    title: "Решение",
    body: "Одно из двух — и всегда осознанно.",
  },
  {
    key: "memory",
    title: "Память",
    body: "Каждое решение с причиной остаётся в истории. Отклонённое не предложат заново без повода.",
  },
] as const;

export function InboxWorkflow() {
  return (
    <div className="mt-6 w-full max-w-2xl rounded-md border border-border bg-card px-4 py-4 text-left">
      <p className="font-mono text-xs uppercase tracking-wide text-muted-foreground">
        как это будет работать
      </p>
      <div className="mt-3 flex flex-col gap-2 sm:flex-row sm:items-stretch sm:gap-3">
        <WorkflowStep step={STEPS[0]} />
        <ChevronRight
          className="hidden size-4 shrink-0 self-center text-muted-foreground sm:block"
          strokeWidth={1.5}
          aria-hidden
        />
        <WorkflowStep step={STEPS[1]} outcome />
        <ChevronRight
          className="hidden size-4 shrink-0 self-center text-muted-foreground sm:block"
          strokeWidth={1.5}
          aria-hidden
        />
        <WorkflowStep step={STEPS[2]} />
      </div>
    </div>
  );
}

function WorkflowStep({
  step,
  outcome = false,
}: {
  step: (typeof STEPS)[number];
  outcome?: boolean;
}) {
  return (
    <div className="flex-1 rounded-sm border border-border p-3">
      <p className="text-sm font-medium text-foreground">{step.title}</p>
      <p className="mt-1 text-sm text-muted-foreground">{step.body}</p>
      {outcome ? (
        <div className="mt-3 flex flex-col gap-1.5">
          <span className="inline-flex items-center gap-2 text-sm text-foreground">
            <Check className="size-4 text-status-green" strokeWidth={2} aria-hidden />
            принял — применяется сразу
          </span>
          <span className="inline-flex items-center gap-2 text-sm text-foreground">
            <X className="size-4 text-status-red" strokeWidth={2} aria-hidden />
            отклонил — указываешь причину
          </span>
        </div>
      ) : null}
    </div>
  );
}
