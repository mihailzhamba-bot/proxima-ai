# Web-кабинет (services/webapp) - память яруса T2

> Перенесено из `AGENTS.md` 30.08.2026 (bmad-project-context). Память автопилота на момент прогона PA-49 Warm Precision (25-26.08.2026); не текущие требования - актуальное в `/STATE.md`, `/DECISIONS.md`, блоке `bmad:context` в `AGENTS.md`.

## Web-кабинет (services/webapp) - память яруса T2

Приватный UI Proxima: Next.js 16.3 App Router + Tailwind 4 + TS strict + vitest; данные - только демо-fixtures, экран под плашкой unreleased (DEC-006). Прогон PA-49 Warm Precision сдан (vitest 26 passed, make verify PASS, build зелёный).

### Команды

```
npm --workspace @proxima/webapp run dev      # dev; порт 3000 занят -> Next молча займёт 3001
npm --workspace @proxima/webapp test         # vitest run
npm --workspace @proxima/webapp exec -- vitest run src/tests/fx.test.ts   # один файл (npx … --root из корня: vitest not found)
npm --workspace @proxima/webapp run typecheck | lint | build # по одной
make verify                                  # полный гейт из корня репо
make webapp-build | make webapp-lint         # те же цели из Makefile
ssh -N proxima-app                           # staging: http://localhost:3000, контейнер proxima-webapp-staging (loopback VPS)
```

### Структура (services/webapp)

- `src/app/layout.tsx` - шрифты Inter + IBM Plex Mono (next/font), ThemeProvider (next-themes)
- `src/app/(app)/` - защищённая зона: `layout.tsx` + страницы `dashboard | brief | inbox | admin | styleguide`
- `src/app/login/`, `src/app/api/auth/[...all]/route.ts` - better-auth обвязка (логику не трогать)
- `src/components/ui/` - примитивы: Button Card Badge GyrBadge FxBadge Skeleton EmptyState SectionError(+Boundary)
- `src/components/metrics/` - MetricStrip MetricCard Sparkline (inline SVG, `max-[379px]:hidden`)
- `src/components/brief/` - SignalRow BriefVerdict Digest CountUp
- `src/components/shell/` - app-sidebar (w-64) cabinet-switcher unreleased-banner
- `src/components/empty/` - InboxWorkflow KeyboardHint FutureBlock AdminModuleStub (6 модулей)
- `src/lib/fixtures/` - metrics brief shell: единственный источник демо-данных (getMetrics/getBrief, префикс fixture-)
- `src/lib/` - gyr.ts fx.ts format/rub.ts utils.ts (семантика и форматирование)
- `src/lib/auth.ts`, `src/lib/auth-client.ts`, `src/lib/db/` - auth + drizzle/pg, запретная зона
- `src/tests/` - fx gyr rub metrics brief-fixtures (5 файлов)
- `Dockerfile` - multi-stage standalone-сборка; секреты приходят окружением на VPS, в образ не печём

### Ключевые файлы

- `services/webapp/src/app/globals.css` - все CSS-токены обеих тем; единственное место с сырыми hex
- `services/webapp/src/lib/fixtures/metrics.ts` - `getMetrics(): readonly FixtureMetric[]`, `getMetrics.dataMode = "fixtures"`
- `services/webapp/src/lib/fixtures/brief.ts` - `getBrief(variant?: "daily"|"quiet")`
- `services/webapp/src/components/metrics/metric-strip.tsx` - метрическая полоса дашборда
- `services/webapp/src/app/(app)/brief/page.tsx` - `/brief?view=quiet` = тихий день («Критичных нет»)
- `services/webapp/src/app/(app)/styleguide/page.tsx` - живой стайлгайд примитивов
- `DESIGN.md` (корень репо) - канон дизайн-системы

### Архитектура

Поток зависимостей: `globals.css` (tokens) -> `lib/fixtures` (провайдер демо-данных) -> `components/ui` (примитивы) -> зоны `metrics | brief | shell | empty` -> страницы `(app)`.
Семантика живёт в либах, не в UI: дельта тонирована по `deltaGoodWhen` из fixtures, GYR/FX-статусы - `lib/gyr`/`lib/fx`.
Швы тестов: геттеры `lib/fixtures` (форма данных стабильна) + чистые `lib/gyr` + `lib/format/rub`; DOM проверяется smoke-сборкой и стайлгайдом, E2E нет.
Секции inbox/dashboard/admin обёрнуты SectionErrorBoundary (2/4/6 секций) - падение секции не роняет экран.

### Соглашения кода

- Сырые hex - только в `globals.css`; компоненты берут цвет исключительно через CSS-переменные.
- Любая демо-цифра на экране - с FxBadge (`lib/fx`, метка "FX"); fixtures обезличены, префикс `fixture-`, без реальных cabinet ID/SKU/цен.
- Плашка unreleased (решение DEC-006) остаётся на всех экранах, снимать нельзя.
- Язык UI русский, идентификаторы английские; без эмодзи, без комментариев в коде (кроме неочевидного).
- Запретная зона правок: `src/lib/auth*`, `src/app/api/auth/`, `src/app/login/`, `Dockerfile`, `infra/*`, `src/lib/db/*`, `Makefile`, `package.json` (новые зависимости = BLOCKED).

### Окружение (имена, не значения)

- `WEBAPP_REQUIRE_AUTH` - гейт auth на `(app)`, читается в `src/app/(app)/layout.tsx:18`
- `WEBAPP_DATA_DATABASE_URI` (fallback `DATABASE_URI`) - данные, `src/lib/db/client.ts:45,55`
- `BETTER_AUTH_SECRET`, `BETTER_AUTH_URL`, `WEBAPP_AUTH_DATABASE_URI` - better-auth (`src/lib/auth.ts:11`, `src/lib/db/client.ts:33`)
- `NEXT_TELEMETRY_DISABLED`, `PUPPETEER_SKIP_DOWNLOAD` - выставлены в `Dockerfile`

### Подводные камни

- `eslint` запинен на `9.39.5` в `services/webapp/package.json`: eslint-config-next 16.3.3 заявляет peer `>=9`, но на eslint 10 конфиг не проверялся - не апгрейдить мимо пина.
- `**/.next/` в `.gitignore:10` держите: попади сборочный вывод в tracked-файлы, secret_scan (`make verify`) уронит гейт.
- `PUPPETEER_SKIP_DOWNLOAD=1` в Dockerfile (deps-stage): транзитивный puppeteer иначе тянет Chromium при `npm ci` - образу он не нужен.
- Тёмная тема: обе палитры (light ivory / dark stone) калиброваны в globals.css (`.dark` через next-themes); правка токена - сразу в двух темах.
- `next dev` при занятом 3000 молча уходит на 3001 - проверяйте адресную строку.

### Тесты

- `npm --workspace @proxima/webapp test` = vitest, 26 passed по 5 файлам (`src/tests/{fx,gyr,rub,metrics,brief-fixtures}.test.ts`).
- Один файл: `npm --workspace @proxima/webapp exec -- vitest run src/tests/metrics.test.ts`.
- Юнит-тесты ходят только через швы (fixtures-геттеры, gyr, rub); разметку юнит-тестами не покрывать.

### Как здесь работает Autopilot

Прогон PA-49 Warm Precision (режим interview) сдан. Спека и таски - в `.autopilot/2026-08-25-pa49-warm-precision/`, прогресс - `.autopilot/dashboard.html`.
Продолжение работы: сказать «продолжи автопилот» - состояние поднимется из `.autopilot/state.js`, переспрашивать не нужно.
Правило неизменно: требование из `manifest.md` может снять только пользователь.
