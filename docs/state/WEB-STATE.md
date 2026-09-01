# WEB-STATE - веб-морда `services/webapp`

Снято 30.08.2026. Локальный клон `~/Desktop/Проекты/Proxima/proxima-ai` (ветка `docs/session-1-inventory`, HEAD = origin/main `db56429`). Сервер `proxima` (135.106.186.210) - только чтение. Каждый факт = команда + дата; чего не проверил - «не выяснено».

## 1. TL;DR

- Стек: Next.js 16.3.3 (App Router, Turbopack, standalone) + React 19.2.8 + TypeScript 5.8.3 + Tailwind 4.3.3 + Better Auth 1.7.1 + Drizzle 0.45.2/pg 8.16.3 + vitest 4.1.11. 2401 строк ts/tsx в `src/`, 0 TODO/FIXME.
- Состояние кода: всё зелёное 30.08.2026 - `npm ci` 28с, `next build` 10с (9 маршрутов), vitest 26/26 за 2с, lint 0, tsc 0.
- Содержание: 1 «живой» экран `/brief` (утренний бриф) + метрическая полоса, остальные 3 экрана - спроектированные заглушки (PA-51/52/54). 100% данных - fixtures в `src/lib/fixtures/`; БД-чтение написано, но нигде не вызывается.
- Сервер: :3000 держит контейнер `proxima-webapp-staging` (образ `bae976c` от 26.08, ручной `docker run`, без compose/systemd), отвечает 200 на всех экранах, `WEBAPP_REQUIRE_AUTH=false`. Отстаёт от main на 5 webapp-коммитов.
- Вердикт: **полуживая** - каркас качественный и свежий (11 коммитов 25-29.08, одним autopilot-прогоном PA-49), но после 26.08 продуктовых правок нет, данных нет, auth не подключён.
- Рекомендация: доделывать - путь до M-03 (D6) = подмена одного провайдера `getBrief()` в уже спроектированном `/brief`. Решение за Mike (§9).

## 2. Стек и структура

Версии - `services/webapp/package.json` (30.08.2026): next 16.3.3, react/react-dom 19.2.8, typescript 5.8.3, tailwindcss + @tailwindcss/postcss 4.3.3, vitest 4.1.11, eslint 9.39.5 (пин, deprecated-warning при `npm ci`), better-auth 1.7.1, drizzle-orm 0.45.2, pg 8.16.3, next-themes 0.4.6, lucide-react 1.34.0.

Workspace: корневой `package.json` объявляет `workspaces: [services/collector, services/webapp]`, lock один в корне; `engines: node >=22 <23`. Локальный Node v22.23.2 / npm 10.9.8 - подходит.

`src/` = App Router (`find services/webapp/src -type f`, 50 файлов):

- `app/layout.tsx` - шрифты Inter + IBM Plex Mono, ThemeProvider; `app/page.tsx` - redirect на `/brief`.
- `app/(app)/layout.tsx` - защищённый шелл: auth-гейт (строка 18), `UnreleasedBanner`, сайдбар, `MetricStrip`.
- `app/(app)/{brief,dashboard,inbox,admin,styleguide}/page.tsx` - 5 экранов; `app/login/page.tsx`; `app/api/auth/[...all]/route.ts`.
- `components/{ui,metrics,brief,shell,empty}/` - 23 компонента; `lib/{auth,auth-client,fx,gyr,utils}.ts`, `lib/db/{client,schema.auth}.ts`, `lib/fixtures/{brief,metrics,shell}.ts`, `lib/format/rub.ts`.
- `tests/` - 5 файлов vitest (только чистые функции и fixtures-геттеры, DOM не тестируется).
- Конфиги: `next.config.ts` (`output: "standalone"`), `vitest.config.ts` (environment node, include `src/tests/**`), `Dockerfile` (3-stage, node:22-bookworm-slim, `PUPPETEER_SKIP_DOWNLOAD=1`), `eslint.config.mjs`, `tsconfig.json` (strict).
- Каталога `drizzle/` с миграциями webapp_auth, упомянутого в `services/webapp/README.md:56`, в дереве нет (`ls -la services/webapp`, 30.08).

## 3. Что показывает (экраны и маршруты)

Маршруты по `next build` 30.08.2026: `/` (static), `/_not-found`, `/admin`, `/api/auth/[...all]` (dynamic), `/brief` (dynamic), `/dashboard`, `/inbox`, `/login`, `/styleguide`.

| Маршрут | Что на экране (по коду) | Данные |
|---|---|---|
| `/` | `redirect("/brief")` | - |
| `/brief` | `BriefVerdict` (дата mono, «N критичных / M внимания» или «Критичных нет»), список `SignalRow` (GYR-полоса, заголовок, причина, «стоимость молчания» ₽/день), `Digest` (2-3 пункта). `?view=quiet` = тихий день | `getBrief(variant)` из `lib/fixtures/brief.ts` |
| `/dashboard` | `EmptyState` «Дашборд оживёт в PA-52» + 3 `FutureBlock` (выручка/заказы 7-28-90 дн, здоровье по SKU, пути до источника) | нет |
| `/inbox` | `EmptyState` «Очередь решений пока пуста» (PA-51) + `InboxWorkflow` + `KeyboardHint` | нет |
| `/admin` | 6 `AdminModuleStub` («оживёт в PA-54») | нет |
| `/styleguide` | живой стайлгайд: токены обеих тем, типографика, примитивы, GYR, ₽-форматы | `getMetrics()` |
| `/login` | форма email/пароль через `authClient.signIn.email`, успех → `/brief` | Better Auth |

Общий шелл `(app)/layout.tsx`: плашка `unreleased · fixtures (DEC-006)`, сайдбар 256px (Ежедневное: Бриф, Inbox; Аналитика: Дашборд; Система: Админ, Стайлгайд), `MetricStrip` на каждом экране - 5 карточек (Сигналы, Выручка/день, Заказы/день, OOS-риски, Свежесть данных) со спарклайнами и бейджем «FX», `CabinetSwitcher` с одним fixture-кабинетом. Каждая секция в `SectionErrorBoundary`.

## 4. Откуда данные

- **Fixtures - единственный источник.** `lib/fixtures/metrics.ts` (`getMetrics.dataMode = "fixtures"`), `lib/fixtures/brief.ts` (`getBrief`, `dataMode: "fixtures"`), `lib/fixtures/shell.ts` (`FIXTURE_CABINETS`, счётчики). Значения обезличены, префикс `fixture-`.
- **API routes:** только `app/api/auth/[...all]/route.ts` - обёртка `better-auth/next-js` над `getAuth().handler`. Других API нет; `grep -rn 'fetch(' src` - 0 совпадений (30.08).
- **Postgres:** `lib/db/client.ts` - drizzle + `pg.Pool`, два ленивых соединения: `getAuthDb()` (`WEBAPP_AUTH_DATABASE_URI`, схема `webapp_auth` из `schema.auth.ts`) и `getDataDb()` / `hasDataDb()` (`WEBAPP_DATA_DATABASE_URI` ?? `DATABASE_URI`). `getAuthDb` используется только в `lib/auth.ts:17`; `getDataDb`/`hasDataDb` не вызываются нигде (`grep -rn getDataDb src`, 30.08). Drizzle-схемы доменных таблиц нет.
- **Collector / control-plane:** обращений нет.
- **Auth-гейт:** `(app)/layout.tsx:18-24` при `WEBAPP_REQUIRE_AUTH=true` проверяет только наличие cookie `better-auth.session_token`, без серверной валидации сессии (комментарий в коде: «вместе с БД-ролью webapp_auth_writer»).
- **Env** (`grep -rhoE 'process\.env\.[A-Z_]+' src | sort -u`, 30.08): `DATABASE_URI`, `WEBAPP_DATA_DATABASE_URI`, `WEBAPP_REQUIRE_AUTH`. Плюс через `process.env[name]` в `requiredEnv`: `WEBAPP_AUTH_DATABASE_URI` (`client.ts:33`). Better Auth сам читает `BETTER_AUTH_SECRET` / `BETTER_AUTH_URL` (README, `infra/webapp.compose.yaml`). Расхождение: `AGENTS.md` (раздел T2) называет `AUTH_SECRET` / `AUTH_DATABASE_URI` - в коде таких имён нет.
- Ролей `webapp_auth_writer` / `webapp_readonly` в `db/migrations/*.sql` нет (`grep -i webapp db/migrations/009_runtime_roles.sql` - пусто, 30.08).

## 5. Сборка и тесты - прогон 30.08.2026 (локально, Node v22.23.2)

Предварительно: `git check-ignore -v services/webapp/node_modules/ services/webapp/.next/` → `.gitignore:9` и `:10` (без trailing slash check-ignore даёт exit 1 - паттерны каталожные).

| Шаг | Команда | Результат | Время |
|---|---|---|---|
| install | `PUPPETEER_SKIP_DOWNLOAD=1 npm ci` (корень, workspace) | `added 652 packages`; warn `eslint@9.39.5 no longer supported` | 28с |
| build | `npm --workspace @proxima/webapp run build` | exit 0; `Compiled successfully in 4.5s`, TypeScript 2.1s, 9/9 static pages | 10с |
| test | `npm --workspace @proxima/webapp test` | exit 0; `Test Files 5 passed (5)`, `Tests 26 passed (26)`, Duration 212ms | 2с |
| lint | `npm --workspace @proxima/webapp run lint` | exit 0, вывода нет (0 warnings) | 2с |
| tsc | `npm --workspace @proxima/webapp run typecheck` | exit 0 | 2с |

Побочный эффект: `next build` переписывает tracked-файл `next-env.d.ts` (`./.next/dev/types/` → `./.next/types/`), в git появляется diff - откатил `git checkout -- services/webapp/next-env.d.ts`. Tracked-версия сгенерирована `next dev`; кто последний запустил dev/build, тот и «победил» - кандидат в бэклог (либо в .gitignore, либо фиксировать build-вариант). Ничего не коммитил, исходники не менял; `node_modules/` и `.next/` остались локально (gitignored).

## 6. Живая или заброшена - git (30.08.2026)

`git log --format='%h %ad %an %s' --date=short -- services/webapp`: 11 коммитов всего, все за 25-29.08.2026, автор Mike Zhamba (autopilot PA-49):

```
8d0932e 2026-08-29 chore: agent configs snapshot (codex, opencode, MEMORY, next-env)
154d5c4 2026-08-26 fix(webapp): доводка P3 - хоткеи подписаны как будущие PA-51
c142dff 2026-08-26 fix(webapp): доводка P2 - блок дельты скрывается без данных
b06af80 2026-08-26 fix(webapp): доводка P1 - FX на дайджесте, chevron только у действий
0077648 2026-08-26 feat(webapp): т07 - staging на VPS за туннелем + фикс Dockerfile
bae976c 2026-08-26 feat(webapp): т05 - стайлгайд Warm Precision
8ae0f44 2026-08-26 feat(webapp): т04 - скелеты inbox/dashboard/admin + boundaries
0fcf117 2026-08-26 feat(webapp): т03 - бриф как редакционный экран
acced0c 2026-08-26 feat(webapp): т02 - сайдбар + метрическая полоса
0dbfa71 2026-08-25 feat(webapp): т01 - токены Warm Precision, примитивы
93f0db1 2026-08-25 feat(webapp): каркас Next.js 16 + Better Auth, деплой-контур
```

- Первый коммит 25.08.2026, последний содержательный 26.08.2026 (`154d5c4`), последний вообще 29.08 (снапшот конфигов). За 30 дней - 11 (= все).
- TODO/FIXME в `src`: 0. Ветка `feat/pa-49-warm-precision` слита в main (`git branch -a --contains bae976c` включает `main`).
- Итог: не заброшена (4 дня от роду), но и не развивается после сдачи PA-49; следующие шаги (PA-50 живые данные, PA-51 inbox, PA-52 дашборд, PA-54 админ) - только в заглушках и Jira. `.autopilot/2026-08-25-pa49-warm-precision/manifest.md`: 20 строк done, R16 (доводка) deferred в PA-50.

## 7. На сервере (30.08.2026, `ssh proxima`, только чтение)

- `sudo ss -tlnp | grep :3000` → `127.0.0.1:3000`, процесс `docker-proxy` pid 1878 (cwd `/`, `-container-ip 172.17.0.2`). Внутри: pid 1704 `next-server (v16.3.3)`, cwd `/app/services/webapp`, uid 1001 (в контейнере `webapp`, на хосте отображается как `proxima-monitor`).
- Контейнер `proxima-webapp-staging`, образ `proxima-webapp-staging:bae976c` (= `:latest`, собран 26.08 03:59 UTC, 424 MB, amd64), `Cmd: node services/webapp/server.js`, mounts нет, `restart: unless-stopped`, RestartCount 0, OOM false, RAM 112 MiB. Env (имена): `WEBAPP_REQUIRE_AUTH`, `NODE_ENV`, `PORT`, `HOSTNAME`, `NEXT_TELEMETRY_DISABLED` + node-базовые. Нет `BETTER_AUTH_*` и `*_DATABASE_URI` - fixtures-режим.
- Кем поднят: не compose (labels пустые) и не systemd (`systemctl list-units | grep -i webapp` - пусто). Ручной `docker run` по ранбуку `services/webapp/README.md:42-49`. Хост перезагружался 30.08 04:45 и 04:55 UTC (`last -x reboot`), контейнер поднялся сам через `unless-stopped` в 04:55.
- Ответы: `/` → 307 на `/brief`; `/brief`, `/dashboard`, `/login`, `/styleguide` → 200 (в `/brief` `<title>Бриф · Proxima AI</title>`); `/api/auth/get-session` → 500 (нет `WEBAPP_AUTH_DATABASE_URI`, `requiredEnv` бросает - ожидаемо для fixtures-режима).
- Чекаут `~/proxima-webapp-staging/repo`: detached HEAD `bae976c` (26.08 06:45 +03), remote `origin = /tmp/pa49-head.bundle`, untracked `services/webapp/Dockerfile.staging` (= Dockerfile + строка `ENV PUPPETEER_SKIP_DOWNLOAD=1 PUPPETEER_SKIP_CHROMIUM_DOWNLOAD=1` после строки 8). Ветки PA-49 как таковой нет - это бандл одного коммита из `feat/pa-49-warm-precision`.
- Расхождение staging vs main (`diff -rq --exclude=node_modules --exclude=.next ~/proxima-ai/services/webapp ~/proxima-webapp-staging/repo/services/webapp`): 8 файлов отличаются (`Dockerfile`, `README.md`, `next-env.d.ts`, `brief-verdict.tsx`, `digest.tsx`, `signal-row.tsx`, `keyboard-hint.tsx`, `metric-card.tsx`) + `Dockerfile.staging` только в staging. Направление: **staging отстаёт** - в main есть 5 webapp-коммитов после `bae976c` (`0077648`, `b06af80`, `c142dff`, `154d5c4`, `8d0932e`); staging-уникальных правок кода нет.
- `~/proxima-ai` = main `db56429`, чистый. `/srv/proxima-ai/repo` @ `fd95fcb` (25.08) - каталога `services/webapp` там нет вовсе. Прод-оверлей `infra/webapp.compose.yaml` (Caddy, 80/443, `WEBAPP_REQUIRE_AUTH=true`) не применён: контейнера caddy нет.
- Мусор: контейнер `hopeful_gates` (Exited 1, 26.08 03:53) - упавший промежуточный слой `npm ci` первой сборки (проблема D01 puppeteer). Не трогал.

## 8. Точка встраивания утренней сводки (D6, M-03)

Экран уже есть: `services/webapp/src/app/(app)/brief/page.tsx` рендерит `BriefVerdict` → `SignalRow[]` → `Digest` из `getBrief()` (`src/lib/fixtures/brief.ts`); это и есть «утренняя сводка» по замыслу PA-49. Тип `BriefSignal` (id, GYR-статус, title, cause, costEstimate) под «отклонение против обычного вторника» надо расширить полями metric, actual, baseline, deltaPercent, window, sourceRef; ближайшая по форме модель уже лежит в `src/lib/fixtures/metrics.ts` (`FixtureMetric.deltaPercent` / `deltaGoodWhen` / `points`) и рендерится `components/metrics/metric-card.tsx`. Слой данных подготовлен, но пуст: `getDataDb()` / `hasDataDb()` в `src/lib/db/client.ts:42-55` (роль `webapp_readonly`) - нужен серверный loader, который заменит `getBrief` при `hasDataDb()` и переключит `UnreleasedBanner` на `dataMode="staging"`. Сама сводка (норма, отклонение) по AGENTS.md считается детерминированным кодом вне UI - в БД сейчас только сырьё (`fact_order_counts`: tenant_id, nm_id, calendar_day, order_count; `business_signal_runs`), таблицы/вью «сводка дня» нет - её даёт M-02/M-03 на стороне collector/control-plane. Для staging потребуется `WEBAPP_DATA_DATABASE_URI` в контейнере (сейчас отсутствует) и роль `webapp_readonly` в миграциях (сейчас нет).

## 9. Доделывать vs переписывать (решение за заказчиком)

**ЗА доделку**

1. Всё зелёное на 30.08: build 10с, 26/26 тестов, lint 0, tsc 0, 0 TODO; стек свежий, 2401 LOC - обозримо.
2. `/brief` уже спроектирован именно под сводку (вердикт, critical-строки с ₽-оценкой, дайджест, тихий день), принят слепой приёмкой G4 16/18 и канонизирован в `DESIGN.md` + `/styleguide` - дизайн-решения повторно принимать не надо.
3. Швы под данные предусмотрены: fixtures-геттеры как единая точка подмены, `getDataDb`/`hasDataDb`, роли и env описаны в README, standalone-Dockerfile и staging-ранбук работают (контейнер отвечает 200).
4. Плашка unreleased/FX и `SectionErrorBoundary` уже дают честный режим «данные частично» - можно показывать сводку с первого дня M-03 без риска выдать fixture за факт.

**ЗА переписывание**

1. Auth-контур - незавершённый полуфабрикат: гейт по наличию cookie без валидации, `/api/auth` → 500, миграций `webapp_auth` и ролей в `db/` нет, имена env расходятся между кодом, README и AGENTS.md.
2. 3 из 4 продуктовых экранов - заглушки, 100% данных fixtures, `MetricStrip` грузит fixtures в шелле на каждом экране; фактическая ценность на 30.08 - ноль, терять нечего.
3. Стек тяжелее задачи: Next 16 + Better Auth + Drizzle + образ 424 MB ради одного экрана для одного пользователя за SSH-туннелем; расчёты всё равно живут в Python control-plane - сводку можно рендерить оттуда (HTML/Telegram) без Node-слоя.
4. Деплой ручной (bundle → `docker run`), staging уже отстал от main на 5 коммитов, в `make verify` для webapp только typecheck+test, без build и без CI - контур придётся достраивать в любом случае.

**Объём** (единица = сеанс агента + один PR):

- Доделка до M-03: (а) контракт «сводка дня» + таблица/вью в БД на стороне control-plane - 1; (б) loader через `getDataDb` + read-only drizzle-схема + расширение `BriefSignal` + `dataMode="staging"` - 1; (в) env/роль `webapp_readonly` + пересборка staging из main + деплой по OK Mike - 1. Auth остаётся `WEBAPP_REQUIRE_AUTH=false` за туннелем до октября. Итого **3**.
- Переписывание (минимальный серверный рендер из control-plane): (а) шаблон + рендер сводки - 1; (б) контейнер/порт/туннель/деплой - 1; (в) перенос токенов/стайлгайда или отказ от них - 0.5-1; плюс тот же пункт (а) из доделки (контракт сводки) - 1. Итого **3.5-4**, при этом PA-49 (11 коммитов, приёмка) списывается.

**Рекомендация:** доделывать. Главный довод: до M-03 через существующий `/brief` - это замена одного провайдера данных при зелёном verify, а переписывание тратит те же 3-4 единицы на воссоздание уже принятого экрана и не снимает ни одного пункта «против» (контракт сводки и деплой-контур нужны в обоих вариантах). Условия: auth не трогать до октября, staging пересобрать из main перед первым живым запуском, `next-env.d.ts` и env-имена - строкой в бэклог.
