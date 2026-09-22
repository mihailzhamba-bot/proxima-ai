# Бриф Codex-ревью: коммит `ca8a67e` (публичный контур 2.6, D42 §3b)

**Статус:** не блокер. Ветка уже запушена; ревью выполняется по `main` после merge либо по ветке `docs/d42-grill-plan`. Фиксы - обычными PR; merge/деплой ревьюер не делает.

## Что это

Коммит вводит публичный HTTPS-контур релиза 2.6 (D42, 21.09): auth-сторону базы, боевой webapp-overlay, правку vps-контракта и гейта, репетиционный Caddyfile. Затронутые файлы:

- `infra/bootstrap/provision-runtime-roles.sh` - шестая роль `proxima_webapp_auth_writer`, схема `webapp_auth`, 4 таблицы (идемпотентно, вне M1-ледеря), гранты, секреты `proxima_webapp_auth_writer_password`/`proxima_webapp_auth_uri` (1001:1001);
- `infra/webapp.compose.yaml` - postgres-режим через `WEBAPP_DATA_DATABASE_URI_FILE` + secrets; `BETTER_AUTH_SECRET`/`WEBAPP_AUTH_DATABASE_URI` через `env_file: /etc/proxima-ai/secrets/webapp_auth.env`;
- `infra/vps-contract.json` + `tools/verify_vps_contract.py` - `caddy_https`, tcp/22+80+443;
- `infra/Caddyfile.rehearsal` - `tls internal` для стенда;
- `tools/rehearsal_run.sh` (строка гейта «6 login roles»), тесты `test_provision_runtime_roles.py`, `test_webapp_public_contour.py`, доки `release-m03.md` §3b / `release-m01.md`.

## Где проверять (вопросы ревью)

1. **SQL-корректность и идемпотентность DDL**: колонки `provision-runtime-roles.sh` (блок `webapp_auth`) 1-в-1 с `services/webapp/src/lib/db/schema.auth.ts` (имена snake_case, кавычки `"user"`, FK `ON DELETE CASCADE`, уникальные email/token); повторный прогон - no-op; `\gexec`-гранты подхватывают ровно 4 таблицы.
2. **Минимальность грантов (AD-12)**: у `proxima_webapp_auth_writer` нет ничего в `public` и в тестовой базе; CONNECT выдан явно; нет членства в ledger-группах.
3. **SCRAM-путь**: пароль auth-роли проходит тот же `read_or_create_password`/`scram_verifier` конвейер; значение не печатается (см. `echo`-строки).
4. **Overlay и секреты**: `WEBAPP_DATA_DATABASE_URI` (плоский) отсутствует; auth-URI идёт env_file - подтвердить, что better-auth (`src/lib/auth.ts`, `src/lib/db/client.ts`) читает именно `WEBAPP_AUTH_DATABASE_URI` и `BETTER_AUTH_SECRET` из окружения; `env_file` с абсолютным путём при отсутствии файла должен валить `up` fail-closed (проверить поведение compose v2).
5. **Гейт контракта**: `verify_vps_contract.py` и JSON не разъезжаются; revert-путь §3b возвращает tcp/22-only.
6. **Caddyfile.rehearsal**: не протекает в бой (монтируется только явным override репетиции), `tls internal` только там.
7. **Покрытие**: чего не хватает в `test_webapp_public_contour.py`.

## Чего НЕ делать

Не мержить, не деплоить, не трогать серверы (VPS/mckenzie недоступны и не нужны), не менять код - только отчёт с findings (blocker/major/minor) и, при желании, ветка с фиксами.
