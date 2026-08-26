# Interfaces — PA-49 Warm Precision

## Границы, решённые в спецификации

| Модуль | Владеет | Выставляет | Прячет |
|---|---|---|---|
| `tokens` (globals.css) | все CSS-переменные обеих тем, radius, selection, focus | классы-токены через CSS vars | конкретные hex (только здесь) |
| `lib/fixtures` | все демо-данные (метрики, сигналы, дельты, точки спарклайнов) | типизированные геттеры `getMetrics()`, `getBrief()` | форматы и структурные значения |
| `components/ui` | примитивы Button/Card/Badge/GyrBadge/FxBadge/Skeleton/EmptyState/SectionError | React-компоненты | внутреннюю разметку |
| `components/metrics` | MetricStrip/MetricCard/Sparkline | `<MetricStrip/>` | расчёт path, деградацию на узких экранах |
| `components/brief` | SignalRow/BriefVerdict/Digest | состав `/brief` | верстку строк |
| `shell` | сайдбар, топбар-полоса, unreleased-плашка, свитчер кабинета | layout | активную навигацию (usePathname) |
| `staging` (инфра) | скрипт сборки/запуска на VPS | runbook-шаги в отчёте | детали VPS |

Швы для тестов: (1) геттеры `lib/fixtures` — форма данных стабильна; (2) `lib/gyr` / `lib/format` — существующие, расширяются FX-токенами. DOM проверяется smoke-сборкой + стайлгайд; E2E нет.

## Из таска 01 — токены, шрифты, примитивы

- Токены: обе палитры (light ivory / dark stone) в globals.css; добавлены `--color-primary-hover`, `--color-ink`, `--color-status-info(+foreground)`; радиусы 4/8/12px; фокус-ring и ::selection violet
- Шрифты: Inter (variable) + IBM Plex Mono через next/font в layout.tsx (self-hosted)
- `lib/fx`: `FX_BADGE_LABEL="FX"`, `fxBadgeClass(): string`
- `components/ui`: `FxBadge(span-props)`, `Skeleton(div-props)`, `EmptyState({icon?, title, description?, footnote?})`, `SectionError({title?, detail?, digest?})`, `SectionErrorBoundary({children, title?, fallback?})`; Button/Card/Badge/GyrBadge переведены на тёплые токены
- Правило: сырые hex только в globals.css; компоненты — только через CSS-переменные
- Тесты: vitest 14 (было 11), +`src/tests/fx.test.ts`

## Из таска 02 — shell + метрическая полоса

- `lib/fixtures/metrics`: `getMetrics(): readonly FixtureMetric[]`, `getMetrics.dataMode = "fixtures"`; `FixtureMetric {id: MetricId, label, value: number|null, format: "count"|"rub-compact"|"clock", status: GyrStatus|null, deltaPercent, deltaGoodWhen, points: readonly number[]}`
- `components/metrics`: `<MetricStrip/>`, `<MetricCard metric/>`, `<Sparkline points/>` (inline SVG, статичный; `max-[379px]:hidden`)
- `components/shell`: сайдбар w-64 с секциями; `cabinet-switcher.tsx` (client dropdown); `app-topbar.tsx` удалён (заменён полосой); unreleased-баннер компактен
- Дельта тонирована по `deltaGoodWhen` из провайдера (семантика владеет fixtures, не UI)

## Из таска 03 — brief

- `lib/fixtures/brief`: `getBrief(variant?: "daily"|"quiet"): BriefData` — `{variant, dateIso, signals: BriefSignal[{id,status,title,cause,costEstimate}], attentionCount, digest: BriefDigestItem[{id,tone,text}], dataMode}`
- `components/brief`: `<SignalRow signal anchorId?>`, `<BriefVerdict dateIso criticalCount attentionCount firstCriticalId?>`, `<Digest items>`, `<CountUp value durationMs?>` + `COUNT_UP_DURATION_MS=400` (rAF+ref, 300-500ms, reduced-motion → сразу)
- Тихий экран: `/brief?view=quiet` (нет critical → вердикт «Критичных нет»)

## Из таска 04 — скелетные экраны

- `components/empty`: `InboxWorkflow()`, `KeyboardHint()`, `FutureBlock({title, note, shape: "chart"|"sku"|"source", tag?})`, `AdminModuleStub({module})` + `ADMIN_MODULES: AdminModule[]` (6 модулей)
- inbox/dashboard/admin обёрнуты SectionErrorBoundary (2/4/6 секций); `module-placeholder.tsx` удалён (мёртв после ухода brief на свои компоненты)

## Правила проекта (для каждого сабагента)

- Стек: Next.js 16.3 App Router, Tailwind 4 (@theme inline), TypeScript strict, vitest. Node >=22 <23.
- Команды: typecheck `npm --workspace @proxima/webapp run typecheck`; тесты `npm --workspace @proxima/webapp test`; lint `npm --workspace @proxima/webapp run lint`; build `npm --workspace @proxima/webapp run build`; полный гейт `make verify` (из корня репо).
- Запреты: НЕ трогать `src/lib/auth*`, `src/app/api/auth/`, `src/app/login/` (логика; визуальные токены каскадом — можно), `Dockerfile`, `infra/*`, `src/lib/db/*`, `Makefile`, `package.json` (новые зависимости = BLOCKED, не install).
- Секреты: в коде и fixtures нет и не должно быть; значения	env только именами.
- fixtures: обезличенные структурные значения, префикс fixture-, никаких реальных cabinet ID/SKU/цен.
- Пометка unreleased (DEC-006) остаётся на всех экранах; демо-цифры — всегда с FxBadge.
- Стиль: DESIGN.md — канон; цвета только через CSS-переменные из globals.css; в компонентах ноль сырых hex. Русский UI, английские идентификаторы. Без эмодзи. Без комментариев в коде, кроме случая, когда без них не читается.
- Git: работа на ветке `feat/pa-49-warm-precision`; стейджить только файлы своей зоны; `git add -A` запрещён; в main не коммитить.
