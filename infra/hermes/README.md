# Мозг Дирижёра в Hermes

Копии того, что развёрнуто вне репозитория (сервера меняются вручную, здесь - истина о содержимом).

| Файл здесь | Где стоит | Назначение |
|---|---|---|
| `proxima-conductor.skill.md` | Skystark 153.56.134.240: `/home/hermes/.hermes/skills/` (в контейнере `/opt/data/skills/`) | Роль Дирижёра для Hermes: глаголы CLI, ритм, когда спрашивать Mike, чего нельзя |
| `hermes-conductor-poll.sh` | Skystark: `/usr/local/sbin/hermes-conductor-poll` + таймер `hermes-conductor-poll.timer` (10 мин) | Будильник: опрашивает конвейер, при событиях пишет Mike в Telegram ботом Hermes (токен не покидает контейнер) |
| `proxima-conductor-cli.sh` | proxima 135.106.186.210: `/usr/local/sbin/proxima-conductor-cli` | SSH forced command: валидирует глагол и аргументы, вызывает `tools/orchestrator/conductor_cli.py` |

## Канал

Hermes (другая машина) → SSH-ключ `hermes_conductor` → пользователь `openhands-agent` на proxima → **только** forced command. В `sshd_config.d/00-proxima-ai.conf`: `AllowUsers proxima-admin openhands-agent@153.56.134.240`; в `05-hermes-conductor.conf` для этого пользователя `ForceCommand`, `PermitTTY no`, форвардинги выключены.

Проверено боем 01.09.2026: `status` отдаёт JSON; `ls /` → `verb not allowed`; `queue; cat /etc/passwd` → `illegal characters`; интерактивный shell → `empty command`; `dispatch 1.14` (история `[Claude]`) → `story not dispatchable`.

## Отзыв доступа

```bash
ssh proxima 'sudo -u openhands-agent sed -i "/hermes-conductor/d" ~/.ssh/authorized_keys'
ssh -p 65022 root@153.56.134.240 'systemctl disable --now hermes-conductor-poll.timer'
```

Запасной мозг (conversation Дирижёра на самой proxima) при этом остаётся рабочим - см. `docs/agent-system/ORCHESTRATOR.md`.
