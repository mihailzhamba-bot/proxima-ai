import type { Metadata } from "next";
import { ModulePlaceholder } from "@/components/module-placeholder";

export const metadata: Metadata = {
  title: "Дашборд",
};

export default function DashboardPage() {
  return (
    <div className="flex flex-col gap-4">
      <ModulePlaceholder
        title="Дашборд кабинета"
        jiraKey="PA-52"
        description="Графики 7/28/90 дней, GYR по SKU, drill-down до SourceRef (артефакт + SHA-256)."
      />
    </div>
  );
}
