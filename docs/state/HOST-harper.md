# HOST-HARPER - карта машины harper (135.106.211.64)

**Дата:** 22.09.2026. **Кто:** opencode (гриль + аудит + autopilot-ран `2026-09-22-host-harper-audit`). **Метод:** инспекция read-only + полная локальная верификация; секреты не читались; живых WB-вызовов не было; VPS и LOOP-control не тронуты. Дополняет `INVENTORY.md` (тот описывает VPS claudette).

## 1. Роли машины

1. **Mainline-точка:** чекаут `/root/loop-install/proxima-ai`, на 22.09 - ветка `docs/d42-grill-plan` (D42). Здесь решения 21.09 были написаны и отсюда идут в `main`.
2. **LOOP-верификатор** (схема contour-v2, `docs/operations/contour-v2-deploy.md` в LOOP-линии): control - mckenzie (Mac mini, 135.106.211.149), worker - claudette, harper - «trusted verification consumer»: юниты `loop-runner.service` (active, `/opt/loop/runner.py`, пользователь `verifier`, sandbox: ProtectSystem=strict, ReadWritePaths=/srv/loop-runner /var/lib/loop-runner, MemoryMax=512M, CPUQuota=50%), `loop-runner-bridge-tunnel.service` (проброс bridge API 127.0.0.1:18771 → mckenzie:18770), `loop-model-relay.service`, `loop-night-guard.timer` (20 с), `loop-night.service` (конечный admitted-батч).

## 2. Состояние двух линий (22.09)

| Линия | Коммит | Верификация | Примечание |
|---|---|---|---|
| mainline `origin/main` | `08043bb` (PR #159 = D41) | **`make verify` PASS полностью** (см. §4) | CI GitHub лежит с 08.09 (биллинг) - приёмка по локальному verify, правило D37 |
| локальная ветка `docs/d42-grill-plan` | `f0b7c6c` (D42) | verify не требуется (docs) | до 22.09 существовала только локально; push - этот ран |
| LOOP `origin/server/loop-continuous` | `15294f5` (PR #157) | офлайн-сюиты: **778 passed** (`pytest tools/tests -k loop`); полный `tools/tests` 1012 passed / 2 failed / 6 skipped | orphan-история, merge-base с main отсутствует |
| локальная `server/loop-continuous` | `8d23519` (PR #149) | - | отстаёт от remote на несколько коммитов |

Два отказа полного прогона LOOP разобраны: (1) `verify_runtime_boundary` - падал без собранного collector (`built import target missing`), после `npm run build --workspace @proxima/collector` - PASS, артефакт порядка сборки, `make verify` его покрывает; (2) `verify_agent_toolset` - **реальный дрейф**: loop head содержит конфиг-фикс #155 (`79115e8`), но не верификатор-фикс #156 (`6513307`), свой гейт красный по 6 MCP-серверам. Синк #156 - задача после 30.09.

LOOP-очередь: последний батч `day-20260916-readiness-r3` завершён 20.09 14:37 (`completed` → `ready_pr` → **PR #145**, base `d5334f2`, head `a6fa928`, ревью glm-5.3-flash/z.ai); состояние `await_new_admitted_batch_manifest`, `automatic_job_admission: false` - легальный простой, ждёт операторского манифеста. Пилотные PR LOOP: #145 (ready), #147 (head `e19d8b4`, из exec-plan T2), #154 (head `26389cc`, sanitized public base по D40); их open/closed статусы с harper не видны (нет gh, приватный репо).

## 3. Карта `/srv` и локальных артефактов

| Путь | Размер | Что это | Вердикт |
|---|---|---|---|
| `/srv/loop-runner/work/` | 8.9G (5×1.5G + tg 514M) | воркспейсы завершённых прогонов (wb-daily-packaging-v2 a1-a1/a1-a3, daily-status-slice-a2, packaging-slice-a3, runtime-v1) | REMOVE/ARCHIVE-кандидат (по mtime, потвждение Mike) |
| `/srv/loop-verification/20260913/` | **21G** | артефакты верификации 13-14.09 | REMOVE/ARCHIVE-кандидат №1 |
| `/srv/loop-runner/evidence/` | 14M, 22 acceptance-файла (2 error) | evidence готовых задач | держать |
| `/srv/loop-runner/{source,release,build-*,continuous-*,fixtures,imports}` | <120M | рабочий контур verifier | держать |
| `/srv/loop-release-staging/` | 1.3M, 10 sha-каталогов | staging кандидатов | пересмотреть после 30.09 |
| `/srv/proxima-verification/` | - | D40 candidate tree (sanitized, 10-12.09) | связан с PR #154, не трогать до решения по PR |
| `/root/v2a1-stale-backup-20260920/` | малый | бэкап batch-state попыток wb-daily-packaging-v2 (attempt-3 `blocked`, причина `run_terminal_or_unknown`) | кандидат в архив после разбора a1-a3 |
| worktrees: `main-audit`, ветка `pr89-update` | - | `fix/agent-toolset-codex-portable` уже в main (#155/#156); pr89-update - helper слитого #89 | REMOVE/ARCHIVE-кандидаты |
| `_bmad-output/party-mode/` в чекауте | 1 файл | untracked memlog скилла | gitignore или удалить |
| ветки `origin/*` | 181 шт. | в т.ч. `feat/loop-*`, `loop-staging/*` | ревизия - P3 |

## 4. Верификация 22.09 (воспроизводимо)

**Mainline `08043bb`, полный `make verify` - PASS, впервые на этой машине с `pg-roundtrip: PASS`:** vitest 120 passed; pytest 455 passed / 23 skipped; contracts, migrations, codegen-diff; pg-roundtrip: initdb disposable cluster, миграции, идемпотентность apply, ledger 18/18, provision ×2 (5 ролей), 25 db-тестов collector, матрицы norm/brief/funnel/nm-daily/detector/RLS; provenance, boundary, secret scan, vps contract, business-signal, wb-client, live-network - PASS.

**Рецепт** (нужен непривилегированный пользователь: `initdb` отказывается работать под root):

```bash
git clone /root/loop-install/proxima-ai /tmp/verify && cd /tmp/verify
git checkout <SHA из таблицы §2>
chown -R verifier:verifier /tmp/verify
runuser -u verifier -- bash -c \
  'cd /tmp/verify && PUPPETEER_SKIP_DOWNLOAD=1 TMPDIR=/tmp PATH=/usr/local/bin:$PATH make verify'
```

После прогона: `git worktree remove`/`rm -rf` на временное дерево (свежий клон, не worktree - linked gitdir ведёт в `/root`, недоступный verifier).

**LOOP-сюиты:** чекаут нужного SHA в scratch-worktree, `PUPPETEER_SKIP_DOWNLOAD=1 npm ci` (без него 3 падения в `test_loop_config.py` на отсутствующих `js-yaml`/`ignore`), затем `uv run --python 3.14 --project services/control-plane --extra test pytest tools/tests -k loop -q`.

## 5. Изменения на машине 22.09 (для отката)

| Что | Зачем | Откат |
|---|---|---|
| `postgresql-16` 16.15 (Ubuntu main), дефолтный кластер на 127.0.0.1:5432 | `initdb` для pg-roundtrip | `apt remove postgresql-16` |
| `/usr/local/bin/uv` (копия бинарника из `/root/.local/bin`) | `uv` недоступен пользователю `verifier` | `rm /usr/local/bin/uv` |
| `/home/verifier/.cache/puppeteer/chrome-headless-shell/linux-151.0.7922.77` | шаг `architecture` (известная ловушка AGENTS.md: `PUPPETEER_SKIP_DOWNLOAD=1` его не ставит) | `rm -rf /home/verifier/.cache/puppeteer` |

## 6. Проблемы и бэклог

**P0** - push `docs/d42-grill-plan` (этот ран). **P1** - этот файл + HANDOFF; шапки RELEASE-READINESS/INVENTORY (сделаны тем же раном). **P2** - чистка из §3 (только по потвждению списка Mike); синк `6513307` в LOOP-линию (после 30.09). **P3** - ревизия 181 remote-веток; статусы PR #145/#147/#154; `git fetch` локальной LOOP-ветки до remote head.

**Пробел D38-D40:** в `DECISIONS.md` обеих линий нумерация идёт D37 → D41; D40 реконструируется из коммитов (sanitized public code base, PR #154), D38/D39 следов нет ни в коммитах, ни в доках; коммиты ссылаются на «ops repo» (`70dd3b2`). Вопрос Mike: где ops repo, если существует.

**EXTERNAL:** LOOP-control (mckenzie) - состояние `UNKNOWN_EXTERNAL`; новый admitted-манифест - решение Mike после 30.09; интеграция LOOP→main - архитектурное решение (orphan-история, нужен graft/патч-перенос), после 30.09; интерактивный ключ `harper-to-mckenzie` (`~/.ssh/id_ed25519_harper_mckenzie.pub`) не добавлен в `authorized_keys` мака - прямая доставка файлов с harper на мак невозможна, только туннельный аккаунт `loop-runner-tunnel` (форвард порта).
