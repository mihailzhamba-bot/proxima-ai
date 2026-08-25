import type { Metadata } from "next";
import { ModulePlaceholder } from "@/components/module-placeholder";

export const metadata: Metadata = {
  title: "Админ",
};

export default function AdminPage() {
  return (
    <div className="flex flex-col gap-4">
      <ModulePlaceholder
        title="Здоровье систем"
        jiraKey="PA-54"
        description="Статус-карточки VPS / Postgres / collector / releases / Telegram / webapp + deploy-лог. Доступ по роли admin."
      />
    </div>
  );
}
