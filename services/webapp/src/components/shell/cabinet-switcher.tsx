"use client";

import * as React from "react";
import { Check, ChevronsUpDown, Store } from "lucide-react";
import { cn } from "@/lib/utils";
import { FIXTURE_CABINETS } from "@/lib/fixtures/shell";

/** Dropdown-свитчер кабинета: один fixtures-элемент, каркас под список из БД (PA-50). */
export function CabinetSwitcher() {
  const [open, setOpen] = React.useState(false);
  const [selectedId, setSelectedId] = React.useState(FIXTURE_CABINETS[0]?.id ?? "");
  const rootRef = React.useRef<HTMLDivElement>(null);

  React.useEffect(() => {
    if (!open) {
      return;
    }
    function onPointerDown(event: PointerEvent) {
      if (!rootRef.current?.contains(event.target as Node)) {
        setOpen(false);
      }
    }
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setOpen(false);
      }
    }
    document.addEventListener("pointerdown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("pointerdown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  const selected = FIXTURE_CABINETS.find((cabinet) => cabinet.id === selectedId);

  return (
    <div ref={rootRef} className="relative">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        aria-haspopup="menu"
        aria-expanded={open}
        data-testid="cabinet-switcher"
        className="flex h-9 items-center gap-2 rounded-sm border border-border bg-card px-3 text-sm text-foreground transition-colors hover:bg-muted focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
      >
        <Store className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
        <span className="max-w-[220px] truncate">{selected?.label ?? "Кабинет"}</span>
        <ChevronsUpDown className="size-3.5 shrink-0 text-muted-foreground" aria-hidden="true" />
      </button>
      {open && (
        <div
          role="menu"
          className="absolute left-0 top-[calc(100%+4px)] z-10 min-w-full rounded-sm border border-border bg-card py-1 shadow-md"
        >
          {FIXTURE_CABINETS.map((cabinet) => {
            const isSelected = cabinet.id === selectedId;
            return (
              <button
                key={cabinet.id}
                type="button"
                role="menuitem"
                onClick={() => {
                  setSelectedId(cabinet.id);
                  setOpen(false);
                }}
                className={cn(
                  "flex h-9 w-full items-center gap-2 px-3 text-left text-sm",
                  isSelected
                    ? "text-foreground"
                    : "text-muted-foreground hover:bg-muted hover:text-foreground",
                )}
              >
                <Check
                  className={cn("size-4 shrink-0", isSelected ? "opacity-100" : "opacity-0")}
                  aria-hidden="true"
                />
                {cabinet.label}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
