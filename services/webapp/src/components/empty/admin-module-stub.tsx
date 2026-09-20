import { GyrBadge } from "@/components/ui/badge";

export type AdminModule = {
  key: string;
  name: string;
  description: string;
};

export const ADMIN_MODULES: AdminModule[] = [
  {
    key: "vps",
    name: "VPS",
    description: "жив ли сервер, сколько памяти и диска в запасе",
  },
  {
    key: "postgres",
    name: "Postgres",
    description: "состояние базы: миграции, размер, соединения",
  },
  {
    key: "collector",
    name: "Collector",
    description: "когда в последний раз собирались данные WB",
  },
  {
    key: "releases",
    name: "Releases",
    description: "какие доменные релизы применены и когда",
  },
  {
    key: "telegram",
    name: "Telegram",
    description: "дошёл ли утренний бриф и тревожные оповещения",
  },
  {
    key: "webapp",
    name: "Webapp",
    description: "какая версия кабинета собрана и здорова ли она",
  },
];

export function AdminModuleStub({ module }: { module: AdminModule }) {
  return (
    <div className="h-full rounded-md border border-border bg-card p-4">
      <div className="flex items-center justify-between gap-2">
        <p className="text-sm font-medium text-foreground">{module.name}</p>
        <GyrBadge status="neutral">Каркас</GyrBadge>
      </div>
      <p className="mt-1.5 text-sm text-muted-foreground">{module.description}</p>
    </div>
  );
}
