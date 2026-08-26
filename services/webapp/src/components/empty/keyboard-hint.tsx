import { Keyboard } from "lucide-react";

type HintItem = {
  keys: string[];
  label: string;
};

const HINTS: HintItem[] = [
  { keys: ["J", "K"], label: "листать очередь" },
  { keys: ["Enter"], label: "принять" },
  { keys: ["E"], label: "отклонить с причиной" },
];

export function KeyboardHint() {
  return (
    <div className="flex flex-wrap items-center gap-x-5 gap-y-3 rounded-md border border-border bg-card px-4 py-3">
      <Keyboard className="size-4 text-muted-foreground" strokeWidth={1.5} aria-hidden />
      <ul className="flex flex-wrap items-center gap-x-5 gap-y-2">
        {HINTS.map((hint) => (
          <li key={hint.label} className="flex items-center gap-2">
            {hint.keys.map((key) => (
              <kbd
                key={key}
                className="inline-flex h-6 min-w-6 items-center justify-center rounded-sm border border-border bg-muted px-1.5 font-mono text-xs text-foreground"
              >
                {key}
              </kbd>
            ))}
            <span className="text-sm text-muted-foreground">{hint.label}</span>
          </li>
        ))}
      </ul>
      <p className="ml-auto font-mono text-xs uppercase tracking-wide text-muted-foreground">
        каркас · заработает в PA-51
      </p>
    </div>
  );
}
