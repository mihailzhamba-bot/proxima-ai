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

Права на запись во внешний мир живут **не здесь**, а в трёх sudo-обёртках на сервере
(`/usr/local/sbin/proxima-git-push`, `proxima-pr`, `proxima-pr-merge`, root 0700):
ключ деплоя и PAT доступны только root, обёртки запрещают force-push, правки
`.github/workflows/**`, ветки вне `feat|fix|docs|chore/*` и мерж при некрасном CI.

Ручной прогон одного шага (для отладки, с сервера):

```bash
sudo -u openhands-agent tools/orchestrator/worker_status.sh <conversation-id>
```
