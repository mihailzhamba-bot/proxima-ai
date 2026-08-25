# PA-49 — Web-кабинет v0 (1/5): каркас webapp

> Living plan. Сессия 1 (2026-08-25, opencode/build): код-каркас. Сессия 2: деплой на VPS + auth-контур.
> Источник решений: интервью Mike 2026-08-25 (грилл фронтенда) + PA-38..PA-55.

## Решения (фикс)

- Стек: Next.js 16.3 (App Router, standalone) + Better Auth 1.7 + Tailwind 4 + Drizzle + shadcn-подобные примитивы. Self-hosted Docker на VPS за Caddy (auto-HTTPS).
- Публичный URL + полный auth (PA-55 фиксирует откат SSH-туннель-only).
- Данные: fixtures-first (DEC-006: unreleased на всех экранах).
- Две темы (light/dark), GYR-токены, ₽-формат, русский UI.
- UI не считает метрики; БД-роли: webapp_auth_writer (только схема webapp_auth) и webapp_readonly (чтение).

## Сессия 1 — сделано (2026-08-25)

- `services/webapp` в npm workspace `@proxima/webapp`; Node >=22 <23 как весь репо.
- Каркас: root layout (ru, next-themes), login-страница, Better Auth lazy (не требует БД на build/test), auth API-роут, шелл (сайдбар 5 разделов + топбар GYR-счётчики fixtures + переключатель кабинета + плашка unreleased/DEC-006).
- Скелеты модулей: /brief (PA-50), /inbox (PA-51), /dashboard (PA-52), /admin (PA-54); стайлгайд `/styleguide` (палитра, GYR, ₽-формат, кнопки) — критерий приёмки №5.
- Ленивые Drizzle-клиенты: `getAuthDb()` / `getDataDb()` (env-driven, без коннекта на import); схема `webapp_auth` (user/session/account/verification) — миграции webapp отдельны от M1-ледаря.
- Тесты: vitest, 11 unit (gyr-маппинг, ₽-форматтеры). Линт: eslint-config-next 16 flat (eslint пин 9.39.5 — plugin-react не поддерживает eslint 10).
- Инфра: `services/webapp/Dockerfile` (multi-stage standalone), `infra/webapp.compose.yaml` (overlay: webapp + caddy, основной compose.yaml не тронут — boundary-гейт читает его построчно), `infra/Caddyfile` (домен через env, security-заголовки).
- Makefile: typecheck/test расширены webapp-нодами; цели `webapp-lint`, `webapp-build`.
- `.gitignore` + `**/.next/` (secret_scan ловил sourcemap-артефакты).
- Verify: `make verify` PASS целиком (включая npm ci по обновлённому lock); smoke standalone: `/`→307→`/brief`, `/brief` рендерит unreleased-плашку, `/styleguide` 200, `/login` 200.

## Сессия 2 — осталось (деплой + auth)

1. Mike: домен + A-запись `app.<домен>` → 135.106.186.210; подтверждение открытия 80/443 в firewall Selectel.
2. VPS: схема `webapp_auth` + роли `webapp_auth_writer` / `webapp_readonly` (additive-only, отдельно от M1-ледаря); секреты в `/etc/proxima-ai/secrets/` + path-only `.env`.
3. Сборка образа на VPS (локального Docker нет), overlay `docker compose -f compose.yaml -f webapp.compose.yaml up -d webapp caddy`.
4. Первый пользователь (Mike) через better-auth CLI/API; `WEBAPP_REQUIRE_AUTH=true`; серверная валидация сессии в (app)-layout через `auth.api.getSession` (сейчас cookie-presence — слабый режим для деплоя).
5. Проверка: https://app.<домен> логин, темы, скелеты; закрыть критерии приёмки 2-3 PA-49.
6. Telegram-заметка: связка с PA-53 (утренняя ссылка) после PA-50.

## Критерии приёмки PA-49 → статус

1. `make verify` зелёный с webapp — DONE (2026-08-25)
2. UI по https://app.<домен>, логин, темы — сессия 2
3. Postgres через read-only роль (мутаций нет) — код готов (роли на VPS), проверка в сессию 2
4. Скелеты разделов — DONE
5. Стайлгайд с токенами — DONE (`/styleguide`)
