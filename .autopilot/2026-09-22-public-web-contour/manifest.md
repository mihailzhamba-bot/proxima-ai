# Манифест требований

Источник: `2026-09-22-brief.md`. Строку из этого списка может снять **только пользователь**.

| ID | Из брифа (дословно) | Статус | Основание | Где |
|----|---------------------|--------|-----------|-----|
| R01 | «DDL + provision» (П-1: роль `proxima_webapp_auth_writer`, схема `webapp_auth`, 4 таблицы better-auth, гранты только внутри схемы, секреты `1001:1001`) | done | T01 | `infra/bootstrap/provision-runtime-roles.sh`, тест `test_auth_contour_role_schema_and_grants`; живое доказательство - pg-roundtrip `ok (6 login roles)` ×2 |
| R02 | «overlay» (П-2: postgres-режим через секрет-файл, auth-секреты env_file, ноль секретов в `.env`) | done | T01 | `infra/webapp.compose.yaml`, тест `test_webapp_public_contour.py` |
| R03 | «контракт» (П-3: `vps-contract.json` tcp/22+80+443, `caddy_https`) | done | T01 | `infra/vps-contract.json` + `tools/verify_vps_contract.py` (синхронно), тест в том же файле |
| R04 | «Caddyfile.rehearsal» (репетиция 27-28.09: tls internal, без LE) | done | T01 | `infra/Caddyfile.rehearsal`, тест `test_rehearsal_caddyfile_uses_the_internal_ca` |
| R05 | runbook'и не врут: `release-m03.md` §3b «исполнено», `release-m01.md` «6 login roles» | done | T01 | оба файла тем же коммитом |
| R06 | полный гейт ветки зелёный | done | T01 | `make verify` EXIT 0, `pg-roundtrip: PASS` на `ca8a67e` (лог `/tmp/opencode/make-verify-contour.log`) |

Отступления (заявлены): (1) оркестратор писал код сам, без субагента - все факты (поля схемы, форма overlay, гейты) только в его контексте; (2) DDL размещён в provision, а не `services/webapp/drizzle/0001_*.sql`, как сначала писал §3b, - одна истина вместо двух, runbook поправлен тем же коммитом.
