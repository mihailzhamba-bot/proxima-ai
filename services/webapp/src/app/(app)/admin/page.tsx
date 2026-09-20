import type { Metadata } from "next";
import { SectionErrorBoundary } from "@/components/ui/section-error";
import { ADMIN_MODULES, AdminModuleStub } from "@/components/empty/admin-module-stub";

export const metadata: Metadata = {
  title: "Админ",
};

export default function AdminPage() {
  return (
    <div className="flex flex-col gap-6">
      <div>
        <p className="text-sm text-muted-foreground">
          Шесть модулей здоровья платформы. Статусы и цифры появятся позже — сейчас видно, за чем
          следить.
        </p>
        <p className="mt-1 font-mono text-xs uppercase tracking-wide text-muted-foreground">
          оживёт в PA-54
        </p>
      </div>
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {ADMIN_MODULES.map((module) => (
          <SectionErrorBoundary key={module.key} title={module.name}>
            <AdminModuleStub module={module} />
          </SectionErrorBoundary>
        ))}
      </div>
    </div>
  );
}
