# @proxima/webapp

Внутренний веб-кабинет Proxima (Трек B, PA-38/PA-49). Стек: Next.js 16 (App Router) + Better Auth + Tailwind 4 + Drizzle. UI только рендерит факты и сигналы; метрики считает детерминированный код (AGENTS.md). Пометка `unreleased` на всех экранах, пока M1 release pointer не двигается (DEC-006).

## Команды

```bash
npm --workspace @proxima/webapp run dev        # локальная разработка (fixtures, без БД)
npm --workspace @proxima/webapp run typecheck
npm --workspace @proxima/webapp test           # vitest (unit, без БД)
npm --workspace @proxima/webapp run lint
make webapp-build                              # продакшн-сборка
```

## Переменные окружения

Реальные значения живут на VPS (`/etc/proxima-ai/secrets/` + path-only `.env`); в Git их нет.

| Переменная | Назначение |
|---|---|
| `WEBAPP_REQUIRE_AUTH` | `true` в проде: без сессионной cookie - редирект на /login. Локально `false` (fixtures-режим) |
| `BETTER_AUTH_SECRET` | Секрет подписи сессий Better Auth |
| `BETTER_AUTH_URL` | Публичный URL (`https://app.<домен>`) |
| `WEBAPP_AUTH_DATABASE_URI` | Роль `webapp_auth_writer`: пишет только в схему `webapp_auth` |
| `WEBAPP_DATA_DATABASE_URI` | Роль `webapp_readonly`: чтение доменных данных, мутации запрещены ролью |

## Границы

- Миграции webapp - в собственном контуре (`drizzle/`), M1-ледарь `db/` не затрагивается; additive-only (DEC B6).
- Единственные мутации UI - решения AM (отдельная роль, приходит с PA-51).
- Deploy: `infra/webapp.compose.yaml` (overlay поверх основного стека) + `infra/Caddyfile`; порты 80/443 открываются только с подтверждения Mike.
