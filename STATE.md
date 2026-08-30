# STATE

Память между сессиями. Первое действие каждой сессии - прочитать этот файл и подтвердить заказчику, что подхватил верно.

**Обновлено:** 30.08.2026, конец прожарки промта (сессия 0).
**Следующая сессия:** 1a.

## Что сделано

- Промт «полный цикл разработки поверх BMAD» прожарен с Mike: 10 решений + 5 допущений → `DECISIONS.md`.
- Read-only разведка сервера `135.106.186.210` (ssh-алиас `proxima`, user `proxima-admin`, sudo NOPASSWD, наружу только tcp/22):
  - `~/proxima-ai` - main @ `db56429` (29.08), чистый, remote GitHub.
  - `/srv/proxima-ai/repo` - @ `fd95fcb` (25.08), отстаёт от main.
  - `~/proxima-webapp-staging/repo` - @ `bae976c` (26.08, ветка PA-49), remote = `/tmp/pa49-head.bundle`.
  - OpenHands workspace `/srv/openhands/persistence/workspace/project/<uuid>` (юзер `openhands-agent`).
  - Loopback-порты: 5432 Postgres (в контейнере, `psql` на хосте нет), 3000 (веб-морда?), 3001/8000/18000/18001 OpenHands, 8080 GlitchTip, 1080/1081 egress-туннель.
  - Таймер `proxima-host-monitor.timer` (раз в минуту). Crontab `proxima-admin` пуст.
  - Секреты вне git: `~/signal-inputs/{wb_analytics_token,telegram_bot_token}`, `/etc/proxima-ai/secrets/*` (по README).
- Локально: архив `~/Desktop/MILV/03-startups/!Proxima/PROXIMA AI (архив - работа на VPS)` на ветке `feat/pa-49-warm-precision` @ `8dfa101` (29.08), полностью запушен. Handoff от 14.08 - `~/Desktop/Проекты/Proxima/proxima-ai-handoff-2026-08-14.md`.
- Свежий клон `~/Desktop/Проекты/Proxima/proxima-ai/`, ветка `docs/session-1-inventory` от `db56429`.

## Что решено

См. `DECISIONS.md` D1-D10, A1-A5. Коротко: лестница M-00..M-05 вместо M1; цель 30.09 = M-03; истина = GitHub main; токены на сервере, API с сервера; Jira через remote MCP, scope PA + PMM, только чтение; Mike мержит и принимает, Claude запускает OpenHands и деплоит по разовому OK; один VPS, `proxima_test` для тест-запусков; Сессия 1 = 1a + 1b.

## Что открыто

- Глубина истории WB API (приоритет 1.1) - неизвестна, от неё зависит реалистичность сентября.
- Ключ Jira-проекта PMM - проверить при подключении MCP.
- Кто держит порт 3000 на сервере и живая ли веб-морда.
- Что из «48 py + 43 TS тестов» (handoff 14.08) сейчас в дереве - в клоне продуктовых тестов не видно.
- Открытые вопросы брифинга (Сессия 2) - список в конце `DECISIONS.md`.

## Где остановился

Сессия 0 закончена на коммите `DECISIONS.md` + `STATE.md` в ветке `docs/session-1-inventory`. Код продукта не писался, сервер не менялся.

## С чего начинать Сессию 1a

1. Прочитать этот файл, подтвердить Mike в одном абзаце.
2. Jira MCP `jira-atlassian` уже добавлен в user-scope Claude Code (30.08, статус «Needs authentication»). Осталось: `/mcp` → авторизоваться в браузере → проверить проекты PA и PMM. Откат: `claude mcp remove jira-atlassian -s user`.
3. Токен Амировой на сервер: sha256-сравнение с существующими → dry-run в чат → OK Mike → `scp` в `~/signal-inputs/amirova_wb_token` (0600). Откат: `ssh proxima 'rm ~/signal-inputs/amirova_wb_token'`.
4. Разведка API с сервера (read-эндпоинты Statistics/Analytics), ответы в фикстуры → `docs/state/API-FACTS.md`.
5. Сервер (1.2) под sudo только чтением → черновик `docs/state/INVENTORY.md`.
6. Веб-морда `services/webapp` → `docs/state/WEB-STATE.md`.
7. Обновить `STATE.md`, push, PR.

Правила: сервер только чтение (единственное исключение - п.3); секреты не выводить; ничего не чинить - строкой в бэклог; в Jira не писать до Ворот 2.
