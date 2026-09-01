# tools/orchestrator

Обвязка серверного оркестратора («Дирижёр», см. `docs/agent-system/ORCHESTRATOR.md`).
Скрипты запускаются на VPS под `openhands-agent`; секретов не содержат и не печатают.

| Скрипт | Что делает |
|---|---|
| `lib.sh` | Общие функции: вызов OpenHands API (ключ читается из файла и уходит в curl через `--config` на stdin, не через argv), статус conversation, путь workspace, JSON-лог |
| `launch_worker.sh <branch> <base> <dispatch-file> <fedor\|glm>` | Провижн workspace из canonical-клона бандлом, ветка от base, справочные `docs/state` и `_bmad-output` кладутся untracked, старт conversation выбранным профилем. Печатает id |
| `worker_status.sh <cid>…` | Строка на воркера: статус, события, ветка, число незакоммиченных файлов |
| `send_fix.sh <cid> <message-file>` | Фикс-раунд или resume в живую conversation |
| `collect_branch.sh <cid> <branch> <base> <out.bundle>` | Проверяет, что дерево чистое и коммиты есть, пакует ветку в бандл. Печатает число коммитов |
| `bad_dev_story.sh --run-id … --branch … --base-ref … --prompt-file …` | Шаг 3 конвейера BAD: провижин → dispatch → ожидание → забор → фетч в `refs/openhands/<run-id>/<attempt>/head`. Печатает одну JSON-строку. Не запускается, пока активен таймер Дирижёра. Тесты - `tools/tests/test_bad_dev_story.py` (офлайн, через сеам `BRIDGE_SUDO`/`BRIDGE_AGENT_USER`) |

Права на запись во внешний мир живут **не здесь**, а в трёх sudo-обёртках на сервере
(`/usr/local/sbin/proxima-git-push`, `proxima-pr`, `proxima-pr-merge`, root 0700):
ключ деплоя и PAT доступны только root, обёртки запрещают force-push, правки
`.github/workflows/**`, ветки вне `feat|fix|docs|chore/*` и мерж при некрасном CI.

Отличия `bad_dev_story.sh` от `launch_worker.sh` (сознательные, см. D25):
в песочнице **ноль remote'ов** вместо `origin` на GitHub, перед стартом проверяются
`HEAD == base_sha` и sha256 контрактных файлов, грязное дерево на выходе - ошибка,
а не предупреждение, и входящий диапазон проходит гейты AGENTS.md и секрет-скан.

Ручной прогон одного шага (для отладки, с сервера):

```bash
sudo -u openhands-agent tools/orchestrator/worker_status.sh <conversation-id>
```
