# PROXIMA AI

## What This Is

Канонический приватный монорепозиторий data-платформы Proxima для WB-кабинетов. Milestone 1 строит production-ready read-only data foundation для одного пилотного кабинета (Bogatova Belle Robe): сбор официальных данных WB, иммутабельное хранение с SHA-256-провенансом, нормализация в PostgreSQL, атомарные доменные релизы и Data Health page только для Mike.

## Core Value

Каждый факт в PostgreSQL прослеживается до официального WB-артефакта с контрольной суммой; ни одна неподтверждённая запись не проходит в production-релиз.

## Requirements

### Validated

(None yet - ship to validate)

### Active

#### M1-A: Провенанс и иммутабельное сырьё
- [ ] SHA-256-манифест каждого артефакта (XLSX, gzip JSON) с записью lineage в БД
- [ ] Хранилище raw-артефактов вне Git, монтируется как private Docker volume
- [ ] Инвентаризация импорта из torgstat-collector и proxima-ai-manager: только проверенный код, без секретов/сессий/uncommitted state

#### M1-B: Источники данных WB
- [ ] Импорт официальных ручных WB-выгрузок (XLSX) через intake-пайплайн
- [ ] WB Statistics API - отдельный SecretRef, least-privilege
- [ ] WB Analytics API - отдельный SecretRef, least-privilege
- [ ] WB Finance API - отдельный SecretRef, least-privilege
- [ ] Torgstat-адаптер: опциональный, fail-closed до явного письменного разрешения/официального export approval

#### M1-C: PostgreSQL - схема и релизы
- [ ] Tenant-safe staging: факты поступают в quarantine до прохождения reconciliation
- [ ] Атомарные независимые доменные релизы: operational inventory и financial разделены
- [ ] Release pointer не продвигается при: failed / partial / stale / schema-drift попытке
- [ ] Last-known-good сохраняется при любом сбое; текущий failure экспонируется отдельно
- [ ] Версионированная per-metric authority map (файл + таблица)

#### M1-D: Первая метрика сверки - order_count
- [ ] Гранулярность: cabinet + SKU + calendar_day + Europe/Moscow timezone
- [ ] WB официальный - каноническая сторона; Torgstat - поддерживающая
- [ ] Любое необъяснённое ненулевое расхождение блокирует релиз
- [ ] Initial backfill: 90 дней от даты запуска

#### M1-E: Data Health page
- [ ] Только для Mike: доступ через VPN или SSH-туннель
- [ ] Показывает: источники, попытки, релизы, freshness, reconciliation status, quarantine, lineage → artifact checksum
- [ ] Read-only, нет мутирующих endpoint'ов

#### M1-F: Scheduler и инциденты
- [ ] Сбор 7 дней в неделю; target: данные готовы к 09:00 MSK
- [ ] Bounded retry с экспоненциальным backoff, hard timeout
- [ ] Sanitized Telegram-алерты при инцидентах (без секретов в тексте)

#### M1-G: Инфраструктура
- [ ] Docker Compose на одном VPS: PostgreSQL, workers, app, private volumes
- [ ] Restic + S3-compatible off-site backup, зашифрованный
- [ ] Automated restore test (dry-run при каждом backup-цикле)
- [ ] Raw-evidence не удаляется в течение пилота

#### M1-H: Архитектурные контракты
- [ ] Mermaid-источники в репозитории + рендер в SVG и PDF
- [ ] Кросс-языковые контракты (API/schema contracts)
- [ ] root `make verify` / `just verify` - единая точка входа для CI
- [ ] CI-ready test suite, покрытие каждого vertical slice

#### M1-I: Процесс и gates
- [ ] Каждый vertical slice коммитится независимо и проходит тесты до мержа
- [ ] Каждый slice проходит cross-model deep review: zero blockers, zero warnings
- [ ] GO-gate: Mike утверждает архитектуру перед первой реализацией
- [ ] GO-gate: Mike утверждает первый data release
- [ ] GO-gate: Mike утверждает первую AI-рекомендацию (M2+)
- [ ] GO-gate: Mike утверждает live deploy

### Out of Scope

- **LLM runtime** - исключён из M1 явно; SCN-001..SCN-008 сохраняются как кандидаты для будущей валидации
- **Ozon** - вне пилота; архитектура должна быть tenant-safe, но Ozon-адаптер не пишем
- **Advertising APIs** - WB рекламные endpoint'ы не подключаем в M1
- **Client-facing UI** - Data Health page только для Mike; внешний UI в M2+
- **WB WRITE operations** - любые API с мутирующим эффектом запрещены; fail-closed по дизайну
- **Live session-based automation (Torgstat)** - до явного письменного разрешения не активируем; адаптер компилируется но не запускается
- **Fabricated test data** - нельзя использовать придуманные cabinet ID, connection ID, credentials, пороги, цены, издержки, исходы
- **Деструктивные изменения Linear** - issues от 2026-08-12 - legacy history; новая rebaseline-иерархия создаётся без перезаписи

## Context

**Пилот:** Wildberries-кабинет Bogatova Belle Robe. Один кабинет, один пилот, одна метрика сверки - намеренно узко для верификации data contract перед масштабированием.

**Sibling-репозитории (проверено локально 2026-08-12):**
- `torgstat-collector`: `/Users/mikezhamba/Desktop/MILV/03-startups/!Proxima/PRoxima/Торгстат-автоматизация/torgstat-collector`, clean tracked baseline `610169a6bd3253fa351fa6fbe4ff571d4f4d5539`; поверх baseline лежит owner-owned dirty worktree с PostgreSQL/ETL/ops файлами. Источник не изменять и не коммитить. Импортировать tracked baseline как provenance-bound subtree, а dirty additions переносить только после allowlist-аудита и фиксации SHA-256 каждого файла.
- `proxima-ai-manager`: `/Users/mikezhamba/Desktop/MILV/03-startups/!Proxima/PRoxima/Опрос-v2.2`, tracked baseline `9cca25d1118ab74a113be43e4346a024b0c7abe7`; source worktree также содержит unrelated owner changes. Импортировать только явно выбранные contracts/tests после аудита.

**WB API:** Три отдельных SecretRef (Statistics, Analytics, Finance) - разделение по принципу least privilege. Официальные ручные выгрузки XLSX - первичный источник для исторических данных.

**Timezone:** Все временны́е расчёты - Europe/Moscow (UTC+3). Calendar day определяется по московскому времени.

**Язык:** Коммуникация и документация - русский. Идентификаторы кода (переменные, функции, таблицы, поля) - английский.

**Linear:** Issues до 2026-08-12 - зафиксированная история; новая иерархия задач создаётся в рамках rebaseline без destructive rewrite существующих записей.

## Constraints

- **Tech stack**: hybrid monorepo - Node.js 22 + TypeScript для существующего collector/data-plane, Python 3.14 + FastAPI для control-plane/Data Health, PostgreSQL 16, Docker Compose; не переписывать проверенный TypeScript collector на Python без отдельного ADR и benchmark evidence
- **Хранилище**: Raw-артефакты вне Git (private Docker volume или network mount), но SHA-256 манифест и lineage таблицы в Git и PostgreSQL
- **Безопасность**: SecretRef через Docker secrets или env-файл вне репозитория; никаких credentials в git history
- **Fail-closed**: Любая операция с внешними источниками либо успешна полностью, либо откатывается; нет partial commits в production
- **Data fidelity**: Нельзя фабриковать cabinet ID, SKU, цены, пороги или ожидаемые исходы даже в тестах - использовать fixture с реальной структурой но явно обезличенными значениями
- **Backup**: Restic репозиторий на S3-compatible хранилище, ключ шифрования вне репозитория
- **Review gate**: Cross-model deep review каждого slice - не опциональный шаг, блокирующий advance
- **VPS**: Один хост, один Docker Compose stack, без оркестрации в M1

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| WB official = canonical, Torgstat = supporting | Официальные данные - единственный источник истины; Torgstat даёт validation, не override | - Pending |
| Release pointer fail-closed | Partial release хуже отсутствия release - last-known-good лучше corrupt state | - Pending |
| Иммутабельное raw-хранилище вне Git | Git не предназначен для бинарных данных; SHA-256 манифест даёт equivalence proof без хранения в VCS | - Pending |
| Атомарные доменные релизы (inventory / finance раздельно) | Разные SLA и owners; shared release создаёт coupling и усложняет rollback | - Pending |
| order_count как первая reconciliation метрика | Простейшая аддитивная метрика с однозначной семантикой; валидирует pipeline до финансовых данных | - Pending |
| Docker Compose вместо K8s | Один VPS, один инженер, M1 = данные а не масштабирование; overhead K8s не оправдан | - Pending |
| Torgstat fail-closed по умолчанию | Сессионная автоматизация без явного разрешения нарушает WB ToS риск; безопаснее запретить по умолчанию | - Pending |
| Data Health page только через VPN/SSH | Нет клиентского UI в M1; минимальная attack surface | - Pending |
| Vertical slice + GO gates | Mike контролирует качество на ключевых переходах; не блокирует параллельную работу внутри slice | - Pending |

---
*Last updated: 2026-08-12 after initial project brief and research phase*
