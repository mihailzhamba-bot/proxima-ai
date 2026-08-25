import type { Metadata } from "next";
import { Button } from "@/components/ui/button";
import { Badge, GyrBadge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { formatRub, formatRubCompact, formatRubPrecise } from "@/lib/format/rub";
import { FxBadge } from "@/components/ui/fx-badge";
import { GYR_STATUSES } from "@/lib/gyr";

export const metadata: Metadata = {
  title: "Стайлгайд",
};

const PALETTE = [
  { token: "--background", label: "background" },
  { token: "--card", label: "card" },
  { token: "--muted", label: "muted" },
  { token: "--border", label: "border" },
  { token: "--primary", label: "primary" },
  { token: "--accent", label: "accent" },
] as const;

const GYR_LABELS: Record<(typeof GYR_STATUSES)[number], string> = {
  green: "Норма",
  yellow: "Внимание",
  red: "Критично",
  neutral: "Нет данных",
};

export default function StyleguidePage() {
  return (
    <div className="flex flex-col gap-4">
      <Card>
        <CardHeader>
          <CardTitle>Дизайн-токены webapp</CardTitle>
          <CardDescription>
            Две темы (light/dark) переключателем в сайдбаре. Проверь обе - контраст GYR обязателен в
            каждой.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-wrap gap-3">
          {PALETTE.map((item) => (
            <div key={item.token} className="flex flex-col items-center gap-1.5">
              <div
                className="size-14 rounded-md border border-border"
                style={{ backgroundColor: `var(${item.token})` }}
              />
              <code className="text-xs text-muted-foreground">{item.label}</code>
            </div>
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Статусы GYR</CardTitle>
          <CardDescription>Единый язык статусов на всех экранах.</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-wrap items-center gap-3">
          {GYR_STATUSES.map((status) => (
            <GyrBadge key={status} status={status}>
              {GYR_LABELS[status]}
            </GyrBadge>
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Формат ₽</CardTitle>
          <CardDescription>
            Детерминированные суммы: без копеек в карточках, с копейками в отчётах, компактные в
            счётчиках.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-1 font-mono text-sm">
          <span className="inline-flex items-center gap-1.5">
            {formatRub(1_234_567)} <FxBadge />
          </span>
          <span className="inline-flex items-center gap-1.5">
            {formatRubPrecise(1234.5)} <FxBadge />
          </span>
          <span className="inline-flex items-center gap-1.5">
            {formatRubCompact(1_250_000)} <FxBadge />
          </span>
          <span className="inline-flex items-center gap-1.5">
            {formatRubCompact(145_000)} <FxBadge />
          </span>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Кнопки и бейджи</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-wrap items-center gap-3">
          <Button>Основная</Button>
          <Button variant="outline">Контурная</Button>
          <Button variant="ghost">Ghost</Button>
          <Button variant="destructive">Destructive</Button>
          <Badge>default</Badge>
          <Badge variant="outline">outline</Badge>
          <Badge variant="muted">muted</Badge>
        </CardContent>
      </Card>
    </div>
  );
}
