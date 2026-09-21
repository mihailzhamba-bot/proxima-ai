/** DEC-006: пометка unreleased на всех экранах (app)-группы; компактная, одна строка. */
export function UnreleasedBanner({ dataMode = "fixtures" }: { dataMode?: "fixtures" | "staging" | "postgres" }) {
  return (
    <div
      role="note"
      data-testid="data-mode"
      className="border-b border-border bg-muted/60 px-4 py-1 text-xs text-muted-foreground lg:px-6"
    >
      <span className="font-medium">unreleased</span>{dataMode === "fixtures" ? " · демонстрационные данные" : dataMode === "staging" ? " · тестовый стенд" : ""}
    </div>
  );
}
