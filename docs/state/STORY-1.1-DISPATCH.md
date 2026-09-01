# Story 1.1 - пакет запуска в OpenHands

Готовый промт единицы для `bmad-build-auto`. Запуск - только после мержа PR #36 (`feat/m01-step0`, Story 1.0) и явного «гоу» от Mike в чате.

## Как запускается

- OpenHands на VPS, доступ с мака через ssh-туннель `com.proxima.openhands-tunnel` (UI/API `http://localhost:8000`).
- API-ключ: переменная в `/home/openhands-agent/.agent-canvas.env` на VPS (заголовок `X-Session-API-Key`). Значение никуда не выводить (D5/Policy).
- Рабочая ветка исполнителя: `feat/m01-story-1.1` от свежего `origin/main` (уже содержащего Story 1.0).
- Исполнитель = OpenHands-сессия со скиллом `bmad-build-auto`; промт сессии = раздел «Промт единицы» ниже целиком.

## Промт единицы

### Задача (epics.md, Story 1.1)

As a оператор конвейера, I want чтобы единственный WB-клиент с бюджетами лимитов, приёмником артефактов и тестами на фикстурах прошёл все 10 шагов конвейера, So that следующие единицы шли по проверенному пути.

**Given** `services/collector/src/wb/{client,transport,fixture-transport,artifact-sink,msk-day}.ts` по AD-4/AD-7: реестр эндпоинтов и бюджетов, `ArtifactSink` (интерфейс) + in-memory реализация для тестов (БД-реализация `WbArtifactSink` и `recording-client.ts` - в Story 1.3), токены через CLI-флаги `--<category>-token-file` по образцу `stockout-signal.ts`; `tools/record_fixture.ts` (артефакт → обезличенная фикстура через `tools/anonymize_fixture.py`)
**When** `make verify`
**Then** новый гейт `tools/verify_wb_client.py` проходит: URL WB только в реестре; реестр = `statistics.orders` (10/мин), `statistics.sales` (1/мин), `analytics.sales_funnel_v3_history` (3/мин), `analytics.nm_report_downloads` (3/мин); `reportDetailByPeriod`/`supplier/stocks` отсутствуют; `setInterval`/`node-cron` не встречаются в `src/**`; `tools/verify_business_signal.py` не изменён
**And** тесты через `FixtureTransport` при незаданных токенах: 429 ждёт по `X-Ratelimit-Retry`, сдаётся после 3 повторов; бюджет не допускает второй `sales` раньше 60 с (виртуальные часы); сетевой вызов падает; `mskDay('2026-08-29T23:30:00Z') = 2026-08-30`, `mskDay('2026-08-29T20:59:59Z') = 2026-08-29`

### Обязательные решения (спайн, читать целиком в `_bmad-output/planning-artifacts/architecture/architecture-proxima-ai-2026-08-30/ARCHITECTURE-SPINE.md`)

- **AD-4** (один WB-клиент, сеть в тестах запрещена): собственная тонкая обёртка с тем же порядком, что `business-signal/http.ts` (артефакт до проверки статуса, allowlist заголовков), переиспользующая `raw-store.ts` и `fetchTransport`; `RecordedHttpClient` и его `SignalRepository` не трогаются. Транспорт и приёмник инжектируются. 429 - ожидание по `X-Ratelimit-Retry`, ≤ 3 повторов. `FixtureTransport` читает `services/collector/tests/fixtures/wb-api/<api>/<endpoint>/*.json`. В тестовом окружении `WB_*_TOKEN_FILE` не заданы - сетевой вызов падает.
- **AD-7** (время в одном месте): `calendar_day` = дата WB `date` в `Europe/Moscow` через единственный helper `mskDay()`; тест на границу полуночи; моменты - `TIMESTAMPTZ`.

### Правила репо (AGENTS.md, обязательные)

- Тесты только на фикстурах; живой WB API в этой истории не вызывается вовсе.
- `services/collector/src/contracts/*.ts` не редактировать (генерятся `make codegen`); миграций в этой истории нет - `db/migrations/` не трогать.
- Стейджить только свои файлы (`git add <files>`, не `-A`); коммиты - английский, conventional-префикс.
- Секреты: значения токенов нигде не появляются; тесты работают без токенов.
- Гейт: `PUPPETEER_SKIP_DOWNLOAD=1 make verify` зелёный целиком, включая новый `verify_wb_client: PASS` и неизменность `tools/verify_business_signal.py`.

### Definition of Done единицы

PR открыт из `feat/m01-story-1.1`, `make verify` зелёный в CI, все AC выше выполнены. Дальше конвейер (вне сессии исполнителя): `bmad-code-review` → e2e-тесты на фикстурах → прогон `WORKS-TODAY.md` → приёмка Mike (одно действие: `make verify` → `verify_wb_client: PASS`) → мерж + тег `v2026.09.NN-1` + `CHANGELOG.md` → безопасный «деплой» AR11 п.1 (restore `origin` у `/srv/proxima-ai/repo`, тег `v2026.09.0-baseline` как точка отката, checkout тега; код не исполняется) → наблюдение сутки → Jira. Документ релиза: `docs/operations/releases/2026-09-NN-m01-1.md`.
