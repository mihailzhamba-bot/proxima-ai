import type { Metadata } from "next";
import { Button } from "@/components/ui/button";
import { Badge, GyrBadge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { FxBadge } from "@/components/ui/fx-badge";
import { SectionError } from "@/components/ui/section-error";
import { Skeleton } from "@/components/ui/skeleton";
import { MetricCard } from "@/components/metrics/metric-card";
import { formatRub, formatRubCompact, formatRubPrecise } from "@/lib/format/rub";
import { getMetrics } from "@/lib/fixtures/metrics";
import { GYR_STATUSES } from "@/lib/gyr";

export const metadata: Metadata = {
  title: "Стайлгайд",
};

const TOKEN_GROUPS: readonly { title: string; tokens: readonly string[] }[] = [
  {
    title: "Поверхности",
    tokens: [
      "--background",
      "--foreground",
      "--card",
      "--card-foreground",
      "--muted",
      "--muted-foreground",
      "--border",
      "--input",
    ],
  },
  {
    title: "Акцент и чернила",
    tokens: [
      "--primary",
      "--primary-foreground",
      "--primary-hover",
      "--accent",
      "--accent-foreground",
      "--ring",
      "--ink",
    ],
  },
  {
    title: "Выделение текста",
    tokens: ["--selection-background", "--selection-foreground"],
  },
  {
    title: "Статусы",
    tokens: [
      "--status-green",
      "--status-green-foreground",
      "--status-yellow",
      "--status-yellow-foreground",
      "--status-red",
      "--status-red-foreground",
      "--status-info",
      "--status-info-foreground",
      "--status-neutral",
      "--status-neutral-foreground",
    ],
  },
];

const TYPE_ROWS: readonly { name: string; className: string; sample: string }[] = [
  {
    name: "headline-lg · Inter 32/600",
    className: "font-sans text-[32px] font-semibold leading-[1.15] tracking-[-0.02em]",
    sample: "Утренний бриф кабинета",
  },
  {
    name: "headline-md · Inter 24/600",
    className: "font-sans text-2xl font-semibold leading-[1.2] tracking-[-0.01em]",
    sample: "Показатели за день",
  },
  {
    name: "body-md · Inter 15/400",
    className: "font-sans text-[15px] leading-[1.55]",
    sample:
      "Выручка выросла на 8,4% к прошлой неделе при том же рекламном бюджете — рост держится третий день.",
  },
  {
    name: "label-md · Inter 12/500 uppercase",
    className: "font-sans text-xs font-medium uppercase leading-[1.2] tracking-[0.06em]",
    sample: "Свежесть данных",
  },
  {
    name: "data-md · IBM Plex Mono 14/400",
    className: "font-mono text-sm leading-[1.45] tabular-nums",
    sample: "1 234 567 ₽ · fixture-sku-100234 · 06:12",
  },
];

function Swatch({ token, forced }: { token: string; forced?: boolean }) {
  const swatch = (
    <div
      className="size-8 rounded-sm border border-border"
      style={{ backgroundColor: `var(${token})` }}
    />
  );
  return forced ? <div className="dark">{swatch}</div> : swatch;
}

function SwatchRow({ token }: { token: string }) {
  return (
    <div className="grid grid-cols-[minmax(0,1fr)_auto_auto] items-center gap-4 border-b border-border py-2 last:border-b-0">
      <code className="min-w-0 truncate font-mono text-xs text-muted-foreground">{token}</code>
      <Swatch token={token} />
      <Swatch token={token} forced />
    </div>
  );
}

export default function StyleguidePage() {
  const metrics = getMetrics();
  const metric = metrics.find((item) => item.id === "revenue-day") ?? metrics[0];

  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-6">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Стайлгайд канона Warm Precision</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Эталон для сверки доводки. Все блоки собраны из боевых компонентов и живых токенов
          globals.css: поломка любого примитива видна здесь сразу. Тему переключай существующим
          переключателем в сайдбаре и проверяй обе.
        </p>
      </header>

      <Card>
        <CardHeader>
          <CardTitle>Палитра: токены обеих тем</CardTitle>
          <CardDescription>
            Свотчи красятся напрямую из CSS-переменных globals.css. Правая колонка всегда показывает
            значения .dark; левая сверяется в светлой теме (в тёмной она следует активной теме).
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-5">
          {TOKEN_GROUPS.map((group) => (
            <div key={group.title}>
              <p className="mb-1 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                {group.title}
              </p>
              <div className="grid grid-cols-[minmax(0,1fr)_auto_auto] items-center gap-4 border-b border-border pb-1 text-xs font-medium uppercase tracking-wide">
                <span className="text-muted-foreground">Токен</span>
                <span className="w-8 text-center text-muted-foreground">light</span>
                <span className="w-8 text-center text-muted-foreground">dark</span>
              </div>
              {group.tokens.map((token) => (
                <SwatchRow key={token} token={token} />
              ))}
            </div>
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Типографика</CardTitle>
          <CardDescription>
            Inter для интерфейса, IBM Plex Mono для чисел, SKU и дат. Метки — uppercase с широким
            трекингом.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-5">
          {TYPE_ROWS.map((row) => (
            <div key={row.name}>
              <code className="font-mono text-xs text-muted-foreground">{row.name}</code>
              <p className={`mt-1 text-foreground ${row.className}`}>{row.sample}</p>
            </div>
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Hairline против тени</CardTitle>
          <CardDescription>
            Постоянные слои разделяются границей 1px; тень — только у транзиентных слоёв вроде
            dropdown.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid gap-4 rounded-md bg-background p-4 sm:grid-cols-2">
            <div className="rounded-md border border-border bg-card p-5">
              <p className="text-sm font-medium">Постоянный слой: hairline</p>
              <p className="mt-1 text-sm text-muted-foreground">
                Карточки, панели, таблицы — граница вместо тени.
              </p>
            </div>
            <div className="rounded-md bg-card p-5 shadow-lg">
              <p className="text-sm font-medium">Транзиентный слой: тень</p>
              <p className="mt-1 text-sm text-muted-foreground">
                Одна мягкая тень, без границы — появляется и уходит вместе со слоем.
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Статусы GYR</CardTitle>
          <CardDescription>Единый язык статусов; контраст чипов проверяй в обеих темах.</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-wrap items-center gap-3">
          {GYR_STATUSES.map((status) => (
            <GyrBadge key={status} status={status} />
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Форматы ₽ и FX-бейдж</CardTitle>
          <CardDescription>
            Детерминированное форматирование: без копеек в карточках, с копейками в отчётах,
            компактные в счётчиках. Любая цифра из fixtures несёт бейдж FX.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-2">
          <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
            <code className="font-mono text-xs text-muted-foreground">formatRub</code>
            <span className="inline-flex items-center gap-1.5 font-mono text-sm tabular-nums">
              {formatRub(1_234_567)} <FxBadge />
            </span>
          </div>
          <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
            <code className="font-mono text-xs text-muted-foreground">formatRubPrecise</code>
            <span className="inline-flex items-center gap-1.5 font-mono text-sm tabular-nums">
              {formatRubPrecise(1234.5)} <FxBadge />
            </span>
          </div>
          <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
            <code className="font-mono text-xs text-muted-foreground">formatRubCompact</code>
            <span className="inline-flex items-center gap-1.5 font-mono text-sm tabular-nums">
              {formatRubCompact(1_250_000)} <FxBadge /> · {formatRubCompact(145_000)} <FxBadge />
            </span>
          </div>
          <div className="mt-2 flex items-center gap-2 border-t border-border pt-3">
            <span className="font-mono text-sm tabular-nums">412</span>
            <FxBadge />
            <span className="text-sm text-muted-foreground">демо-цифра помечена на первый взгляд</span>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Состояния карточек</CardTitle>
          <CardDescription>
            Загрузка, пустое состояние и ошибка секции — живыми компонентами, не картинками.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <div className="flex items-end justify-between gap-3 rounded-lg border border-border bg-card p-4">
            <div className="flex flex-col gap-2">
              <Skeleton className="h-3 w-24" />
              <Skeleton className="h-8 w-32" />
              <Skeleton className="h-3 w-24" />
            </div>
            <Skeleton className="h-10 w-24 rounded-lg" />
          </div>
          <EmptyState
            title="Решений пока нет"
            description="Очередь принятых и отклонённых решений оживёт в PA-51."
            footnote="PA-51"
          />
          <SectionError
            detail="Источник данных недоступен — демо fallback-состояния секции."
            digest="fixture-error-digest"
          />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Метрика вживую</CardTitle>
          <CardDescription>
            MetricCard на данных getMetrics(): число mono, FX-бейдж, дельта к 7 дням, статичный
            спарклайн.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <MetricCard metric={metric} />
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
