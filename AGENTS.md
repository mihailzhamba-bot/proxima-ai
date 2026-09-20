# AGENTS.md - PROXIMA AI (публичная версия)

Единый контракт для coding-агентов (Claude Code / Codex / opencode) и людей-контрибьюторов.

> **Композит.** Полная рабочая версия этого файла (с серверными деталями и внутренними правилами) живёт в приватном ops-репозитории `proxima-ai-ops` и подключается симлинком. Если `docs/` и `_bmad-output/` в дереве - ты работаешь в композите и видишь полную картину. Если нет - это публичный чекаут: код + CI, доков нет.

## Что это за проект

Платформа WB-кабинетов: сбор данных по WB API → PostgreSQL → утренняя сводка с отклонениями в веб-морде. TypeScript collector (`services/collector`), Python control-plane (`services/control-plane`, uv 3.14), Next.js webapp (`services/webapp`), PostgreSQL 16.

## Policy (непреложное)

1. **Значения токенов, паролей, ключей никуда не выводить** - ни в лог, ни в отчёт, ни в коммит; только имя переменной или файла. Секреты не живут в репозитории.
2. **WB API только READ.** Любая мутирующая операция против WB - архитектурное нарушение.
3. **Не выдумывать данные.** Никаких фиктивных cabinet ID, SKU, цен, порогов; в тестах - структурные фикстуры с обезличенными значениями. Демо-данные webapp - только из `src/lib/fixtures/` с префиксом `fixture-`.
4. **LLM не считает метрики**: цифры - детерминированный код; каждый факт со SourceRef; reviewer блокирует unsupported claims.
5. **Destructive ops** (`rm -rf`, `git push --force`, `drop table`, `reset --hard`) - только с явного подтверждения владельца.
6. **Hygiene-гейт** (`make hygiene`) обязан быть зелёным: публичное дерево не содержит боевых IP, имён кабинетов, внутренних хостов. Файл с such данными = красный verify.
7. **Один write-capable агент на рабочее дерево**; параллельно - только read-only исследование. Стейджить только свои файлы.

## Контракты и кодогенерация

- Схемы контрактов: `contracts/*.schema.json` (канонические, JSON Schema Draft 2020-12).
- TS-типы генерируются `make codegen` в `services/collector/src/contracts/` - **не редактировать руками**, перегенерировать.
- Миграции `db/migrations/NNN_*.sql` не править и не переименовывать - только новая `NNN+1_<snake>.sql`, additive-only, `BEGIN…COMMIT`, self-checksum (`tools/verify_migrations.py`).
- Каждая запись в БД помечена `run_id`, идемпотентна и удаляется по `run_id` целиком - требование к любому новому писателю.

## Verify

```bash
make verify
```

Единый exit-code: install + codegen + typecheck + webapp lint/test + collector tests + contracts + migrations + pg-roundtrip + provenance + architecture* + boundary + secrets scan + hygiene + vps-contract* + business-signal + wb-клиенты. (* = выполняются, когда рядом есть `docs/` из ops-репо; в CI на публичном репо пропускаются.)

- `PUPPETEER_SKIP_DOWNLOAD=1` перед `npm ci` / `make verify`, иначе качается Chromium.
- Без локального PostgreSQL 16 шаг `pg-roundtrip` даёт `SKIP` с exit 0 - миграции не проверены.
- Python только через uv: `uv run --python 3.14 --project services/control-plane --extra test pytest services/control-plane/tests tools/tests`.
- Один vitest-файл: `npm --workspace @proxima/webapp exec -- vitest run src/tests/<file>`.
- `next build` переписывает tracked `services/webapp/next-env.d.ts` - после сборки `git checkout -- services/webapp/next-env.d.ts`.

## Conventions

- Коммиты - английский, conventional-префиксы (`feat(webapp): …`, `fix: …`); атомарные, описательные.
- Collector тестируется `node:test` через `tsx` (`services/collector/tests/`), webapp - vitest (`services/webapp/src/tests/`); jest нигде.
- Идентификаторы кода - английский; общение - русский.
- Заморожено: auth-зона webapp (`src/lib/auth*`, `src/app/api/auth/`, `src/app/login/`) и verbatim-дерево `services/control-plane/src/proxima/` - изменения только через владельца.
- Чужой код - только через `provenance/import-inventory.json` + attestation (`make provenance`); Torgstat и браузерная автоматизация в runtime запрещены (`tools/verify_runtime_boundary.py`).

## Замечание о внутренностях

Серверная топология, имена хостов, IP, операционные процедуры, планирование и решения - в приватном `proxima-ai-ops`. Попытка закоммитить их сюда будет остановлена hygiene-гейтом; обнаружил утечку - сообщи владельцу, не «чинь сам».
