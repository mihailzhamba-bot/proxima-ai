import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { FIXTURE_SHELL_COUNTERS } from "@/lib/fixtures/shell";

type CounterItem = {
  status: "red" | "yellow" | "green";
  label: string;
  className: string;
};

export function AppTopbar() {
  const counters = FIXTURE_SHELL_COUNTERS;

  const items: CounterItem[] = [
    { status: "red", label: "Критично", className: "bg-status-red text-status-red-foreground" },
    { status: "yellow", label: "Внимание", className: "bg-status-yellow text-status-yellow-foreground" },
    { status: "green", label: "Норма", className: "bg-status-green text-status-green-foreground" },
  ];

  return (
    <header className="flex h-14 items-center gap-4 border-b border-border px-4 lg:px-6">
      <span className="text-sm font-semibold text-muted-foreground">Сигналы сегодня:</span>
      <div className="flex items-center gap-2" role="status" aria-label="Счётчики сигналов GYR">
        {items.map((item) => (
          <span
            key={item.status}
            className={cn(
              "inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-sm font-semibold tabular-nums",
              item.className,
            )}
          >
            <span aria-hidden="true">{counters[item.status]}</span>
            <span className="sr-only">{item.label}</span>
            <span aria-hidden="true" className="text-xs font-medium">
              {item.label}
            </span>
          </span>
        ))}
      </div>
      <div className="ml-auto flex items-center gap-3">
        <Badge variant="muted" data-testid="data-mode">
          данные: fixtures
        </Badge>
        <CabinetSwitcher />
      </div>
    </header>
  );
}

function CabinetSwitcher() {
  // Статический список из fixtures; реальный список кабинетов придёт из БД (PA-50+).
  return (
    <span
      className="inline-flex items-center rounded-md border border-border bg-card px-3 py-1.5 text-sm text-muted-foreground"
      data-testid="cabinet-switcher"
      title="Переключение кабинетов появится с подключением данных (PA-50)"
    >
      Пилотный кабинет (fixtures)
    </span>
  );
}
