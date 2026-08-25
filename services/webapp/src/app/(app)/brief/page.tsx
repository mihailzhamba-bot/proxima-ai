import type { Metadata } from "next";
import { ModulePlaceholder } from "@/components/module-placeholder";

export const metadata: Metadata = {
  title: "Бриф",
};

export default function BriefPage() {
  return (
    <div className="flex flex-col gap-4">
      <ModulePlaceholder
        title="Daily Brief"
        jiraKey="PA-50"
        description="Утренний бриф: дайджест + critical отдельно; карточка сигнала с причиной, рекомендацией, ₽-оценкой и SourceRef."
      />
    </div>
  );
}
