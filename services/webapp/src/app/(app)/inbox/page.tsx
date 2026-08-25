import type { Metadata } from "next";
import { ModulePlaceholder } from "@/components/module-placeholder";

export const metadata: Metadata = {
  title: "Inbox",
};

export default function InboxPage() {
  return (
    <div className="flex flex-col gap-4">
      <ModulePlaceholder
        title="Decision Inbox"
        jiraKey="PA-51"
        description="Принял / отклонил / отложил + причина. Зародыш Decision Memory: каждое решение фиксируется."
      />
    </div>
  );
}
