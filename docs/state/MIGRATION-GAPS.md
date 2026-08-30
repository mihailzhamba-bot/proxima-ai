# MIGRATION-GAPS - проверка полноты миграции на сервер

**Дата:** 30.08.2026 (Сессия 1b, окно A, Этап 2). **Истина:** `origin/main` = `db56429` (D3).
**Стороны сличения:** локальный архив `~/Desktop/MILV/03-startups/!Proxima/PROXIMA AI (архив - работа на VPS)` (ветка `feat/pa-49-warm-precision` @ `8dfa101`, 29.08), `origin/ai/pa-50` @ `d8c912c`, все 46 remote-refs GitHub, серверные чекауты по `INVENTORY.md` (сервер: одна read-only команда `ssh proxima 'ls/stat/find/git log'` без sudo).
**Метод:** только `git fetch/log/diff/show/ls-tree/cherry/fsck`, чтение файлов, 6 проверочных скриптов в scratchpad (скан секретов печатает первые 4 символа + длину). Ничего не восстанавливалось и не менялось. Каждый факт - команда в Приложении.

## 1. TL;DR

- **Потеряно точно: 0 файлов кода и данных.** Архивная ветка целиком внутри main (`git merge-base origin/main origin/feat/pa-49-warm-precision` = `8dfa101` = её HEAD; `origin/main..archive` пуст). Все 27 локальных веток архива и 6 snapshot-коммитов 29.08 есть на origin; рабочее дерево архива чистое (0 modified, 0 untracked).
- **Под подозрением: 3 класса.** (а) 27 dangling-коммитов в архиве - сброшенные stash/amend, содержимое проверено построчно: всё в main или на origin-ветках, кроме двух устаревших текстовых WIP 15.08; (б) 9 операционных файлов только на сервере (бэкап, zone-check, bind-guard, политика зоны, `Dockerfile.staging`) - ни в одном git; (в) `build/reports/proxima-ai-activity-2026-08-09--2026-08-19.html` (702 КБ) - единственная копия в архиве, регенерируется из `raw/`.
- **Восстановимо: 7 origin-веток с незамерженным кодом** (1 545 строк кода вне main): `ai/pa-50` (провайдер данных webapp), `pmm29-contracts` (контракты signal/diagnosis/decision-record), `PA-03-02-promotion` + `pa41-full-w2-phase3` (единственный писатель `fact_order_counts`), `pmm-20-scn-001` (детектор SCN-001, базовая норма 7/14/28), `now-orchestrator`, `pa-9` (preview, скорее всего superseded), `stash/pa-27-snapshot` (Makefile). Три разных `010_*.sql` в трёх ветках - коллизия нумерации при восстановлении.
- **Секреты в истории git: НЕТ.** Скан 258 коммитов + 27 dangling в архиве (все refs) и 276 коммитов в клоне (46 refs) по 12 паттернам: 10 совпадений, все - код (`password = Path(...).read_text()`) или плейсхолдер `<password>`. Файлы `.env*`, `*.pem`, `*.key`, `id_*` не добавлялись ни разу. Чистка истории и ротация по итогам скана не нужны.
- **Косвенные признаки:** импорты TS 182/0 битых, `tsc` collector 0 ошибок, Python 58 файлов/0 битых; 1 битая ссылка в конфиге (`opencode.json` → `tools/node_repl_server.js`, никогда не существовал); 1 env без примера (`PROXIMA_TEST_POSTGRES_DSN`) + 2 фантомных имени в AGENTS.md; 10 таблиц из миграций 007-010 нет в БД, 0 таблиц в БД без миграции; 11 из 23 таблиц никто в main не пишет.
- **Главный вывод:** миграция ничего не потеряла; риск не в переезде, а в 7 незамерженных ветках и в серверных скриптах вне git. Решение «мержить / списывать» - за Mike (Ворота 1).

## 2. Потеряно точно (с доказательством)

Ничего. Проверено четырьмя способами (30.08.2026):

| Проверка | Команда | Результат |
|---|---|---|
| Коммиты только в архиве | `git log --oneline origin/main..origin/feat/pa-49-warm-precision` | пусто |
| Файлы, удалённые в main после `8dfa101` | `git diff --name-status origin/feat/pa-49-warm-precision origin/main \| grep -E '^(D\|R)'` | 1 rename `R092 db/migrations/007_client_passport_supply_plan.sql → 010_…` (коммиты `fa57aa9`, `31cf85f`, `ad89513` - объяснён) |
| Локальные ветки архива без копии на origin | цикл `git branch -r --contains <tip>` по 27 `refs/heads/*` | 0 веток; местный `main` архива = `72423c2` = `origin/mihailzhamba-bot/pmm29-contracts` |
| Незакоммиченное в архиве | `git -C "<архив>" status --short` | пусто (только `!!` ignored) |
| Локальный `raw/` vs сервер | `stat` локально / `ssh proxima 'stat …events.json'` | 845 816 Б, 19.08 05:29 UTC с обеих сторон; 15 файлов = 15 файлов |

Единственное, чего «нет», никогда и не существовало ни в одном ref (`git log --all -- <path>` = пусто): `tools/node_repl_server.js`, `services/webapp/drizzle/`, `docs/evidence/`, `docs/agent-system/evidence/`, `docs/operations/incident-playbook.md`, `contracts/authority-map.yaml`, `services/collector/{migrations,scripts,src/sources}` - см. §5.

## 3. Под подозрением

### 3.1. Dangling-коммиты в архиве (27; `git fsck --lost-found`)

Исчезнут при `git gc` (reflog 90 дней). Содержимое сверено с main построчно (доля добавленных строк, найденных verbatim в файле main):

| Хэш | Дата | Что | Вердикт |
|---|---|---|---|
| `ec002ba` | 27.08 | `feat(collector): promote staged order counts atomically` (7 файлов, +655) | amend-версия `321a855` на `origin/mihailzhamba-bot/PA-03-02-promotion`; не в main - см. §4 |
| `ac8a41d` | 28.08 | stash: `tools/verify_runtime_boundary.py` +19 | 19/19 строк = `8f543b5` (в main) |
| `a020527` | 15.08 | stash PA-27: Makefile +52, README +21 | подмножество `ddefed6` = `origin/stash/pa-27-snapshot` |
| `d1e590e` | 26.08 | stash PA-49 т07: 7 файлов | 63/64 строк AGENTS.md и все компоненты в main |
| `290b3f8`, `26dea51` | 25.08 | stash: package.json, Makefile (PA-49) | 2/2, 6/7 в main |
| `707b6d5`, `258b658`, `bb8e4b7`, `90da64a` | 27.08 | stash: `opencode.json` (локальный путь npx), `.autopilot/state.js` | путь npx в main с `8d0932e`; state.js - шум |
| `9a89d2f` | 17.08 | stash: `docs/agent-system/DECISIONS.md` +9 | 8/9 в main |
| `618ac7a` | 15.08 | stash pa-32: AGENTS.md +46, CLAUDE.md +1 | 0/46 в main - **текст AGENTS.md от 15.08, переписан позднее**; единственный dangling с уникальным содержимым, ценность низкая |
| 12 прочих (`6301967`, `704f7ae`, `afafb34`, `abe3c8f`, `f2c43ff`, `c36adfa`, `e1f16e4`, `84f4617`, `90188e1`, `02758d7`, `0958654`, `a17ffd4`) | 12-27.08 | amend-дубли | у каждого есть коммит в main с тем же сообщением (`3770efd`, `0e9fe6f`, `4c1db07`, `6082846`, `8b07249`, `dfaa91a`, `0edb08d`, `5db8ca6`, `877bb3e`) |

Dangling blob `b048b96` = черновик `REVIEWS.md` фазы 01 (текст в `.planning/phases/01-…/REVIEWS.md` main).

### 3.2. Только на сервере, ни в одном git (по `INVENTORY.md` §a, c, h, i; `ssh` 30.08)

| Файл | Где | Дата | Почему подозрение |
|---|---|---|---|
| `proxima-pg-backup.sh` (1599 Б, 0750 root) | `/usr/local/bin/` | 29.08 | ночной бэкап + age + S3; репо не содержит (`git ls-files \| grep backup` = только `001_bootstrap.sql`) |
| `openhands-zone-check.sh` (1984 Б) | `/usr/local/sbin/` | 29.08 | алерты в Telegram; не в репо |
| `preflight-bind-guard.sh` | `/srv/openhands/config/` | 29.08 | fail-closed старт agent-canvas; не в репо |
| `OPENHANDS_SECURITY_POLICY.md`, `ZONE_CHANGES.md` (11.7 КБ) | `/srv/openhands/config/` | 29.08 | политика зоны и журнал изменений loopback-патча; не в репо |
| `.openhands/SECURITY-POLICY.md` | `tasks/pa-50`, `tasks/acceptance-migration-docs` (untracked) | 29.08 | в main есть только `.openhands/{hooks.json,hooks/verify-gate.sh,setup.sh}` |
| `services/webapp/Dockerfile.staging` (1486 Б) | `~/proxima-webapp-staging/repo` (untracked) | 26.08 03:54 | = `Dockerfile` + 1 строка `ENV PUPPETEER_SKIP_*` (WEB-STATE §7) |
| `/etc/proxima-ai/{monitor.env,vps-contract.json}`, `/srv/proxima-ai/repo/.env` (619 Б), `.env.task` (99 Б) | сервер | 13-29.08 | конфиги: в репо `infra/runtime.env.template`, `infra/monitoring/monitor.env.example`, `infra/vps-contract.json` - соответствие имён проверено (§7.3), значения не сверялись |
| `/usr/local/lib/proxima-ai/host_monitor.py` | сервер | 13.08 | в репо `infra/monitoring/host_monitor.py`; равенство версий не проверялось (нужен sha256 с сервера) |

Бэкапится только Postgres (S3). Скрипты и политика зоны при потере VPS уходят вместе с ним.

### 3.3. Локальные артефакты вне git (архив, `git status --ignored`)

| Путь | Размер / файлов | Дата | Вердикт |
|---|---|---|---|
| `build/reports/proxima-ai-activity-2026-08-09--2026-08-19.html` | 702 КБ | 19.08 08:29 | **единственная копия** (`find /srv/proxima-ai /home/proxima-admin -name 'proxima-ai-activity-*.html'` = пусто); регенерируется `raw/…/build_dashboard.py` из `events.json` |
| `build/architecture/{system,data-flow,delivery,deployment}.{svg,pdf,png}` | 10 файлов, 0.4 МБ | 12.08 / 28.08 | рендер `docs/architecture/*.mmd` (`make architecture`) - мусор |
| `raw/project-activity/2026-08-09--2026-08-19/` | 15 файлов, 2.0 МБ (`jira.json` 473 КБ, `github.json` 90 КБ, `events.json` 846 КБ, `collect_local.py`, `build_dashboard.py`) | 19.08 | копия на сервере `/srv/proxima-ai/data/raw/…` побайтно совпадает; `jira.json` = снимок Jira на 19.08 - пригодится окну B |
| `services/collector/dist/` | 66 файлов, 332 КБ | 16.08 | устаревший `npm run build` - мусор |
| `.opencode/{package.json,package-lock.json,.gitignore}` | 65 Б + 14 КБ | 16.08 | зависимость `@opencode-ai/plugin@1.18.18` - `npm i` восстановит |
| `_bmad/custom/config.user.toml` | 162 Б | 28.08 | личные overrides BMAD, паттернов ключей 0 |
| `.venv` 45 МБ, `.next` 464 МБ, `__pycache__`, `.pytest_cache`, `*.tsbuildinfo`, `.DS_Store` | - | - | кэши |

### 3.4. Прочее

- `pa30-stage` на `/srv/proxima-ai/repo` = `54c4cb1` (15.08) = коммит из `origin/mihailzhamba-bot/pa-30-mcp-cli-toolset`; уникального содержимого нет.
- `fixtures/wb-api/` 436 МБ (36 файлов) - в клоне через `.git/info/exclude`, копия на сервере `~/signal-inputs/fixtures/wb-api/`; в git не влезает (2 файла > 100 МБ) - решение Mike (STATE).
- Точность `API-FACTS.md` §D: строка «ручной XLSX-интейк → `source_artifacts`, `artifact_manifests`, `intake_attempts`» неверна - `services/collector/src/intake/manual-wb-xlsx.ts` пишет манифесты в файловую систему (`publishManifest`), в БД эти таблицы никто не пишет (§7.7), на сервере в них 0 строк.

## 4. Восстановимо (откуда) - без действий

Незамерженные origin-ветки с кодом (`git cherry origin/main <b>`: все коммиты `+`; пофайлово: absent = файла нет в main, differ = есть, но отличается):

| Ветка @ tip | Коммитов | Код: absent / differ | Что это | Связь с лестницей |
|---|---|---|---|---|
| `origin/ai/pa-50` @ `d8c912c` (29.08) | 4 | 7 / 9 (19 файлов, +694/-68) | `src/lib/data/{provider,types,fixtures-provider,postgres-provider,index}.ts`, `signal-detail.tsx`, тест; вводит `WEBAPP_DATA_MODE=fixtures\|postgres`, postgres-режим = явная заглушка «ждёт PMM-29 и роль webapp_readonly» | M-03 (D11) |
| `origin/mihailzhamba-bot/pmm29-contracts` @ `72423c2` (29.08) | 4 над `c412a27` | 14 / 1 (26 файлов, +1039/-242) | `contracts/{signal,diagnosis,decision-record}.schema.json` + 7 synthetic-примеров, TS-типы `services/collector/src/contracts/*`, `product-contracts.test.ts` (Ajv), `tools/verify_contracts.py` +68; закрыт автопилотом «PMM-29 contracts run». В main лежит только `.autopilot/2026-08-28-pmm29-contracts--wip/`, ссылающийся на эти схемы | M-03/M-04 (контракт сигнала) |
| `origin/mihailzhamba-bot/PA-03-02-promotion` @ `321a855` (27.08) | 2 над `727ef40` | 5 / 5 | `services/collector/src/facts/promote-order-counts.ts` (313 строк), `cli/{promote-order-counts,promotion-args}.ts`, `facts-promotion.test.ts` (238), `db/migrations/010_promotion_attempt_completion.sql`; INSERT в `fact_attempt_runs`, `fact_lineage_records`, `fact_order_counts`, `quality_check_results`, `stg_quarantine_rows` - **единственный писатель этих 5 таблиц** | M-01/M-02 (дневной ряд) |
| `origin/mihailzhamba-bot/pa41-full-w2-phase3` @ `e3df114` (29.08, snapshot pre-freeze) | 1 над `0a7b2c6` | 4 / 6 | то же ядро promotion + `db/migrations/010_phase3_promotion_privileges.sql`; новее PA-03-02 на 2 дня | как выше; выбрать одну из двух |
| `origin/mihailzhamba-bot/pmm-20-scn-001-u-cvr-aov-baseline-7-14-28` @ `7841ab0` (28.08) | 7 над `b5fa069` | 13 / 0 | `services/control-plane/src/proxima_control_plane/detectors/scn001/{baseline,clock,config,decomposition,loader,metrics,signal,smoke}.py` + 3 теста; сезонная база 7/14/28 дней, декомпозиция U×CVR×AOV; «codex gate 0/0» | M-02 «норма», M-03 «отклонение» - прямое попадание |
| `origin/mihailzhamba-bot/now-orchestrator` @ `397cdd9` (29.08, snapshot) | 5 над `f4b6e4c` | 27 / 0 | `tools/now_orchestrator/**` (core/integration/jira), `scripts/agent/now`; оркестрация агентов, не продукт | вне лестницы |
| `origin/mihailzhamba-bot/pa-9-p1-02-02-…` @ `8014f6e` (16.08) | 5 над `bdfcd57` | 7 / 3 | `db/migrations/007_preview_order_counts.sql`, `staging/preview-transform.ts`, `control-plane/preview.py`; preview дневных order_count из staging | скорее всего superseded фазой 3 (`fact_order_counts` в 007 main); проверить перед восстановлением |
| `origin/stash/pa-27-snapshot` @ `ddefed6` (29.08) | 1 над `1a211c9` | 1 / 1 | Makefile +95, README +35, `tools/tests/test_makefile.py` (140) - централизация runtime-конфига | инфраструктура |

Ветки, чей код уже в main (только docs отличаются, восстанавливать нечего): `pa-30-mcp-cli-toolset` (3 файла identical, 2 differ - main новее), `PA-56-glitchtip` (`infra/glitchtip.compose.yaml` в main через `e52059d`), `pa-29-agent-harness`, `feat/pa-49-webapp-skeleton`, `pa-12-state-evidence`, `pa-15-…`, `pa-33-agents.md`, `pmm-7/8/12` snapshots, `docs/session-1-inventory` (наша).

**Коллизия нумерации при восстановлении:** в main `010` = client_passport, в PA-03-02 `010` = promotion_attempt_completion, в pa41 `010` = phase3_promotion_privileges, в pa-9 `007` = preview_order_counts (в main `007` = quality_lineage). Ledger additive-only с sha256 - потребуется перенумерация как в `ad89513`.

Прочие источники: `raw/` - сервер `/srv/proxima-ai/data/raw/project-activity/…` (побайтно); `build/reports/*.html` - регенерация `build_dashboard.py`; `build/architecture/*` - `make architecture`; `services/collector/dist` - `npm run build`; серверные скрипты §3.2 - только `scp` с сервера (read-only).

## 5. Писать заново (никогда не существовало ни в одном ref)

| Что | Кто ссылается | Замечание |
|---|---|---|
| `tools/node_repl_server.js` | `opencode.json` (`mcp.node_repl.command`), `.codex/config.toml` `[mcp_servers.node_repl]` (без command - ждёт `~/.codex/config.toml`), `CLAUDE.md:7`, `tools/verify_agent_toolset.py:26,93-95` | `git log --all -- tools/node_repl_server.js` пусто; в архиве `ls tools` без repl. Для opencode MCP `node_repl` не стартует. Либо написать, либо убрать из `opencode.json` |
| `services/webapp/drizzle/` (миграции `webapp_auth`) и роли `webapp_readonly` / `webapp_auth_writer` в `db/migrations` | `services/webapp/README.md:56`, `src/lib/db/client.ts`, WEB-STATE §4 | `/api/auth/get-session` → 500 (WEB-STATE) |
| Писатели `source_artifacts`, `artifact_manifests`, `intake_attempts` (002) | `db/migrations/002`, `contracts/source-artifact.schema.json` | 0 строк на сервере; интейк пишет ФС-манифесты. Либо ETL манифест→БД, либо списать таблицы |
| Писатели `release_attempts`, `release_promoted_facts`, `domain_release_pointers` (008) | `.planning/phases/03-…/03-03-PLAN.md`, `03-04-PLAN.md` | планы 03-03/03-04 не выполнялись ни в одной ветке |
| `docs/evidence/`, `docs/agent-system/evidence/` | `docs/exec-plans/active/w1-slice-exit-criteria.md`, `docs/agent-system/WORKFLOW.md` | каталоги evidence обещаны, не созданы |
| `docs/operations/incident-playbook.md` | `.planning/STATE.md` | - |
| `contracts/authority-map.yaml`, `services/collector/{migrations/, scripts/scheduler.ts, src/sources/{manual-wb,torgstat,wb-statistics}}` | `.planning/research/ARCHITECTURE.md` (12.08) | проект архитектуры, реализация пошла другим путём (`src/intake`, `src/business-signal`, `db/migrations`); ссылки исторические |
| Расписание ежедневного сбора (cron/timer) | INVENTORY §c, флаг 3 | не потеря миграции - никогда не было |
| `.env.example` для webapp (`WEBAPP_*`, `BETTER_AUTH_*`) и `PROXIMA_TEST_POSTGRES_DSN` | §7.3 | имена задокументированы только в README/compose |

## 6. Секреты в истории git (без значений)

Скан: архив `git log --all <27 dangling> -p` (258 коммитов + dangling, 45 remote + 27 local refs) и клон `git log --all -p` (276 коммитов, 46 refs), 12 паттернов (JWT `eyJ…{40,}`, AKIA, PRIVATE KEY, ghp_/github_pat_, `password[=:]`, `postgres://u:p@`, `sk-`, `xox[bpa]-`, AIza, telegram `\d{8,10}:…{35}`, AGE-SECRET-KEY, `api_key/secret_key/access_token[=:]…{24,}`), только добавленные строки; вывод маскирован (4 символа + длина).

| Путь | Коммит | Дата | Автор | Тип паттерна | Значение (4 симв./длина) | Статус |
|---|---|---|---|---|---|---|
| `infra/bootstrap/prepare-business-signal-runtime.sh` | `20ea8cf` | 2026-08-13 | Mike Zhamba | `password =` | `path…` / 45 | в HEAD; **код** `password = pathlib.Path(sys.argv[2]).read_text(...)` - не секрет |
| `infra/bootstrap/provision-postgres-diagnostics.sh` | `54c4cb1`, `8962f36` | 2026-08-15 | Mike Zhamba | `password =` | `Path…` / 37 | в HEAD; **код** `password = Path(sys.argv[1]).read_text(...)` |
| `tools/wb_async_report.py` | `d1e819f` | 2026-08-13 | Mike Zhamba | `password =` ×2 | `read…` / 21, `pass…` / 9 | в HEAD; **код** `password = read_secret(Path(env[...]))`, `password=password` |
| `AGENTS.md` | `16e2799`, `771372f`, `e04cda9`, `aa9afcd`, `df5ebbb` | 2026-08-16 | Mike Zhamba | `postgresql://u:p@` | `<pas…` / 10 | в HEAD; **плейсхолдер** `postgresql://<user>:<password>@localhost:5433/<db>` |

Совпадений по остальным 10 паттернам: 0. Файлы с «секретными» именами, когда-либо добавленные (`--diff-filter=A -- '*.env' '.env*' '*.pem' '*.key' 'id_*' '*token*' '*secret*' '*credential*'`): `services/collector/src/business-signal/secrets.ts` (`0d5b950`, 13.08 - код чтения секретов), `tools/secret_scan.py` (`f67401a`, 12.08 - сканер), `.autopilot/2026-08-25-pa49-warm-precision/tickets/01-tokens-fonts-primitives.md` (`12651e4`, 26.08 - дизайн-токены). История `.env`, `.env.task`, `.env.local`: пусто. `.gitignore` main содержит `.env`, `.env.*`, `secrets/`, `raw/`, `build/`, `logs/`.
Каталоги HEAD `_bmad`, `_bmad-output`, `.openhands`, `provenance`, `.codex`, `.claude`, `.opencode`, `.agents`, `.autopilot`, `infra` - grep по тем же паттернам: 0. Единственная «привязка к машине»: `opencode.json` с абсолютным путём `/Users/mikezhamba/.local/bin/npx` (`8d0932e`, 29.08) - не секрет.
**Вердикт:** переписывать историю не требуется; ротация по итогам скана не требуется. Вне git остаются флаги INVENTORY §4.7 (`~/.git-credentials` на сервере, analytics-токен RW, PA-13) - без изменений.

## 7. Косвенные признаки (пункт C)

### 7.1. Импорты - чисто
- TS (`check_ts_imports.py`, 30.08): `services/collector/{src,tests}` + `services/webapp/src` = 90 файлов, 182 относительных/`@/` импорта, 0 без цели. `npx tsc --noEmit -p services/collector` → exit 0 (~1 с; `tsconfig.json` + `tsconfig.build.json` есть, `node_modules` в корне workspace, 464 пакета). Webapp `tsc` зелёный по WEB-STATE §5.
- Python (`check_py_imports.py` на 3.14 из venv архива, ast): `services/control-plane/{src,tests,evals}`, `tools`, `scripts`, `infra` = 58 файлов, 0 неразрешённых локальных импортов, 0 неизвестных модулей.

### 7.2. Конфиги → пути
| Конфиг | Ссылка | Статус |
|---|---|---|
| `opencode.json` | `tools/node_repl_server.js` | **отсутствует везде** (§5) |
| `.codex/config.toml` | `[mcp_servers.node_repl]` без command | ожидается user-level `~/.codex/config.toml` (комментарий 27.08 в файле); `verify_agent_toolset.py` проверяет только codex-конфиг |
| `.openhands/hooks/verify-gate.sh` | `./.env.task` | серверный, есть в `/srv/openhands/workspaces/proxima-ai/tasks/*/.env.task` (INVENTORY §i) |
| `infra/bootstrap/prepare-*.sh` | `data/{business-signal,day1-wb-api,wb-analytics-spool}` | `/srv/proxima-ai/data/…` есть, два последних пусты (INVENTORY §g) |
| `infra/compose.yaml` | `${PROXIMA_SECRETS_DIR}/postgres_{user,password}`, `db/migrations → /docker-entrypoint-initdb.d` | `/etc/proxima-ai/secrets/` есть; на сервере смонтирован чекаут `/srv/proxima-ai/repo` с 001-006 (флаг 2) |
| `infra/webapp.compose.yaml` | `./Caddyfile`, `services/webapp/Dockerfile`, `/etc/proxima-ai/secrets/` через env_file | файлы есть; Caddy не развёрнут (флаг 5) |
| `infra/glitchtip.compose.yaml` | `./manage.py`, `/srv/proxima-ai/glitchtip/docker-compose.yaml` | путь внутри контейнера / серверный, есть |
| `infra/monitoring/*.service` | `/usr/local/lib/proxima-ai/host_monitor.py`, `/etc/proxima-ai/monitor.env`, `/var/lib/proxima-ai-monitor` | есть (INVENTORY §c) |
| `Makefile`, `.mcp.json`, `.github/workflows`, `.githooks` | внутренние пути | все существуют |

### 7.3. Env-переменные
Читает код: TS - `WEBAPP_REQUIRE_AUTH`, `WEBAPP_DATA_DATABASE_URI`, `DATABASE_URI`, `WEBAPP_AUTH_DATABASE_URI` (`requiredEnv`), `CI` (`tools/*.mjs`); Python - `WB_{STATISTICS,ANALYTICS,FINANCE,PRICES,PROMOTION}_TOKEN_FILE`, `PROXIMA_RAW_DIR`, `PROXIMA_SPOOL_DIR`, `POSTGRES_{USER_FILE,PASSWORD_FILE,HOST,PORT,DB}` (`wb_api_probe.py`, `wb_async_report.py`), `PROXIMA_MONITOR_{CONTRACT,STATE_FILE}`, `PROXIMA_TELEGRAM_{TOKEN_FILE,CHAT_ID_FILE}` (`host_monitor.py`), `PROXIMA_LLM_API_KEY` (имя настраиваемое, `diagnosis/config.py`), `PROXIMA_TEST_POSTGRES_DSN` (`tools/tests/*postgres*.py`, `test_runtime_roles_schema.py`, `pg_local_roundtrip.sh`).
Примеры/доки: `infra/runtime.env.template` (12 имён = серверный `.env` по INVENTORY §i), `infra/monitoring/monitor.env.example` (4), `services/webapp/README.md` + `infra/webapp.compose.yaml` (`WEBAPP_*`, `BETTER_AUTH_{SECRET,URL}`), `AGENTS.md` (`DATABASE_URI`, `PROXIMA_LLM_API_KEY`).
Расхождения: (1) `PROXIMA_TEST_POSTGRES_DSN` - ни в одном примере/README; (2) `PROXIMA_SECRETS_DIR`, `PROXIMA_POSTGRES_PORT` (compose) - не в README; (3) фантомы в `AGENTS.md` T2: `AUTH_SECRET`, `AUTH_DATABASE_URI` - в коде `BETTER_AUTH_SECRET`, `WEBAPP_AUTH_DATABASE_URI`; (4) `WEBAPP_DATA_MODE` - только в `ai/pa-50`; (5) `WB_PRICES_TOKEN_FILE`, `WB_PROMOTION_TOKEN_FILE` указывают на отсутствующие файлы (INVENTORY 7c).

### 7.4. Ссылки в документации на отсутствующие файлы
`check_doc_refs2.py`: 167 md вне vendor (`.agents/`, `_bmad*`), 491 ссылка с `/`, 87 не резолвятся напрямую; после резолва относительно `services/{webapp,control-plane,collector}` (AGENTS.md и autopilot-спеки пишут пути без префикса) реально отсутствуют:
- на ветке `pmm29-contracts`: `contracts/{signal,diagnosis,decision-record}.schema.json` ← `.autopilot/2026-08-28-pmm29-contracts--wip/manifest.md`;
- никогда не существовали: §5 (`docs/evidence/`, `incident-playbook.md`, `authority-map.yaml`, `services/collector/{migrations,scripts,src/sources}`, `services/webapp/drizzle/`), плюс `tests/integration/model_contract/test_model_adapter.py`, `tests/unit/ai/test_review_boundary.py` ← `docs/audits/pa-39-scenario-engine-audit.md` (описывает исходный репо Опрос-v2.2, не этот);
- устаревшие имена: `.autopilot/2026-08-27-release-cutter--wip/` → фактически `2026-08-27-release-cutter/` (`docs/release-gates/2026-08-27-pmm-7-dry-run.md`); `docs/02-wbs-catalog.md`, `docs/03-issue-templates.md` ← `docs/exec-plans/active/pm2-backlog-run.md` (внешняя папка `Downloads/ai-marketplace-os`);
- только на сервере: `services/webapp/Dockerfile.staging` (WEB-STATE);
- ожидаемые в этой сессии: `docs/state/{MIGRATION-GAPS,BACKLOG-REVIEW,WORKS-TODAY}.md`, `docs/archive/planning-m1/`.

### 7.5. История git - чисто
Начало: `10e8752 2026-08-12 Initial commit` (Mike Zhamba), без grafts/shallow; 223 коммита в main, 276 во всех refs. Удалений в main за всю историю - 3 файла: `services/webapp/src/components/shell/app-topbar.tsx` (`acced0c`, т02), `components/module-placeholder.tsx` (`8ae0f44`, т04) - заменены в PA-49; `CLAUDE.md~16e2799…` (`4c1db07`, 16.08, бэкап-артефакт). Snapshot-коммиты 29.08 в main: `980e186`, `8f543b5`, `8d0932e`, `78f65c4` (324 файла, BMAD pack - самый большой), `4fac6c4`, `e52059d`, `50ae00c`; на ветках - 5 «pre-freeze» + `ddefed6`, все на origin.

### 7.6. Миграции vs таблицы БД
- `001-006` создают ровно 13 таблиц = 13 в `proxima` (INVENTORY §d): `schema_migrations`, `tenants`, `source_artifacts`, `artifact_manifests`, `intake_attempts`, `wb_analytics_report_tasks`, `wb_analytics_quota_events`, `raw_wb_analytics_responses`, `dim_product`, `dim_warehouse_map`, `business_signal_runs`, `business_signal_raw_artifacts`, `stg_wb_nm_report_rows` (006 - только ALTER).
- В миграциях, но не в БД (`schema_migrations` = 1-6): `007` `fact_attempt_runs`, `stg_quarantine_rows`, `fact_order_counts`, `fact_lineage_records`, `quality_check_results`; `008` `release_attempts`, `release_promoted_facts`, `domain_release_pointers` + 3 view `public_order_counts_{operational,inventory,financial}`; `009` 4 роли `proxima_*` + 24 RLS-политики; `010` `dim_client_passport`, `stg_supply_plan`. Итого 10 таблиц.
- В БД без миграции: 0.

### 7.7. Таблицы без записывающего кода (main, без тестов; `check_table_writers.py`)
Пишут: `business_signal_runs`, `business_signal_raw_artifacts` ← `services/collector/src/business-signal/repository.ts`; `dim_product`, `dim_warehouse_map`, `dim_client_passport`, `stg_supply_plan`, `tenants` ← `business-signal/config.ts` (seed CLI); `wb_analytics_report_tasks`, `wb_analytics_quota_events`, `raw_wb_analytics_responses`, `stg_wb_nm_report_rows`, `tenants` ← `tools/wb_async_report.py`; `schema_migrations` ← INSERT в самих `001-010`.
**Не пишет никто (11):** `source_artifacts`, `artifact_manifests`, `intake_attempts` (интейк пишет ФС; 0 строк на сервере); `fact_attempt_runs`, `stg_quarantine_rows`, `fact_order_counts`, `fact_lineage_records`, `quality_check_results` (писатель - только на ветках PA-03-02 / pa41, §4); `release_attempts`, `release_promoted_facts`, `domain_release_pointers` (писателя нет ни в одном ref).

## 8. Приложение: команды (все 30.08.2026, клон `~/Desktop/Проекты/Proxima/proxima-ai`, архив `$A`)

- A: `git fetch origin feat/pa-49-warm-precision ai/pa-50`; `git log --oneline origin/main..origin/feat/pa-49-warm-precision` (пусто) и обратное (57 коммитов); `git merge-base`; `git diff --name-status origin/feat/pa-49-warm-precision origin/main` (59 A / 25 M / 1 R, +4961/-42); `git log --oneline origin/main..origin/ai/pa-50`; `git diff --stat|--name-status origin/main...origin/ai/pa-50`; `git show origin/ai/pa-50:services/webapp/src/lib/data/{postgres-provider,index}.ts`; свип `for b in $(git branch -r)`: `git rev-list --count origin/main..$b`, `git cherry origin/main $b`, `git diff --name-only origin/main...$b`, пофайлово `git cat-file -e origin/main:$f` / `git diff --quiet origin/main $b -- $f`.
- B: `git -C "$A" status --short --ignored`; `git -C "$A" branch -a`; `git -C "$A" stash list` (пусто); `git -C "$A" reflog`; `git -C "$A" fsck --lost-found`; `git -C "$A" log --all --oneline -- raw build` (пусто); `git -C "$A" diff --stat <dangling>^1 <dangling>`; построчное сравнение добавленных строк с `git show origin/main:<file>`; `du -sh`, `find … -exec stat -f '%z %Sm %N'`; `ssh proxima 'ls -la …/raw/project-activity/…; stat events.json; find … -name "proxima-ai-activity-*.html"; ls Dockerfile.staging; git -C /srv/proxima-ai/repo log -1 pa30-stage'`.
- C: `scratchpad/check_ts_imports.py`, `check_py_imports.py` (venv 3.14 архива), `check_doc_refs2.py`, `check_table_writers.py`; `npx tsc --noEmit -p services/collector`; grep `process.env` / `os.environ|getenv` / `"[A-Z_]+_(TOKEN|FILE|URI|DIR|…)"`; grep путей в `infra/*.yaml`, `Makefile`, `opencode.json`, `.mcp.json`, `.codex/config.toml`, `.openhands/*`, `.github/workflows/*`; `git log --diff-filter=D --name-only origin/main`; `git log --reverse | head -5`; `git rev-list --count`; `git log --shortstat | sort`; `grep -niE 'create (table|view|role|policy)' db/migrations/*.sql`; `git log --all -- <missing-path>`.
- D: `git log --all $(git fsck --lost-found | awk '/dangling commit/{print $3}') -p --format='COMMIT\t%h\t%ad\t%an\t%s' | scan_secrets.py` (архив; первый прогон дал 0 из-за zsh-разбиения аргумента - перезапущен), то же `--all` в клоне; `git log --all --diff-filter=A --name-only -- '*.env' '.env*' '*.pem' '*.key' 'id_*' '*token*' '*secret*' '*credential*'`; `git log --all -- .env .env.task .env.local`; `grep -rnIE <12 паттернов>` по `_bmad _bmad-output .openhands provenance .codex .claude .opencode .agents .autopilot infra` с маскированием; проверка совпадений: `git show <hash>:<file> | grep -n password` с обрезкой после 4 символов.
