import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { GyrBadge } from "@/components/ui/badge";
import type { GyrStatus } from "@/lib/gyr";

type ModulePlaceholderProps = {
  title: string;
  jiraKey: string;
  description: string;
};

/** Скелет модуля: виден в навигации с первого деплоя, оживает своей подзадачей PA-38. */
export function ModulePlaceholder({ title, jiraKey, description }: ModulePlaceholderProps) {
  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between">
        <div className="flex flex-col gap-1.5">
          <CardTitle>{title}</CardTitle>
          <CardDescription>{description}</CardDescription>
        </div>
        <GyrStatusStub />
      </CardHeader>
      <CardContent>
        <p className="text-sm text-muted-foreground">
          Модуль в каркасе. Оживает в <span className="font-mono text-xs">{jiraKey}</span>; данные —
          fixtures, пометка unreleased на каждом экране (DEC-006).
        </p>
      </CardContent>
    </Card>
  );
}

function GyrStatusStub() {
  const status: GyrStatus = "neutral";
  return <GyrBadge status={status}>Каркас</GyrBadge>;
}
