"use client";

import * as React from "react";
import { cn } from "@/lib/utils";

type SectionErrorProps = React.HTMLAttributes<HTMLDivElement> & {
  title?: string;
  detail?: string;
  digest?: string;
};

export function SectionError({
  title = "Секция не загрузилась",
  detail,
  digest,
  className,
  ...props
}: SectionErrorProps) {
  return (
    <div
      role="alert"
      className={cn("rounded-md border border-status-red/40 bg-card p-4", className)}
      {...props}
    >
      <p className="text-sm font-medium text-status-red">{title}</p>
      {detail ? <p className="mt-1 text-sm text-muted-foreground">{detail}</p> : null}
      {digest ? (
        <code className="mt-1.5 block font-mono text-xs text-muted-foreground">{digest}</code>
      ) : null}
    </div>
  );
}

type SectionErrorBoundaryProps = {
  children: React.ReactNode;
  title?: string;
  fallback?: (error: Error) => React.ReactNode;
};

type SectionErrorBoundaryState = {
  error: Error | null;
};

export class SectionErrorBoundary extends React.Component<
  SectionErrorBoundaryProps,
  SectionErrorBoundaryState
> {
  state: SectionErrorBoundaryState = { error: null };

  static getDerivedStateFromError(error: Error): SectionErrorBoundaryState {
    return { error };
  }

  render() {
    const { error } = this.state;
    if (error) {
      if (this.props.fallback) {
        return this.props.fallback(error);
      }
      return (
        <SectionError
          title={this.props.title}
          detail={error.message}
          digest={(error as Error & { digest?: string }).digest}
        />
      );
    }
    return this.props.children;
  }
}
