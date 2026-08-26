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

## Staging (VPS через туннель)

Кабинет доступен с любой машины Mike через SSH-туннель; публичные порты не открываются.

Посмотреть:

```bash
ssh -N proxima-app        # держать открытым (LocalForward 3000)
# → http://localhost:3000
```

Контейнер `proxima-webapp-staging` на VPS: порт опубликован только на `127.0.0.1:3000`, `restart: unless-stopped`, `WEBAPP_REQUIRE_AUTH=false` (fixtures, без БД и секретов). Checkout - `~/proxima-webapp-staging/repo` (detached, из git bundle - паттерн PA-13); основной compose-стек VPS не затрагивается.

Обновить на новый коммит (с машины разработки):

```bash
git bundle create /tmp/pa49-head.bundle HEAD
scp /tmp/pa49-head.bundle proxima:/tmp/
ssh proxima 'cd ~/proxima-webapp-staging/repo && git fetch -q /tmp/pa49-head.bundle HEAD && git checkout -q FETCH_HEAD \
  && sudo docker build -f services/webapp/Dockerfile.staging -t proxima-webapp-staging:latest . \
  && sudo docker rm -f proxima-webapp-staging \
  && sudo docker run -d --name proxima-webapp-staging --restart unless-stopped \
       -p 127.0.0.1:3000:3000 -e WEBAPP_REQUIRE_AUTH=false proxima-webapp-staging:latest'
```

`Dockerfile.staging` - дериват `services/webapp/Dockerfile` с одной строкой `ENV PUPPETEER_SKIP_DOWNLOAD=1` (postinstall puppeteer от root-devDep mermaid-cli падает в slim-образе без unzip; живёт только в staging-каталоге VPS).

## Границы

- Миграции webapp - в собственном контуре (`drizzle/`), M1-ледарь `db/` не затрагивается; additive-only (DEC B6).
- Единственные мутации UI - решения AM (отдельная роль, приходит с PA-51).
- Deploy: `infra/webapp.compose.yaml` (overlay поверх основного стека) + `infra/Caddyfile`; порты 80/443 открываются только с подтверждения Mike.
