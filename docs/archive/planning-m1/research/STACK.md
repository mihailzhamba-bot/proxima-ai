# Stack Research

**Domain:** Data pipeline / ETL platform (WB marketplace cabinets)
**Researched:** 2026-08-12
**Confidence:** HIGH

---

## Recommended Stack

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Node.js + TypeScript | 22 / 5.6 | Collector, raw commit protocol, WB adapters, typed ETL | Existing collector baseline `610169a` already passes 125/125 offline tests and `tsc --noEmit` on 2026-08-12; preserving it is lower risk than a rewrite |
| Python | 3.14 | Control-plane, Data Health, release/evidence workflows | Existing Proxima baseline `9cca25d` already uses this runtime and has FastAPI/PostgreSQL contracts; keep the service boundary explicit |
| PostgreSQL | 15+ | Primary data store, quarantine, lineage, release pointers | Уже зафиксировано в constraints; JSONB для metadata, advisory locks для atomic release promotion |
| Docker Compose | 2.x (Compose V2) | Оркестрация сервисов на одном VPS | Уже зафиксировано; единая команда `docker compose up -d` запускает весь стек |
| Restic | latest | Off-site encrypted backup | Нативный S3-compatible backend, client-side шифрование, dry-run restore verification встроена |

### Database Layer

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| psycopg3 (`psycopg[binary]`) | 3.x | PostgreSQL async driver | Всегда — psycopg2 в maintenance-only режиме; psycopg3 даёт 3.4× throughput и dual sync/async API из одного пакета |
| SQLAlchemy Core | 2.0+ | SQL toolkit без ORM overhead | Для всех database операций в workers; Core (не ORM) даёт точный контроль над транзакциями и явный SQL, что критично для fail-closed release logic |
| Alembic | 1.x | Schema migrations | Версионированные миграции; autogenerate из SQLAlchemy metadata; обязателен для schema-drift detection |

### HTTP и API-клиенты

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| httpx | 0.27+ | Async HTTP client для WB API | Type-safe, async-native, connection pooling, поддержка timeout per request; предпочтительнее aiohttp по developer experience |
| tenacity | 8.x | Retry с exponential backoff + jitter | Декорируется поверх httpx-вызовов; `wait_exponential_jitter` исключает thundering herd при восстановлении WB API |

### Scheduling

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| Existing TypeScript scheduler + PostgreSQL run ledger | Node 22 | Daily/retry orchestration | Audit and harden the existing scheduler first; do not add a second scheduler runtime unless a measured gap remains |

**Важно:** Python control-plane не владеет расписанием ingestion в M1. Один scheduler owner исключает duplicate runs и split-brain.

### XLSX Processing

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| Existing bounded OOXML reader | TypeScript collector | Валидация и чтение XLSX без загрузки workbook целиком | Preserve namespace/content-type/relationship safety limits and add report-specific schema contracts |

**Решение:** не добавлять openpyxl/pandas в M1 без подтверждённого формата, который существующий bounded reader не поддерживает.

### Configuration и Secrets

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pydantic-settings | 2.x | Typed config из env/Docker secrets | Единая точка входа для всех настроек; поддерживает чтение из `/run/secrets/` (Docker secrets path) напрямую |

### Data Health Page

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| FastAPI | 0.111+ | Read-only internal dashboard | Async, type-safe, OpenAPI из коробки; для M1 (Mike only via SSH tunnel) без JS-фреймворка |
| Jinja2 | 3.x | HTML templates | Минимальный server-side render; никакого React/Vue для read-only страницы |
| uvicorn | 0.29+ | ASGI server | Стандарт для FastAPI в Docker; один worker достаточен для личного dashboard |

### Alerting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| httpx (прямой вызов) | — | Telegram Bot API для алертов | Достаточно POST на `api.telegram.org/bot{token}/sendMessage`; python-telegram-bot излишен для send-only use case |

### Testing

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest | 8.x | Test runner | Стандарт; лучше unittest по readability и fixture system |
| pytest-asyncio | 0.23+ | Async test support | Все workers async — без этого не протестировать корректно |
| testcontainers[postgresql] | 4.x | Real PostgreSQL в CI | Не мокать БД; testcontainers запускает реальный PostgreSQL контейнер (~3 сек старт) — critical для verifying release pointer logic |
| pytest-cov | 4.x | Coverage | Requirement по vertical slice coverage |

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| ruff | Linting + formatting (заменяет flake8 + black + isort) | Один инструмент вместо трёх; конфигурация в `pyproject.toml` |
| mypy | Static type checking | `strict` режим для worker code; pydantic-совместим |
| just | `just verify` entrypoint | Проще Makefile; `just verify` = lint + typecheck + test — единая точка входа по M1-H |
| pre-commit | Git hooks | ruff + mypy перед каждым коммитом |

---

## Installation

```bash
# Collector/data-plane
npm ci --prefix services/collector

# Control-plane/Data Health
uv sync --project services/control-plane --frozen

# Root verification
make verify
```

---

## Alternatives Considered

| Recommended | Alternative | Why Not |
|-------------|-------------|---------|
| Hybrid TypeScript + Python | Python-only rewrite | Переписывание потеряет проверенные collector invariants, commit recovery и 125 offline tests; service boundary уже существует и проверяется единым root verify |
| psycopg3 | psycopg2, asyncpg | psycopg2 maintenance-only; asyncpg быстрее но без sync fallback и не поддерживает SQLAlchemy DDL нативно |
| SQLAlchemy Core | SQLAlchemy ORM | ORM скрывает транзакции — неприемлемо для fail-closed release logic; Core даёт явный `BEGIN/COMMIT/ROLLBACK` |
| Existing TypeScript scheduler | Celery/APScheduler | Второй scheduler owner создаст duplicate-run и recovery ambiguity; сначала укрепить существующий run ledger и single-instance lock |
| Existing bounded OOXML reader | openpyxl/pandas rewrite | Rewrite потеряет hard safety limits и OOXML provenance tests без продуктовой выгоды |
| httpx | aiohttp, requests | requests блокирующий; aiohttp хуже по DX и type hints; httpx async-first, тот же API для sync/async |
| testcontainers | pytest-postgresql, mocks | Моки пропускают schema drift и transaction edge cases — именно те баги, которые ломают release pointer logic |
| FastAPI | Flask, Django | Flask/Django sync-first; Django излишен для read-only внутренней страницы; FastAPI нативно async и генерирует OpenAPI |
| ruff | flake8 + black + isort | Три инструмента → один; ruff в 10-100× быстрее, поддерживает все те же правила |

---

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| SQLAlchemy ORM (declarative) | Скрывает BEGIN/COMMIT, усложняет явный контроль транзакций в release pipeline | SQLAlchemy Core с явными `text()` или `Table` конструкциями |
| Celery + Redis | Два дополнительных сервиса без распределённой нагрузки — overkill для одного VPS | Existing TypeScript scheduler + PostgreSQL run ledger |
| Airflow / Prefect / Dagster | Полноценный orchestrator с UI, worker pool, scheduler — весь стек ради 4-5 cron jobs | Existing TypeScript scheduler |
| openpyxl/pandas для raw XLSX read | Дублируют уже проверенный bounded OOXML boundary | Existing TypeScript OOXML reader |
| psycopg2 | Maintenance-only с 2023, нет native async | psycopg3 (`psycopg[binary]`) |
| aiopg | Обёртка над psycopg2, устаревшая | psycopg3 |
| Flask-SQLAlchemy | Flask sync-first, ORM-oriented | FastAPI + SQLAlchemy Core |
| python-telegram-bot | SDK для full-featured bot; для send-only алертов излишен | httpx прямой вызов Bot API |
| Kubernetes, Nomad | Не нужно для одного VPS в M1 | Docker Compose |
| .env файл в Git | Секреты в истории репозитория — неприемлемо | Docker secrets (`/run/secrets/`) или env-файл вне репозитория |

---

## Stack Patterns by Context

**Workers (data ingestion, reconciliation):**
- TypeScript collector modules own source adapters, raw persistence, parsing, staging and release publication.
- `pg` Pool and explicit SQL transactions own database writes.
- Python control-plane consumes approved read models and never duplicates ingestion ownership.

**Scheduler:**
- One TypeScript scheduler process backed by the PostgreSQL run ledger.
- PostgreSQL advisory/lease lock prevents a second process from starting the same bounded job.

**Release pipeline:**
- Явный PostgreSQL advisory lock (`pg_try_advisory_lock`) на domain release
- Atomic `UPDATE release_pointer` только после `SELECT COUNT(*) = expected` из quarantine
- `SAVEPOINT` для partial rollback внутри транзакции

**Data Health page:**
- FastAPI + Jinja2, без JS-фреймворка
- Read-only PostgreSQL user для dashboard queries
- Доступ только через SSH tunnel (`ssh -L 8080:localhost:8080 vps`) — без публичного порта

**Secrets:**
- `pydantic-settings` с `env_nested_delimiter='__'`
- Docker secrets монтируются в `/run/secrets/<name>`, читаются через `SecretsSettingsSource`
- Три отдельных SecretRef: `wb_statistics_token`, `wb_analytics_token`, `wb_finance_token`

**Backup:**
- Restic в отдельном Docker сервисе с `restic backup` + `restic check --read-data-subset=5%`
- `--dry-run` restore verification в каждом backup-цикле
- Restic repo password в Docker secret, никогда в env var или логах

---

## Version Compatibility

| Package | Compatible With | Notes |
|---------|-----------------|-------|
| SQLAlchemy 2.0+ | psycopg 3.x | Используй `postgresql+psycopg` dialect, не `postgresql+psycopg2` |
| Alembic 1.x | SQLAlchemy 2.0+ | Полностью совместимы; autogenerate работает с 2.0 metadata |
| FastAPI 0.111+ | pydantic v2 | FastAPI требует pydantic v2; pydantic-settings 2.x тоже; конфликт с pydantic v1 исключён |
| testcontainers 4.x | pytest-asyncio 0.23+ | Async fixtures совместимы; используй `@pytest.fixture(scope="session")` для PostgreSQL контейнера |
| Python 3.14 | existing Proxima control-plane | Preserve the pinned project runtime unless a dependency compatibility check proves a blocker |

---

## Sources

- psycopg3 async performance — [Johal.in psycopg3 2026 benchmarks](https://johal.in/psycopg3-async-drivers-high-throughput-python-postgres-connections-2026/)
- httpx + tenacity pattern — [httpx-tenacity tutorial](https://midnighter.github.io/httpx-tenacity/0.1/tutorial/)
- testcontainers-python — [Official docs](https://testcontainers-python.readthedocs.io/) + [Docker Getting Started](https://docs.docker.com/guides/testcontainers-python-getting-started/)
- Alembic autogenerate — [Official Alembic docs](https://alembic.sqlalchemy.org/en/latest/autogenerate.html)
- FastAPI + PostgreSQL production — [BetaZetaDev guide](https://betazeta.dev/blog/fastapi-postgresql-production/)

---

*Stack research for: PROXIMA AI — WB data platform, M1*
*Researched: 2026-08-12*
