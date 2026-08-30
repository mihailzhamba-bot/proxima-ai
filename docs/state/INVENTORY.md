# INVENTORY - сервер 135.106.186.210 (claudette)

**Дата:** 30.08.2026, 05:55-06:10 UTC. **Статус:** черновик Сессии 1a, часть «сервер» (Этап 1.2).
**Метод:** только чтение по `ssh -o BatchMode=yes proxima '<cmd>'` под `sudo`. Секреты не читались: для них путь/mode/owner/size/дата и sha256 (A3). Роль Postgres из `/run/secrets/postgres_user` в выводе заменена на `<pg_user>`.
**Не покрыто:** локальный архив и GitHub-ветки (Сессия 1b), содержимое OpenHands `settings.json`/`secrets.json`, содержимое `.env`-файлов (только имена переменных).

## 1. Таблица компонентов

| # | Компонент | Где | Вердикт | Чем подтверждено (30.08.2026) |
|---|---|---|---|---|
| 1 | Postgres пилота `proxima-ai-postgres-1` (postgres:16.10-alpine) | compose `/srv/proxima-ai/repo/infra/compose.yaml`, volume `proxima-ai_postgres-data`, 127.0.0.1:5432 | работает | `sudo docker ps`, `docker inspect`, `ss -tlnp`; healthy, up с 04:55 UTC |
| 2 | База `proxima` (13 таблиц, ledger 6 миграций) | в №1 | работает, данные заморожены с 25.08 | `psql -d proxima` (см. Прил. d) |
| 3 | База `proxima_dev` на хосте | в №1 | не понял: 0 таблиц | `psql -d proxima_dev`: `pg_stat_user_tables` пусто |
| 4 | Веб-морда `proxima-webapp-staging` (Next.js 16.3.3, образ `bae976c`) | docker run без compose, 127.0.0.1:3000 | работает в fixtures-режиме, auth выключен | `curl 127.0.0.1:3000/brief` → 200, `docker inspect`: `WEBAPP_REQUIRE_AUTH=false`, Labels пусто |
| 5 | GlitchTip 6.2.6 (web+worker+postgres+redis) | compose `/srv/proxima-ai/glitchtip/docker-compose.yaml`, 127.0.0.1:8080 | работает; 1 org, 1 project `webapp`, 1 issue (28.08) | `curl 127.0.0.1:8080/_health/` → `ok`; `psql -U glitchtip` counts |
| 6 | OpenHands agent-canvas 1.16.0 (user `openhands-agent`, UID 1002) | user-unit `agent-canvas.service`; 127.0.0.1:8000 ingress, :3001 static, :18000 agent-server 1.44.0, :18001 automation 1.9.0 | работает | `sudo -u openhands-agent XDG_RUNTIME_DIR=/run/user/1002 systemctl --user list-units`; `curl :8000` → 200 |
| 7 | Rootless Docker зоны + контейнер `proxima-dev` (postgres:16-alpine = 16.15) | user-unit `docker-rootless.service`, `/srv/openhands/rootless-docker` | работает; база `proxima_dev` пуста (0 таблиц) | `DOCKER_HOST=unix:///run/user/1002/docker.sock docker ps`; `psql -d proxima_dev` |
| 8 | Egress-туннель `dutch-tunnel` (autossh SOCKS 127.0.0.1:1080 → root@153.56.134.240:65022) + `privoxy` 127.0.0.1:1081 | system units | работает | `systemctl list-units`, `ss -tlnp`, `/etc/privoxy/config`: `forward-socks5t / 127.0.0.1:1080` |
| 9 | Reverse-туннель `openhands-ingress-tunnel` (127.0.0.1:8000 VPS → 127.0.0.1:8000 на 153.56.134.240) | system unit | работает | `systemctl cat`, `ps -p 696` |
| 10 | `proxima-host-monitor.timer` (раз в минуту, user `proxima-monitor`) | `/etc/systemd/system/proxima-host-monitor.*`, `/usr/local/lib/proxima-ai/host_monitor.py` | работает | `systemctl list-timers`; `state.json` обновлён 05:57 UTC, `active: {}` |
| 11 | Ночной бэкап `proxima-pg-backup.sh` (03:00, root) | `/etc/cron.d/proxima-pg-backup`, `/var/backups/proxima`, age → S3 `proxima-backups` | работает | `/var/log/proxima-backup.log`: 30.08 03:00 OK local+s3 для `proxima` (64K) и `proxima_dev` (4K) |
| 12 | Zone-check `openhands-zone-check.sh` (*/5 мин, root, алерты в Telegram) | `/etc/cron.d/openhands-zone-check`, `/var/log/openhands-zone.log` | работает; 7 ALERT в истории (все 29.08) | `sudo tail /var/log/openhands-zone.log`: `ok: svc-up disk=19% zone-mem=1343M containers=1` |
| 13 | Чекаут `~/proxima-ai` | `/home/proxima-admin/proxima-ai`, main @ `db56429` (29.08) | работает как зеркало main; toolchain для `make verify` нет | `git status --short` = 0, `origin/main..HEAD` пусто; `node_modules`/`.venv` отсутствуют, `uv` не установлен |
| 14 | Чекаут `/srv/proxima-ai/repo` | detached @ `fd95fcb` (25.08), remote отсутствует, ветка `pa30-stage` | полуготово: рабочий источник compose и initdb-миграций, отстал от main | `git remote -v` пусто; `db/migrations` = 001-006 vs 001-010 в main |
| 15 | Чекаут `~/proxima-webapp-staging/repo` | detached @ `bae976c` (26.08, PA-49), remote = `/tmp/pa49-head.bundle` | полуготово: источник образа №4, remote мёртв | `ls /tmp/pa49-head.bundle` → нет; `?? services/webapp/Dockerfile.staging` |
| 16 | OpenHands workspace `26fa6b87…` | `/srv/openhands/persistence/workspace/project/26fa…`, ветка `ai/pa-50` @ `d8c912c` (29.08 19:07 UTC) | полуготово: 4 коммита, которых нет в GitHub | `git log main..HEAD` = 4; `git ls-remote origin` (с мака) не содержит `ai/pa-50` |
| 17 | OpenHands task-репо `tasks/pa-50`, `tasks/acceptance-migration-docs` | `/srv/openhands/workspaces/proxima-ai/tasks/*` | работает (pa-50 = main `db56429`; acceptance = `ad89513`, смержен PR #33) | `sudo -u openhands-agent git log/status`; `?? .openhands/SECURITY-POLICY.md` в обоих |
| 18 | 11 пустых OpenHands workspace (`master`, 0 коммитов, только `.git` [+ симлинк `_bmad`]) | `/srv/openhands/persistence/workspace/project/*` | мёртвое/мусор | `git log -1` → «does not have any commits yet» |
| 19 | Контейнер `hopeful_gates` (exit 1, `npm ci --workspace @proxima/webapp`) | docker, создан 26.08 03:53 | мёртвое | `docker inspect hopeful_gates` |
| 20 | Caddy / nginx / traefik | `/etc/nginx`, `/etc/caddy`, `dpkg -l` | отсутствуют; `infra/Caddyfile`, `infra/webapp.compose.yaml` из main не развёрнуты | `ls /etc/nginx /etc/caddy` → нет; `docker ps` без caddy |
| 21 | `wb-probe-venv` (Day 1 probe) | `/srv/proxima-ai/wb-probe-venv`, root, 41M, 13.08 | не понял: живой ли (данных в `data/day1-wb-api` нет) | `du -sh`, `ls data/day1-wb-api` пусто |
| 22 | Secrets `/etc/proxima-ai/secrets/` (21 файл) и `~/signal-inputs/` (13 файлов) | см. Прил. i | работает; расхождения см. §4 | `ls -la --time-style=long-iso`, `sha256sum` |
| 23 | `~/.orca-remote/relay-0.1.0+1f3529d59e03/` (relay.js, hook-runtime; 29.08 17:27) | home proxima-admin | не понял: процессов/юнитов нет | `ls`, `ps -eo cmd \| grep -i relay` пусто |
| 24 | `~/.git-credentials` (0600, 130 B, 29.08 17:00) | home proxima-admin | работает (для push из OpenHands-задач?) - см. §4 | `find -name .git-credentials` |

## 2. Что можно пощупать прямо сейчас

- Веб-морда: `ssh -N proxima-app` (LocalForward 3000) → http://localhost:3000/brief. Проверка на сервере: `curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:3000/brief` → 200; `/login /brief /dashboard /inbox /admin /styleguide` все 200, плашка unreleased на каждой, `fixture-*` id на /brief (4) и /styleguide (2).
- GlitchTip: `curl -s http://127.0.0.1:8080/_health/` → `ok`. UI - через `ssh -N proxima-errors` (LocalForward 18080, по комментарию в compose). Данные: 1 проект `webapp` (javascript-nextjs), 1 issue, 1 event (партиция `issue_events_issueevent_20260828_h0`).
- OpenHands UI: `curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8000/` → 200; с мака через туннель `proxima-openhands` (D7). API automation :18001 отвечает 404 на `/` (жив).
- Postgres пилота: `sudo docker exec proxima-ai-postgres-1 sh -c 'psql -U "$(cat /run/secrets/postgres_user)" -d proxima -c "\dt"'` → 13 таблиц. `psql` на хосте нет.
- Бэкап: `sudo tail -4 /var/log/proxima-backup.log`; `sudo ls -la /var/backups/proxima/` (дампы 29.08 и 30.08).
- Монитор: `systemctl list-timers proxima-host-monitor.timer`; `sudo head -c 300 /var/lib/proxima-ai-monitor/state.json`.
- Zone-check: `sudo tail -2 /var/log/openhands-zone.log`.
- Туннели: `ss -tln | grep -E ':1080|:1081|:8000'` - три LISTEN на 127.0.0.1.
- Ресурсы: `df -h /` 28G/158G (19%), `free -h` 1.6G/15G used, load 0.11.

## 3. Нашёл, но не понял

1. Две базы `proxima_dev`, обе пустые: на хостовом Postgres (роль `<pg_user>_dev`) и в rootless-контейнере `proxima-dev` в зоне OpenHands (user `proxima_dev`, без port-binding). В `/etc/proxima-ai/secrets/` лежат `proxima_dev_uri` и `proxima_dev_uri_sandbox` (обе 0600 root). Какую из них использует `.env.task` (`DATABASE_URI=<set>`) - не видно без чтения секрета. Политика зоны говорит «только proxima_dev via DATABASE_URI».
2. `~/.orca-remote/relay-*` (29.08 17:27, файлы 0666) - relay какого-то оркестратора (Orca coordinator из AGENTS.md?). Запущенных процессов/юнитов нет; кто и как его вызывает - неизвестно.
3. Ветка `deploy-main` в GitHub = `6168968` (= `mihailzhamba-bot/pmm-3-w1-daily-brief…`). На сервере ничего на неё не ссылается.
4. 11 пустых workspace OpenHands (`git init`, 0 коммитов) с датами 29.08 18:34-19:11 и 30.08 04:34 - похоже на conversation-workspace'ы, создаваемые при каждом диалоге. Кто чистит - не видно.
5. Ветка `pa30-stage` в `/srv/proxima-ai/repo` (без remote). Кто её создал и зачем - нет следов.
6. Роль `<pg_user>_diagnostics` (login, без superuser, `c`-привилегия на `proxima`) и `postgres_diagnostics_password` (15.08). Скрипт `infra/bootstrap/provision-postgres-diagnostics.sh` есть в main; использования (подключений) не видно.
7. Файл `/etc/proxima-ai/secrets/proxima_dev_ip` - mode 0644, 14 байт, 29.08 12:30. Что за IP и почему world-readable - неизвестно (не читал).
8. Два reboot'а подряд 30.08: 04:45:37 UTC «System is powering down (hypervisor initiated shutdown)», boot 04:45:51-04:47:01, снова boot 04:55:28. Инициатор - гипервизор Selectel; второй цикл не объяснён. Всё поднялось по restart-policy, разрыв в `state.json` монитора 04:44→04:57.
9. Веб-морда 1 раз за 7 дней записала `Error: webapp: env WEBAPP_AUTH_DATABASE_URI не задан…` - 30.08 05:57:32, ровно в момент моих первых curl-проб (`/`, `/login`, `/dashboard`). Повторный обход всех 6 страниц новых ошибок не дал. Похоже на разовую ленивую инициализацию auth-модуля при `WEBAPP_REQUIRE_AUTH=false`.
10. `agent-profiles/{Fedor,Harness,ORK_Z}.json` и `provider_connections.json` (+ `.bak` от root 29.08 19:13) в `/srv/openhands/persistence/.openhands/` - профили агентов и LLM-провайдер. Модель не выяснена (`settings.json` содержит только `"agent": "CodeActAgent"` среди безопасных ключей; остальное не читал).

## 4. Красные флаги

1. **Незапушенная работа PA-50.** Workspace `26fa6b87…` (0700, openhands-agent): `ai/pa-50` @ `d8c912c`, 4 коммита над `db56429` (`4f5d6c1 feat(webapp): провайдер данных и полная карточка сигнала`, `d4febf5`, `68785d8`, `d8c912c docs: доказательство make verify`). В GitHub ветки `ai/pa-50` нет (`git ls-remote --heads origin`, с мака). Единственная копия - на сервере.
2. **Схема БД отстаёт от кода на 4 миграции.** `schema_migrations` в `proxima`: версии 1-6, последняя `raw_artifact_headers` 14.08 17:53. В main `db/migrations` = 001-010 (007 quality_lineage, 008 release_records, 009 runtime_roles, 010 client_passport). `/srv/proxima-ai/repo` (initdb-mount compose) содержит только 001-006.
3. **Данные не обновляются.** Последний WB-ответ: `raw_wb_analytics_responses.persisted_at` = 25.08 16:33, `stg_wb_nm_report_rows` 1220 строк (staged 25.08). Business-signal: 14.08 19:37. `data/day1-wb-api` и `data/wb-analytics-spool` пусты. Расписания сбора нет: ни cron, ни timer (только monitor, backup, zone-check). 5 дней без данных на 30.08.
4. **Пять копий кода разъехались.** `~/proxima-ai` `db56429` (main) | `/srv/proxima-ai/repo` `fd95fcb` (25.08, detached, remote нет) | `~/proxima-webapp-staging/repo` `bae976c` (26.08, remote → отсутствующий `/tmp/pa49-head.bundle`, `?? Dockerfile.staging`) | OpenHands `tasks/pa-50` `db56429` | OpenHands `26fa…` `d8c912c`. Compose пилота монтирует миграции из самой старой копии.
5. **Веб-морда не соответствует main и запущена вручную.** Образ `proxima-webapp-staging:bae976c` собран из ветки PA-49 (26.08), тогда как PA-49 в main = `8dfa101`; контейнер без compose-label, без env_file, `WEBAPP_REQUIRE_AUTH=false`, `NODE_ENV=production`. `infra/webapp.compose.yaml` (auth=true, Caddy, домен `WEBAPP_DOMAIN`) в main - не развёрнут, Caddy на сервере нет.
6. **D8 не реализован на хосте.** Коммит `8dfa101 feat(infra): postgres bridge binding 172.17.0.1:5432` есть в main (`~/proxima-ai/infra/compose.yaml:19`), но `/srv` compose без этой строки и `ss` показывает 5432 только на 127.0.0.1. Sandbox-путь к `proxima_test`/`proxima_dev` через bridge отсутствует; вместо него в зоне живёт отдельный rootless Postgres 16.15 с пустой базой.
7. **Секреты.** (a) `~/.git-credentials` (0600, 130 B, 29.08) - серверный GitHub-кред, README обещал «later operation does not depend on… a server-side GitHub credential». (b) `wb_analytics_token`: `/etc/…` (25.08, sha256 `90ff3aec…`) ≠ `~/signal-inputs/` (13.08, `98a1b353…`) - два разных токена; finance/statistics/telegram совпадают. (c) `wb_prices_token`, `wb_promotion_token` отсутствуют (README ожидает 5; `.env` ссылается на `WB_PRICES_TOKEN_FILE`, `WB_PROMOTION_TOKEN_FILE`). (d) `proxima_dev_ip` 0644 в каталоге секретов. (e) `.orca-remote/*` файлы 0666.
8. **Egress = один SSH-туннель.** LLM-вызовы OpenHands идут через `HTTPS_PROXY=127.0.0.1:1081` → privoxy → SOCKS `dutch-tunnel` → `root@153.56.134.240:65022` (ключ `/root/.ssh/dutch_tunnel`). Падение того сервера = OpenHands без LLM. Zone-check это мониторит, но резерва нет.
9. **Хрупкость loopback-патча OpenHands.** По `ZONE_CHANGES.md` §1.1: agent-canvas 1.16.0 не умеет bind на loopback штатно, патч в vendored-скриптах; `npm install` его снимает. `preflight-bind-guard.sh` делает fail-closed (сервис не стартует). 29.08 12:32 zone-check уже ловил `port 8000 answers externally: 200` (до патча).
10. **Память зоны.** 29.08 18:35-18:55 четыре ALERT `zone memory 37xx MB near 4G limit`; сейчас порог в скрипте 7.3 GB (лимит подняли?) и `zone-mem=1343M`. `/srv/openhands` = 8.0G (persistence 3.5G, rootless-docker 2.0G, cache 1.3G, workspaces 1.3G).
11. **Toolchain на сервере не соответствует репо.** `uv` нет, `psql` на хосте нет, системный Python 3.12.3 (репо требует 3.14 через uv), node v22.23.2 OK. `make verify` вне OpenHands-зоны не запустить; в `~/proxima-ai` нет `node_modules`.
12. **Мусор.** `hopeful_gates` (exit 1, 26.08), анонимный volume `5a5b53e1…` (28.08), 11 пустых workspace, 3 старых дампа в `/srv/proxima-ai/backups` (13/21/25.08, вне ротации), пустая база `proxima_dev` на хосте.
13. **Шум безопасности (не критично).** 29.08 16:08 brute-force с `220.90.220.204` (13× `maximum authentication attempts exceeded`); ufw = только 22/tcp, `PasswordAuthentication no`, `AllowUsers proxima-admin`, `MaxAuthTries 3`. GlitchTip: `ALLOWED_HOSTS is the wildcard default` (RuntimeWarning).

## Приложение. Факты сервера, 30.08.2026

### a) Порты и сервисы

`sudo ss -tlnp` (05:55 UTC):

| Порт | Процесс | Кто |
|---|---|---|
| 0.0.0.0:22, [::]:22 | sshd | система |
| 127.0.0.1:5432 | docker-proxy → 172.19.0.2 | `proxima-ai-postgres-1` (compose `proxima-ai`) |
| 127.0.0.1:3000 | docker-proxy → 172.17.0.2 | `proxima-webapp-staging` (docker run, bridge) |
| 127.0.0.1:8080 | docker-proxy → 172.20.0.5 | `glitchtip-web-1` (compose `glitchtip`, сеть `proxima-ai-glitchtip`) |
| 127.0.0.1:8000 | node `agent-canvas/scripts/ingress.mjs` pid 2333 | user-unit `agent-canvas.service` (UID 1002) |
| 127.0.0.1:3001 | node `agent-canvas/scripts/static-server.mjs` pid 2287 | тот же unit |
| 127.0.0.1:18000 | python `agent-server --import-modules canvas_ui_tool` pid 1842 | тот же unit, cwd `/srv/openhands/persistence/.openhands/agent-canvas/workspaces` |
| 127.0.0.1:18001 | python `uvicorn openhands.automation.app:app` pid 2307 | тот же unit |
| 127.0.0.1:1080 | `ssh -N -D` pid 696 (root) | `dutch-tunnel.service` |
| 127.0.0.1:1081 | privoxy pid 717 | `privoxy.service` |
| 127.0.0.1:40533 | containerd | система |
| 127.0.0.53/54:53 | systemd-resolved | система |

`sudo docker ps -a`: running - `proxima-ai-postgres-1` (healthy), `glitchtip-web-1`, `glitchtip-worker-1`, `glitchtip-postgres-1`, `glitchtip-redis-1` (redis:7.4.11-alpine), `proxima-webapp-staging`; exited - `glitchtip-migrations-1` (0, 46 ч назад), `hopeful_gates` (1, 4 дня). Все running стартовали 04:55:36 UTC (после reboot), RestartCount 0.
`sudo docker images`: proxima-webapp-staging bae976c/latest 424MB (4 дня), node 22-bookworm-slim, node 22-alpine, redis 7/7.4.11-alpine, postgres 16-alpine/16.10-alpine, glitchtip 6.2.6 1.08GB. Volumes: `proxima-ai_postgres-data`, `glitchtip_glitchtip-pgdata`, анонимный `5a5b53e1…`.
`systemctl list-units --type=service --state=running`: 24 юнита, из проектных - `docker`, `containerd`, `dutch-tunnel`, `openhands-ingress-tunnel`, `privoxy`, `user@1000`, `user@1002`, `watchdog`, `unattended-upgrades`. Failed: 0.
User-units UID 1000 (`systemctl --user list-units`): 0. UID 1002 (`sudo -u openhands-agent XDG_RUNTIME_DIR=/run/user/1002 systemctl --user list-units --type=service`): `agent-canvas.service`, `docker-rootless.service`, `dbus.service` - все running. `loginctl`: openhands-agent linger=yes.
Rootless docker (UID 1002): `proxima-dev` postgres:16-alpine up ~1h, ports нет; images: `openhands-zone/agent-canvas:1.16.0` 1.49GB, `ghcr.io/astral-sh/uv:0.12.7`, node 22-bookworm-slim, postgres 16-alpine, hello-world.
Юнит `agent-canvas.service` (cat): `OH_BIND_HOST=127.0.0.1`, `OH_MAX_CONCURRENT_RUNS=1`, `HTTPS_PROXY/ALL_PROXY=http://127.0.0.1:1081`, `NO_PROXY` включает `api.z.ai`, github, npm, pypi, `172.17.0.0/16`; `EnvironmentFile=/home/openhands-agent/.agent-canvas.env`; `ExecStartPre=/srv/openhands/config/preflight-bind-guard.sh`; `ExecStart=agent-canvas --public`; `HOME=/srv/openhands/persistence`.

### b) Код

| Чекаут | HEAD | Ветка | Remote | status | stash | Не в origin/main |
|---|---|---|---|---|---|---|
| `~/proxima-ai` | `db56429` 29.08 19:59+03 «Merge PR #33 …acceptance-migration-docs» | main | github.com/mihailzhamba-bot/proxima-ai | 0 | 0 | 0 (origin/main = db56429, локально) |
| `/srv/proxima-ai/repo` | `fd95fcb` 25.08 07:31+03 «Revert "fix: enforce READ-only Analytics token…(PA-13)"» | detached; есть `pa30-stage` | нет | 0 | 0 | нет origin - сравнить нельзя |
| `~/proxima-webapp-staging/repo` | `bae976c` 26.08 06:45+03 «feat(webapp): т05 - стайлгайд…(PA-49)» | detached | `/tmp/pa49-head.bundle` (файла нет) | 1 (`?? services/webapp/Dockerfile.staging`) | 0 | нет origin/main |
| OpenHands `tasks/pa-50` | `db56429` | `ai/pa-50` | github (+ local) | 1 (`?? .openhands/SECURITY-POLICY.md`) | 0 | 0 |
| OpenHands `tasks/acceptance-migration-docs` | `ad89513` 29.08 16:57Z | `ai/acceptance-migration-docs` | github | 1 | 0 | 17 относительно локального `origin/main`=`c412a27` (устаревший ref; ветка запушена, PR #33 смержен) |
| OpenHands `project/26fa6b87…` | `d8c912c` 29.08 19:07Z «docs(agent-system): доказательство make verify и итог ревью по PA-50» | `ai/pa-50` | `local` → tasks/pa-50, `origin` github | 1 (`?? _bmad/_bmad`) | 0 | 4 над local `main`; в GitHub ветки нет |
| OpenHands `project/*` ещё 11 | нет коммитов | master | нет | 0-5 untracked | 0 | - |

Команды: `git log -1 --format="%h %ci %s"`, `git branch --show-current`, `git remote -v`, `git status --short | wc -l`, `git stash list`, `git log --oneline origin/main..HEAD`; для зоны - `sudo -u openhands-agent git -C …` (под root - «dubious ownership»). `git ls-remote --heads origin` выполнен с мака из клона.
`git -C ~/proxima-ai branch -a`: локально `main`, `feat/pa-49-warm-precision`; remote-ветки 13.

### c) Расписание

`systemctl list-timers --all`: `proxima-host-monitor.timer` (OnBootSec=2min, OnUnitActiveSec=1min, Persistent) - последний запуск 05:57:00; остальные системные (apt-daily, logrotate, man-db, e2scrub, privoxy-cleanup, …). User-timers обоих юзеров: только `launchpadlib-cache-clean.timer`.
`sudo ls /etc/cron.d`: `e2scrub_all`, `openhands-zone-check` (`*/5 * * * * root /usr/local/sbin/openhands-zone-check.sh`), `proxima-pg-backup` (`0 3 * * * root /usr/local/bin/proxima-pg-backup.sh >> /var/log/proxima-backup.log`). `/var/spool/cron/crontabs` пуст; `crontab -l` для proxima-admin/openhands-agent/root - нет.
`proxima-host-monitor.service`: `User=proxima-monitor`, `EnvironmentFile=/etc/proxima-ai/monitor.env` (переменные `PROXIMA_MONITOR_CONTRACT`, `PROXIMA_MONITOR_STATE_FILE`, `PROXIMA_TELEGRAM_TOKEN_FILE`, `PROXIMA_TELEGRAM_CHAT_ID_FILE`), `ExecStart=/usr/bin/python3 /usr/local/lib/proxima-ai/host_monitor.py`, hardening (ProtectSystem=strict, ProtectHome, NoNewPrivileges), `ReadWritePaths=/var/lib/proxima-ai-monitor`.
`proxima-pg-backup.sh` (1599 B, 0750 root, 29.08 12:31): `pg_dump` `proxima` через `docker exec proxima-ai-postgres-1` → `/var/backups/proxima/<date>-proxima.sql.gz`, age-шифрование (`backup_age_recipient`) → `s3cmd put s3://proxima-backups/YYYY-MM/…`; retention local 14 дн; затем `proxima_dev` из rootless `proxima-dev` (`pg_dump -U proxima_dev`). Лог 30.08: `OK local proxima (64K)`, `OK s3`, `OK local proxima_dev (4.0K)`, `OK s3`.
`openhands-zone-check.sh` (1984 B, 29.08 18:56): проверяет agent-canvas/docker-rootless active, диск >75% / <20GB, память `user@1002` >7.3GB, контейнеров в зоне >2, dutch-tunnel/1080/privoxy/1081, ufw не пускает 8000/1800x, 8000 слушает; алерт в Telegram через `telegram_bot_token`/`telegram_chat_id`. Лог: 7 ALERT (29.08 12:32 «port 8000 answers externally: 200»; 18:35-18:55 ×4 «zone memory 37xx MB near 4G limit»; ещё 2 - не выведены), сейчас `ok`.

### d) Базы данных

Контейнер `proxima-ai-postgres-1`: image `postgres:16.10-alpine`, started 04:55:36Z, healthy, RestartCount 0; env `POSTGRES_USER_FILE`, `POSTGRES_PASSWORD_FILE`, `POSTGRES_DB=proxima`; mounts: `/srv/proxima-ai/repo/db/migrations → /docker-entrypoint-initdb.d`, `/etc/proxima-ai/secrets/postgres_{user,password} → /run/secrets/*`, volume `proxima-ai_postgres-data`. Compose: `/srv/proxima-ai/repo/infra/compose.yaml`, порт `127.0.0.1:${PROXIMA_POSTGRES_PORT:-5432}:5432`. `pg_postmaster_start_time` 04:55:37Z. PostgreSQL 16.10.
Базы (`SELECT datname, owner, size FROM pg_database`): `postgres` 7.5MB, `proxima` (owner `<pg_user>`) 9.4MB, `proxima_dev` (owner `<pg_user>_dev`) 7.6MB. Роли: `<pg_user>` (superuser), `<pg_user>_dev`, `<pg_user>_diagnostics` (обе login, без привилегий). `datacl` на `proxima`: `<pg_user>_diagnostics=c`. Активных клиентских соединений кроме моего psql - 0.
Схемы `proxima`: только `public`; extensions: `plpgsql`; views: 0.
`SELECT relname, n_live_tup FROM pg_stat_user_tables` (proxima):

| Таблица | rows | max(timestamp) |
|---|---|---|
| artifact_manifests | 0 | created_at - |
| business_signal_raw_artifacts | 18 (count 27) | persisted_at 2026-08-14 18:03:46 |
| business_signal_runs | 6 (count 11) | completed_at 2026-08-14 19:37:36; telegram_attempted_at 2026-08-13 15:03 |
| dim_product | 1 (count 9) | created_at 2026-08-14 19:37:17 |
| dim_warehouse_map | 60 | created_at 2026-08-14 18:00:39 |
| intake_attempts | 0 | - |
| raw_wb_analytics_responses | 4 (count 7) | persisted_at 2026-08-25 16:33:15 |
| schema_migrations | 2 (count 6) | applied_at 2026-08-14 17:53:26 |
| source_artifacts | 0 | - |
| stg_wb_nm_report_rows | 1220 | staged_at 2026-08-25 16:33:15 |
| tenants | 1 (count 2) | created_at 2026-08-14 19:37:17 |
| wb_analytics_quota_events | 1 (count 2) | reserved_at 2026-08-25 04:37:58; sent_at 2026-08-25 16:32:54 |
| wb_analytics_report_tasks | 1 (count 2) | downloaded_at/updated_at 2026-08-25 16:33:15 |

(n_live_tup - оценка; count(*) - точное значение из max-запросов, где они расходятся.)
`schema_migrations`: 1 bootstrap (13.08 09:06), 2 intake_metadata (13.08), 3 wb_analytics_raw (13.08 09:18), 4 business_signal_slice (13.08 11:14), 5 wb_analytics_staging (14.08 17:53), 6 raw_artifact_headers (14.08 17:53); sha256 каждой записаны в таблице.
`proxima_dev` (хост): схема `public`, таблиц 0, ledger-таблиц нет. Rootless `proxima-dev` (PostgreSQL 16.15, `proxima_dev`): таблиц 0, 7.5MB.
GlitchTip (`glitchtip-postgres-1`, postgres:16.10-alpine, БД `glitchtip`, user `glitchtip`): organizations 1, projects 1 (`webapp`, javascript-nextjs), users 1, issues 1, project keys 1, api_tokens 2; партиция `issue_events_issueevent_20260828_h0` = 1 событие. Бэкапа `glitchtip-pgdata` нет (по замыслу, комментарий compose).
Старые дампы `/srv/proxima-ai/backups/`: `pre-phase-2.1-20260813.dump` 40K, `pre-pa13-20260821-082129.dump` 81K, `pre-pa13rw-20260825.dump` 68K.

### e) Веб-сервер и домены

nginx/caddy/traefik: нет (`ls /etc/nginx /etc/caddy /etc/traefik`, `dpkg -l`). Публичных портов кроме 22 нет (`ufw status verbose`: deny incoming, allow 22/tcp v4+v6). `vps-contract.json`: `application_access: ssh_tunnel_only`, `inbound_allow: [tcp/22]`.
:3000 = контейнер `proxima-webapp-staging` (`Cmd: node services/webapp/server.js`, `HOSTNAME=0.0.0.0`, `PORT=3000`, `NODE_ENV=production`, `WEBAPP_REQUIRE_AUTH=false`, `NEXT_TELEMETRY_DISABLED`; mounts нет; RestartPolicy unless-stopped; сеть bridge 172.17.0.2). `GET /` → 307 `/brief`.
:8080 = `glitchtip-web-1` (`GLITCHTIP_DOMAIN=http://localhost:8080`, `PORT=8080`, `EMAIL_BACKEND=console`, `DATABASE_URL`, `REDIS_URL`, `SECRET_KEY` = set). Compose-сеть `proxima-ai-glitchtip`, alias `glitchtip` (DSN-хост для webapp).
Домены: в конфигурации сервера доменов нет. В main `infra/Caddyfile` ожидает `{$WEBAPP_DOMAIN}` (A-запись → 135.106.186.210) - не развёрнут.
`/etc/hosts`: `149.154.167.220 api.telegram.org` (pin, README).
sshd (`sudo sshd -T`): `allowusers proxima-admin`, `permitrootlogin no`, `passwordauthentication no`, `maxauthtries 3`.

### f) Ошибки за 7 дней

`sudo journalctl -p err --since "7 days ago" | tail -60`: sshd brute-force 29.08 16:08 (`220.90.220.204`, 13 строк); 29.08 16:10 `sshd[3817]: connect_to localhost port 8000: failed` ×19 (reverse-туннель до старта agent-canvas); `kex_exchange_identification: Connection reset by peer` ×6 (сканеры); 29.08 18:18 `(o-bridge)[131466]: PAM unable to dlopen(pam_lastlog.so)`; `utempter: pututline: Permission denied` ×10 (сессии openhands-agent); 30.08 04:45:37 `Access denied for user proxima-admin by PAM account configuration` (момент shutdown); `Failed to find module 'i6300esb'` ×2 при boot. Критичных ошибок приложений нет.
Warnings по юнитам (`-p warning`, json-count): kernel 30215, ssh 351, init.scope 263, user@1002 125, networkd-dispatcher 47.
`journalctl _UID=1002 -p err`: 29.08 12:27:51 `openhands-agent : user NOT in sudoers ; COMMAND=/usr/bin/cat /etc/proxima-ai/secrets/proxima_dev_password` (попытка агента прочитать секрет через sudo - отказано); остальное utempter.
`docker logs --since 168h --tail 40`: `proxima-ai-postgres-1` - штатный shutdown 04:46:57 и старт 04:55:37, плюс мои `FATAL: role "root" does not exist` ×3 и 2 синтаксические ошибки (05:56-05:57, мои пробы); `proxima-webapp-staging` - 5 стартов «Ready», 1 `Error: webapp: env WEBAPP_AUTH_DATABASE_URI не задан…` 05:57:32; `glitchtip-web-1` - `RuntimeWarning: ALLOWED_HOSTS is the wildcard default`; `glitchtip-migrations-1` - 28.08 миграции применены, `models … have changes that are not yet reflected in a migration` (upstream); `glitchtip-worker-1` - `uptime-dispatch-checks` каждые ~секунды, ошибок нет; `glitchtip-postgres-1`, `glitchtip-redis-1`, rootless `proxima-dev` - штатно. `hopeful_gates` - `logging driver does not support reading`.
Boots (`journalctl --list-boots`): 13.08 08:32 → 14.08 15:53; 14.08 15:54 → 29.08 08:26; 29.08 09:28 → 30.08 04:45; 30.08 04:45:51 → 04:47:01; 30.08 04:55:28 → now. `last -x`: shutdown 30.08 04:47-04:55 (8 мин), 29.08 08:26-09:28 (62 мин).

### g) Ресурсы

`uptime` 05:55 UTC: up 59 min, load 0.11/0.04/0.01. `df -h /`: /dev/sda1 158G, used 28G, avail 124G (19%) - диск больше контрактных 120 GiB. `free -h`: 15Gi total (контракт 12 GiB), used 1.6Gi, available 13Gi, swap 4.0Gi/0B.
`du -sh`: `/srv/proxima-ai/backups` 192K, `data` 9.0M, `glitchtip` 60M, `repo` 78M, `wb-probe-venv` 41M; `/srv/openhands` 8.0G (persistence 3.5G, rootless-docker 2.0G, cache 1.3G, workspaces 1.3G, config 144K, logs 52K); `~/proxima-ai` 9.7M; `~/proxima-webapp-staging` 3.2M; `/home/openhands-agent` 3.3G.
`/srv/proxima-ai/data`: 64 файлов, новейший 19.08 05:30 (`raw/project-activity/2026-08-09--2026-08-19/manifest.json`; там же `events.json` 846K, `build_dashboard.py`, `dashboard_template.html`); `business-signal/{objects,manifests(5),tmp}`, `business-signal-setup{,-v2}`; `day1-wb-api` и `wb-analytics-spool` пусты.

### h) Документация на сервере (имена и даты)

`~/proxima-ai` (все 29.08): `AGENTS.md` 36K, `ARCHITECTURE.md`, `CLAUDE.md`, `DESIGN.md`, `README.md`; `docs/adr/0001-0006`, `docs/agent-system/{DECISIONS,EVALS,HANDOFF(20K, 16:59),KNOWN_FAILURES,MEMORY,ORCHESTRATION,PROJECT,README,RULES,TASKS,TOOLS,WORKFLOW}.md`, `docs/architecture/{README.md, data-flow, delivery, deployment, system}.mmd`, `docs/audits/pa-39-*`, `docs/exec-plans/{active,completed}`, `docs/governance/{assumptions-register,dod-checklist,risk-register}.md`, `docs/operations/{agent-toolset,business-signal-runbook}.md`, `docs/release-gates/{2026-08-27-pmm-7-dry-run,README}.md`. `docs/state/` нет.
`/srv/proxima-ai/repo`: `AGENTS.md` 12.9K (25.08), `ARCHITECTURE.md`, `CLAUDE.md` (21.08, root), `README.md` 5.1K (25.08); `docs/` без `release-gates/`; adr только 0001; `docs/exec-plans/active/{pm2-backlog-run,pmm-audit-2026-08-17}.md` (21.08); `docs/agent-system/*` 25.08.
`~/proxima-webapp-staging/repo` (все 26.08): те же корневые 5 файлов (`AGENTS.md` 15.7K), `docs/exec-plans/active/pa-49-webapp-skeleton.md`, adr только 0001, без `release-gates/`.
Зона OpenHands: `/srv/openhands/config/OPENHANDS_SECURITY_POLICY.md` (12 пунктов: prod-пути запрещены, только `proxima_dev`, без push/merge/deploy, `make verify` stop-hook), `ZONE_CHANGES.md` 11.7K (29.08 19:00: loopback-патч, confirmation_mode=true, MCP tavily@0.2.22 и mcp-atlassian@0.23.1 запинены, `OH_MAX_CONCURRENT_RUNS=1`, `SANDBOX_VOLUMES` убран, `LOCAL_BACKEND_API_KEY` ротирован).

### i) Секреты (путь, mode, owner, size, дата; содержимое не читалось)

`/etc/proxima-ai/` (0750 root:proxima-monitor): `monitor.env` 0640 419B 13.08; `vps-contract.json` 0640 1888B 13.08; `business-signal/` 0700 proxima-admin (`founder-chat.json` 25B, `products.csv` 442B, `warehouses.csv` 3048B 14.08, `.bak-2026-08-14`).
`/etc/proxima-ai/secrets/` (0750 root:proxima-monitor, 29.08 12:30):

| Файл | mode | owner | size | дата |
|---|---|---|---|---|
| backup_age_key.txt | 0600 | root | 184 | 29.08 11:20 |
| backup_age_recipient | 0644 | root | 63 | 29.08 11:20 |
| glitchtip_bootstrap_meta | 0600 | root | 86 | 28.08 07:45 |
| glitchtip_superuser_password | 0600 | root | 49 | 28.08 07:43 |
| glitchtip_webapp_dsn | 0600 | root | 61 | 28.08 07:45 |
| postgres_diagnostics_password | 0600 | root | 65 | 15.08 10:16 |
| postgres_password | 0640 | root:proxima-monitor | 65 | 13.08 09:06 |
| postgres_url | 0600 | proxima-admin | 109 | 13.08 14:58 |
| postgres_user | 0640 | root:proxima-monitor | 8 | 13.08 09:06 |
| proxima_dev_ip | 0644 | root | 14 | 29.08 12:30 |
| proxima_dev_password | 0600 | root | 33 | 29.08 09:30 |
| proxima_dev_uri | 0600 | root | 85 | 29.08 09:30 |
| proxima_dev_uri_sandbox | 0600 | root | 86 | 29.08 10:13 |
| s3_access_key / s3_secret_key | 0600 | root | 33 / 33 | 29.08 11:20 |
| telegram_bot_token | 0640 | proxima-admin:proxima-monitor | 47 | 13.08 14:50 |
| telegram_chat_id | 0640 | proxima-admin:proxima-monitor | 10 | 15.08 09:28 |
| wb_analytics_token | 0600 | proxima-admin | 410 | 25.08 16:31 |
| wb_finance_token | 0600 | proxima-admin | 422 | 13.08 14:50 |
| wb_statistics_token | 0600 | proxima-admin | 422 | 13.08 14:50 |

Отсутствуют: `wb_prices_token`, `wb_promotion_token`.
`~/signal-inputs/` (0700 proxima-admin, все 0600, 13.08): `wb_analytics_token` 410B 14:04, `wb_finance_token` 422B, `wb_statistics_token` 422B, `telegram_bot_token` 47B, `products.csv` 442B (+2 `.pre-*`), `warehouses.csv` 2361B (+2 `.pre-*`), `candidate-shortlist.csv` 702B, `founder-chat.json` 25B. Подкаталога `fixtures/` нет.
sha256 (первые 12): `wb_analytics_token` etc `90ff3aec07ed` / signal-inputs `98a1b35348fc` - **разные**; `wb_finance_token` `853d1aea1d6b` - равны; `wb_statistics_token` `9ee9b6daf1da` - равны; `telegram_bot_token` `21d1d3823523` - равны.
Прочее: `/home/openhands-agent/.agent-canvas.env` 0600 256B 29.08 19:18; `/root/.ssh/{dutch_tunnel,openhands_ingress}` 0600 419B (29.08) + `.pub`, `authorized_keys` 81B (13.08); `~/.git-credentials` 0600 130B 29.08 17:00; `/srv/proxima-ai/repo/.env` 0600 619B 14.08 (переменные: `WB_{STATISTICS,ANALYTICS,FINANCE,PRICES,PROMOTION}_TOKEN_FILE`, `PROXIMA_RAW_DIR`, `PROXIMA_SPOOL_DIR`, `POSTGRES_{USER_FILE,PASSWORD_FILE,HOST,PORT,DB}`); `/srv/proxima-ai/glitchtip/.env` 0600 root 163B 28.08 (`GLITCHTIP_SECRET_KEY`, `GLITCHTIP_POSTGRES_PASSWORD`); `/srv/openhands/workspaces/proxima-ai/tasks/*/.env.task` 0644 99B (`DATABASE_URI`); `/srv/openhands/persistence/.openhands/{secrets.json 1386B 30.08 04:55, settings.json 5525B 29.08}` 0600.

### j) Тесты и Makefile (`~/proxima-ai`)

`find services db tools -name "*test*" -o -name "*.spec.*" | grep -v node_modules`: Python 21 файлов `test_*.py` - `services/control-plane/tests/{diagnosis/ (9), evals/, unit/, e2e/, test_boundary.py}`, `tools/tests/{test_verifiers,test_wb_async_report,test_wb_api_probe,test_runtime_roles_schema,test_wb_async_report_postgres}.py`; TS 12 файлов `*.test.ts` - `services/collector/tests/` (7: imported-boundary, manual-wb-xlsx-intake, business-signal ×3, client-passport-config, intake-contract), `services/webapp/src/tests/` (5: brief-fixtures, metrics, rub, gyr, fx). Это соответствует «48 py + 43 TS тестов» из handoff 14.08 только по файлам; число тест-кейсов не считалось.
`grep -E '^[a-z-]+:' Makefile`: `verify: install codegen typecheck test contracts migrations pg-roundtrip provenance architecture boundary secrets vps business-signal`; цели `install codegen typecheck test webapp-lint webapp-build contracts migrations pg-roundtrip provenance architecture boundary secrets vps business-signal agent-toolset probe-wb-api apply-migrations collect-wb-analytics`.
На сервере `make verify` не запускался в `~/proxima-ai`: нет `node_modules`, `.venv`, `uv`; лог `verify-acceptance-migration-docs.log` (17K, 29.08 16:58) лежит в `/srv/openhands/logs/` - verify гонялся внутри зоны OpenHands.
