import * as React from "react";
import { Inbox, type LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";

type EmptyStateProps = React.HTMLAttributes<HTMLDivElement> & {
  icon?: LucideIcon;
  title: string;
  description?: string;
  footnote?: string;
};

export function EmptyState({
  icon: Icon = Inbox,
  title,
  description,
  footnote,
  className,
  children,
  ...props
}: EmptyStateProps) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center gap-2 rounded-md border border-border bg-card px-6 py-10 text-center",
        className,
      )}
      {...props}
    >
      <Icon className="size-6 text-muted-foreground" strokeWidth={1.5} aria-hidden />
      <p className="text-sm font-medium text-foreground">{title}</p>
      {description ? <p className="max-w-sm text-sm text-muted-foreground">{description}</p> : null}
      {footnote ? (
        <p className="mt-1 font-mono text-xs uppercase tracking-wide text-muted-foreground">
          {footnote}
        </p>
      ) : null}
      {children}
    </div>
  );
}
