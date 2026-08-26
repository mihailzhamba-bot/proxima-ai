import type { Metadata } from "next";
import { ListChecks } from "lucide-react";
import { EmptyState } from "@/components/ui/empty-state";
import { SectionErrorBoundary } from "@/components/ui/section-error";
import { InboxWorkflow } from "@/components/empty/inbox-workflow";
import { KeyboardHint } from "@/components/empty/keyboard-hint";

export const metadata: Metadata = {
  title: "Inbox",
};

export default function InboxPage() {
  return (
    <div className="flex flex-col gap-6">
      <SectionErrorBoundary title="Очередь решений">
        <EmptyState
          icon={ListChecks}
          title="Очередь решений пока пуста"
          description="Proxima будет приносить предложения: поднять ставку, пополнить склад, поправить цену. Каждое — принять или отклонить с причиной."
          footnote="оживает в PA-51"
        >
          <InboxWorkflow />
        </EmptyState>
      </SectionErrorBoundary>
      <SectionErrorBoundary title="Подсказки клавиш">
        <KeyboardHint />
      </SectionErrorBoundary>
    </div>
  );
}
