# PA-39: Аудит scenario engine в Опрос-v2.2

Дата: 2026-08-23. Lane: основной агент (решение grill-сеанса 2026-08-23).
Выход этого аудита: карта модулей, граф зависимостей, consumed-surface map для
PMM-29, allowlist (`pa-39-import-allowlist.yaml`) и оценка объёма PA-41.

---

## 1. Provenance

| Параметр | Значение |
|---|---|
| Source worktree | `/Users/mikezhamba/Desktop/MILV/03-startups/!Proxima/PRoxima/Опрос-v2.2` |
| Source commit (пин аудита и allowlist) | `53b7d604ec27537be7683f51850f6bb3080dd6ed` |
| Задокументированный baseline (STATE.md) | `9cca25d1118ab74a113be43e4346a024b0c7abe7` |
| Отношение | `9cca25d1` - предок `53b7d604` (подтверждено `git merge-base --is-ancestor`) |
| Дельта baseline -> пин | 10 docs-файлов, +1573 строк (7 в `0_hq/` + 3 в `.planning/`: VALIDATION.md, 02-02-PLAN.md, 02-03-PLAN.md) - `src/`, `tests/`, `evals/` не тронуты, все хэши allowlist идентичны в обоих коммитах |
| Состояние worktree при снятии хэшей | clean: `git status --porcelain` = 0 записей (снимок до и после аудита - §9) |

Решение grill-сеанса: пинним фактический HEAD `53b7d604`, т.к. audit описывает
ровно то состояние, из которого PA-41 будет копировать. Дельта задокументирована
здесь и в `meta.baseline_note` allowlist.

## 2. Карта модулей `src/proxima`

### 2.1 Deep-зона (per-file аудит; импорт по allowlist)

| Файл | LOC | Назначение | Зависимости | Волна |
|---|---|---|---|---|
| `application/scenario_engine.py` | 653 | Детерминированное ядро SCN-001..008: реестр 8 хендлеров, policy-gate, факты/фингерпринты (canonical_hash = sha256 sorted JSON), дедуп открытых контрактов, типизированные BLOCKED/INCIDENT вместо исключений | pydantic, stdlib; `ai.contracts` (5 типов) | W1 |
| `ai/contracts.py` | 521 | Контрактный слой: ScenarioId (8 Literal), SourceRef/Money/SnapshotRef/ContextEnvelope/ScenarioInput/DeterministicScenarioResult/ScenarioPolicy/ActionContractDraft/CycleRequest/CycleResult; StrictModel (extra=forbid); trusted_source_class | pydantic | W1 |
| `evals/gate_validator.py` | 611 | E0-E3 evidence-валидация: CF-01..10 critical failures, пороги гейтов, HMAC-аттестация тест-прогонов, AST-проверки структуры тестов | pydantic, stdlib (ast, hmac) | W1 |
| `evals/reference_replay.py` | 485 | Offline-replay замороженных practitioner-кейсов: схема кейса, inventory, режимы replay, E0-readiness по покрытию сцен/edge-классов | pydantic, stdlib | W1 |
| `evals/shadow_comparison.py` | 467 | Blind-сравнение независимо замороженных human/AI ответов: commit-reveal, canonical bytes, InMemory-repo, sampling policy | pydantic, stdlib; `canonical_hash` из engine | W1 |
| `application/scenario_orchestrator.py` | 873 | State-routing read-only цикла: SIGNAL -> ANALYSIS -> RECOMMENDATION_DRAFT -> REVIEW_PENDING -> TERMINAL; ReviewedCycleRepository protocol; lease-конфиг ревью | pydantic; engine + весь ai/* | W2 |
| `ai/model_adapter.py` | 406 | Transport-neutral boundary одного structured-вызова: StrictAdapterModel, retry/timeout бюджеты, ModelFailureCode, refusal-детект | pydantic; contracts, model_port, prompts | W2 |
| `ai/model_port.py` | 104 | Registry провайдеров + build_model_port; провайдер и модель НЕ зарегистрированы (решение D3 - выбор на golden-set) | `proxima.settings` - единственная связь со settings | W2 |
| `ai/prompts.py` | 313 | Версионированные промпты (generator/reviewer/context v1) + trust-граница: карантин external_text, маркеры атак, детект секретов | pydantic; contracts | W2 |
| `ai/independent_reviewer.py` | 175 | Независимый ревью замороженного proposal тем же adapter; verdict + risk-порядок R0..R3 | pydantic; contracts, model_adapter, prompts, validator | W2 |
| `ai/recommendation_validator.py` | 286 | Детерминированные CF-01..10 guards публикации: числа в тексте <= чисел в фактах, live-action запрещён, только read-only формулировки | pydantic; contracts, model_adapter, prompts | W2 |

Тесты deep-зоны (все без БД и сети):

| Файл | LOC | Покрывает | Волна |
|---|---|---|---|
| `tests/unit/application/test_scenario_engine.py` | 486 | 10 тест-функций (2 параметризованные) - полная матрица поведения engine. Входы строит inline, БД не нужна | W1 |
| `tests/unit/ai/test_contracts.py` | 271 | Инварианты контрактов (strict, forbid extra, валидация) | W1 |
| `tests/evals/contracts/test_critical_failures.py` | 325 | GateValidator + e0-e3.json/schema сверка + drift-детект | W1 |
| `tests/evals/reference/test_reference_replay.py` | 301 | Loader/Readiness; кейсы пишет в tmp_path | W1 |
| `tests/evals/test_shadow_comparison.py` | 122 | Commit-reveal, canonical bytes, sampling | W1 |
| `tests/unit/ai/test_review_boundary.py` | 541 | Review-граница: quarantine, секреты, validator (fake-транспорт) | W2 |
| `tests/integration/model_contract/test_model_adapter.py` | 322 | Контракт adapter (fake-транспорт; БД не нужен, несмотря на путь) | W2 |

Данные deep-зоны:

| Файл | Размер | Роль |
|---|---|---|
| `tests/fixtures/scenario_engine/scn_008_partial.json` | 3,859 B | Единственный scenario-fixture: CycleInputBundle SCN-008 partial, обезличенные SYNTH-* значения. Потребитель в источнике - e2e; в PA-41 - вход adapter-слоя SCN-008 slice |
| `evals/evidence/e0-e3.json` + `.schema.json` | 12,225 + 10,225 B | Замороженные evidence-гейты + схема; вход gate_validator |
| `evals/reference/schema.json` | 10,532 B | Схема reference-кейсов (447 строк) |
| `evals/reference/cases.jsonl` | **0 B (пусто)** | Reference-датасет НЕ наполнен - placeholder. Replay-механизм готов, данных нет; наполнение - после PA-41, не блокер W1 |

### 2.2 Card-зона (модульные карточки; НЕ импортируется)

| Модуль | LOC | Что делает | Почему не сейчас |
|---|---|---|---|
| `web/app.py` + `auth.py` | 532 | FastAPI-приложение кабинета, basic-auth | Web-слой - после W1/W2, зависит от PA-38 и repositories |
| `web/decision_inbox.py` | 984 | Decision Inbox: lifecycle, lease, resolution | Тянет sqlalchemy + миграции источника; Inbox v0 - отдельная волна |
| `web/postgres.py` | 1253 | Пул/сессии, схема proxima источника | Инфраструктура БД источника |
| `cli/daily_manager.py` | 193 | CLI вход цикла (argparse) | Зависит от analytics_reader + repositories + settings |
| `observability/ai_metrics.py` | 631 | Метрики цикла (экспорт в web) | Потребляется web/cli |
| `logging.py` / `db.py` | 47 / 69 | Процессный логгинг; фабрика engine источника | db.py документирует dual-schema (proxima=alembic, analytics=torgstat RO) |
| `infrastructure/postgres/analytics_reader.py` | 360 | Read-only резолвер SourceRef -> ScenarioInput поверх `proxima.ai_source_resolutions/publications` + `analytics.*` вьюх (см. §7) | Write-path источника несовместим с db/ ledger монорепо; редизайн после PMM-29 |
| `infrastructure/postgres/decision_event_repository.py` | 1311 | Append-only журнал решений (16+ event-типов) | То же; кардинально зависит от миграций 003-010 |
| `infrastructure/postgres/shadow_submission_repository.py` | 156 | PG-реализация ShadowSubmissionRepository | InMemory-версия уже в W1; PG - после Data GO |
| `alembic/versions/001..010` | 10 миграций | Схема proxima источника (namespace, releases, manager state, decision ledger, inbox hardening, shadow roles, runtime head-lock) | Монорепо: ordered immutable db/ ledger (B6 additive-only) - перенос = редизайн, не копия |

### 2.3 Вне кода

`0_hq/` (бизнес-доки, rescue-дельта), `docs/`, `runbooks/`, `scripts/`, `infra/`,
`olga-trevozhnitsa/` - материалы источника, к scenario engine не относятся.

## 3. Сценарии: источник vs продуктовые волны

Все 8 SCN источника мапятся на волны PRODUCT-VISION; SCN-009/010/011 - greenfield.

| SCN | Реализация в источнике | Волна (PRODUCT-VISION) | Тесты | Readiness |
|---|---|---|---|---|
| SCN-008 data quality | `_run_scn_008` + INCIDENT-владелец в `run()` | **W1** | unit (полная), fixture partial | Готов к импорту; vertical slice PA-41 п.4 |
| SCN-001 продажи | `_run_scn_001`: ratio current/baseline | **W1** | unit | Готов; данные - adapter |
| SCN-005 OOS | `_run_scn_005`: days_cover = SELLABLE/demand <= threshold | **W1** | unit (stock-math только SELLABLE) | Готов; PMM-23 |
| SCN-007 DRR | `_run_scn_007`: ratio + обязательный experiment-дизайн (6 полей) | W2 | unit (эксперимент-гейт) | Готов; PMM после W1 |
| SCN-002 заказы | `_run_scn_002`: orders ratio | W2 | unit | Готов |
| SCN-004 маржа | `_run_scn_004`: PNL-компоненты, формула-гейт | W2 | unit (формула + COGS) | Готов; COGS - от Богатовой |
| SCN-003 P&L | `_run_scn_003`: contribution profit, формула-гейт | W4 | unit | Готов; полный P&L - W4 |
| SCN-006 overstock | `_run_scn_006`: days_cover >= threshold + сезонность | W4 | unit | Готов; 12-мес прогноз - greenfield |
| SCN-009/010/011 | **отсутствуют** | W3 | - | Greenfield: отзывы, акции, контент-алерты |

Общий gate движка: snapshot.status != ready или качество != fresh -> SCN-008
INCIDENT, остальные BLOCKED (`DATA_QUALITY_NOT_READY`) - «один владелец инцидента
качества, зависимые блокируются». Это архитектурное свойство сохраняется при
импорте без правок.

## 4. Зависимости

### 4.1 Внутренний граф (deep-зона)

```
settings.py <- model_port.py <- model_adapter.py <- orchestrator.py
contracts.py <- scenario_engine.py <- shadow_comparison.py (canonical_hash)
contracts.py <- prompts.py, model_adapter.py, recommendation_validator.py,
                independent_reviewer.py, orchestrator.py
gate_validator.py, reference_replay.py        # изолированы (ноль proxima-импортов)
```

W1-замыкание: `engine + contracts + 3x evals + 5 тестов + 5 файлов данных` -
ни одного импорта за пределы среза, ни БД, ни сети, ни LLM.

### 4.2 Внешние пакеты

| Пакет | Источник (пин) | Control-plane | Действие PA-41 |
|---|---|---|---|
| pydantic | 2.13.4 | **отсутствует** (`dependencies = []`) | Добавить в W1 (2.13.4) |
| pydantic-settings | 2.15.0 | отсутствует | Только W2 (settings-адаптация) |
| pytest | 9.1.1 | 8.4.2 (test extra) | Оставить 8.4.2; bump только при падении |
| sqlalchemy/psycopg/fastapi/uvicorn/jinja2 | есть | частично | НЕ нужны W1/W2 (проверено импортами) |

LLM SDK отсутствует в источнике намеренно (решение D3: провайдер выбирается на
golden-set). W2 наследует этот принцип - PMM-31 решает провайдера.

### 4.3 Ожидания БД

W1/W2-код к БД не обращается. БД-поверхности задокументированы для будущих волн:
схема `proxima` источника (таблицы `ai_source_resolutions`,
`ai_source_publications`, `source_releases`, decision ledger) и схема `analytics`
(torgstat-collector, RO). В источнике «две системы миграций на одну схему»
запрещены комментарием в conftest - монорепо сохраняет принцип: владелец схемы
один, M1-коллектор после Data GO.

### 4.4 Torgstat-точки

Функционального кода Torgstat в deep-зоне **нет**. Следы - только владельские
пометки: `db.py:5` и `settings.py:38` («схема analytics принадлежит
torgstat-collector, только читается»), `conftest.py:22,154` (проверка вьюх
аналитики в интеграционных тестах - conftest не импортируется). Живого
интерфейса, токенов или automation в импортируемом срезе нет; запрет
«Torgstat live session automation» не нарушается.

### 4.5 Синтаксис и Python-версия

`scenario_engine.py` использует PEP 758 (`except ScenarioPolicyMissing,
ValueError:` без скобок) - валидно только на Python 3.14+. Стек control-plane -
3.14 (uv) - совместимо. Понижение интерпретатора невозможно без правки байтов
(запрещено verbatim-правилом).

## 5. Consumed-surface map: вход для PMM-29

PMM-29 проектирует контракты signal/diagnosis/decision-record с нуля (решение
grill-сеанса). Ниже - полный перечень символов, которые импортируемые файлы
берут из `ai/contracts.py`; это минимальный интерфейс, который новые контракты
обязаны покрыть (или явно редизайнить) в adaptation-коммите PA-41.

| Символ | Потребители | Роль |
|---|---|---|
| `ScenarioId` | engine, orchestrator, prompts, model_adapter, recommendation_validator | Literal из 8 SCN |
| `ScenarioStatus` | engine | NO_ACTION/PROPOSED/BLOCKED/INCIDENT |
| `RiskLevel` | prompts, model_adapter, reviewer, validator | R0..R3 |
| `SourceRef` | engine, analytics_reader | факт с источником, доверием, качеством, lineage |
| `SnapshotRef` | engine (через ScenarioInput), analytics_reader | идентичность среза данных |
| `VersionedKnowledge` / `ClientContext` | analytics_reader, тесты | версионированный контекст клиента |
| `ContextEnvelope` | engine (через input), analytics_reader, тесты | operational_data + decision_memory |
| `DecisionMemoryRef` | engine, analytics_reader, тести | ссылка на прошлые решения (дедуп) |
| `OpenActionContractRef` | engine, analytics_reader, тесты | открытые контракты (дедуп) |
| `ScenarioPolicy` | engine, тесты | пороги/параметры/обязательные источники |
| `ScenarioInput` | engine, orchestrator, prompts, validator, тесты | вход цикла |
| `DeterministicScenarioResult` | engine, orchestrator, prompts, validator | выход движка (4 фингерпринта) |
| `ActionContractDraft` | orchestrator, тесты | черновик действия на review |
| `CycleRequest` / `CycleResult` | orchestrator, тесты | запрос/результат цикла |
| `CycleInputBundle` | analytics_reader, e2e | bundle для CLI-цикла |
| `trusted_source_class()` | analytics_reader | классификация доверия источника |

Итого: 18 символов. Дополнительно PMM-29 следует знать: `canonical_hash()`
живёт в engine (не в contracts) и является основой всех четырёх фингерпринтов
(trigger/facts/evidence/decision_state) - идентичность идемпотентности цикла.

## 6. Модель импорта PA-41 (двухкоммитная схема)

Решение grill-сеанса: PMM-29 -> PA-41. PA-41 исполняется двумя коммитами на
волну:

1. **Verbatim-коммит**: копирование строго по allowlist (re-hash перед каждым
   файлом; mismatch = abort), прогон `make verify`. Импорты `proxima.*`
   резолвятся без правок - пакет ложится в `services/control-plane/src/proxima/`
   рядом с `proxima_control_plane`.
2. **Adaptation-коммит**: перепривязка `proxima.ai.contracts`-импортов на
   контракты PMM-29 (reviewed diff, по consumed-surface map §5); правки
   pyproject (packages); при W2 - settings-адаптация.

Путевая арифметика проверена: `Path(__file__).parents[3]` в тестах указывает на
`services/control-plane/`, поэтому структура `tests/ + evals/` переносится без
правок путей. `pytest --import-mode=importlib` (источник) совместим с запуском
control-plane; `__init__.py` в tests-директориях не нужны.

Порядок волн: W1 (не ждёт ничего, кроме решения о pydantic-dep) -> PMM-29 ->
W2 (adaptation на новые контракты + settings). SCN-008 vertical slice (PA-41
п.4) выполняется на W1-fixture сразу после verbatim-коммита W1.

## 7. Интерфейс `analytics_reader` (спецификация будущего адаптера M1-данных)

В W1/W2 не импортируется, но определяет контракт будущего адаптера
«M1-факты -> ScenarioInput»:

- Вход: `SourceRef` (семантический locator) в рамках tenant (client/cabinet/snapshot).
- Разрешение: только через publication-слой (`ai_source_resolutions` ->
  `ai_source_publications` -> `source_releases`) с проверкой пересчитанного
  `resolution_checksum` = sha256 канонического JSON строки резолва.
- Fail-closed: любой разрыв цепочки publication/release -> `AnalyticsReadBlocked`
  с кодом, а не пустой результат.
- Выход: `ContextEnvelope` + `ScenarioInput` (факты с trust_class и quality).

Адаптер монорепо обязан сохранить: прослеживаемость каждого факта до
M1-release-pointer (наш аналог publication), fail-closed семантику и
проверку контрольных сумм на границе. Конкретные таблицы монорепо определяет
PMM-29 + редизайн repositories (не PA-41).

## 8. Оценка объёма PA-41

| Волнa | Работа | Оценка |
|---|---|---|
| W1 verbatim | 18 файлов = 104.5 KB src + 54.1 KB тестов + 36.8 KB данных (fixture + evals, вкл. пустой cases.jsonl), re-hash, pyproject: pydantic + packages, `make verify` зелёный | 0.5 дня |
| W1 SCN-008 slice | adapter-слой подачи fixture -> engine -> результат в тестах (по образцу 10-roadmap дни 51-60) | 0.5-1 день |
| W2 verbatim | 8 файлов + settings-адаптация + adaptation на контракты PMM-29 (по §5) | 1-2 дня (после PMM-29) |
| Риски | pytest 8 vs 9 (низкий); пустой cases.jsonl не блокирует (replay-тесты самодостаточны); PEP 758 уже совместим | - |

Итого PA-41: W1 - ~1-1.5 дня и не ждёт PMM-29; W2 - +1-2 дня после PMM-29.
Критический путь W1-среза M2 (PMM-5/20/23) деблокируется сразу после W1-части.

## 9. Протокол «не мутировать» (проверка аудита)

- Снимок ДО (до начала операций аудита): `git -C Опрос-v2.2 rev-parse HEAD` =
  `53b7d604ec27537be7683f51850f6bb3080dd6ed`; `git status --porcelain` = пусто
  (0 записей).
- Все операции аудита - только чтение (`sed`, `grep`, `find`, `shasum`,
  `git log/diff/show`, `uv run --no-sync python -c "import ..."`).
- Снимок ПОСЛЕ (после написания артефактов): HEAD и porcelain идентичны
  снимку ДО - `diff` пуст, «IDENTICAL: zero mutation confirmed». Независимо
  перепроверено reviewer-subagent'ом (см. §10).

## 10. Верификация аудита

**Машинный hash-transcript** (`pa-39-hash-transcript.txt`, лежит рядом):
программная сверка всех 27 записей allowlist (18 W1 + 8 W2 + 1 adaptation
base) - SHA-256 + size_bytes каждого файла пересчитаны из байтов источника,
результат **27/27 PASS**. Транскрипт доказал свою работу: первый прогон поймал
ошибку переноса хэша `test_model_adapter.py` (был подставлен дайджест соседнего
`test_ai_audit_reconstruction.py`) - ошибка исправлена, повторный прогон ALL
PASS. Любой может перепроверить: `shasum -a 256 <файл>` против allowlist.

**Independent reviewer-subagent** (read-only, вердикт в PR):
1. Dependency-closure W1/W2 - подтверждён по фактическим импортам всех
   19 py-файлов среза (включая поиск dynamic imports) - 0 нарушений.
2. Нулевая мутация источника - подтверждена (HEAD и clean status до/после).
3. Согласованность allowlist <-> аудит, LOC-числа (19/19 deep-зона),
   ScenarioId/PEP 758/parents[3]/conftest-независимость W1-тестов - подтверждены.
4. Первый прогон нашёл 3 blocker'а (счётчик тестов в §2.1 и 2 числовые
   ошибки в card-зоне, неверные итоги §8; машинные хэш-доказательства
   отсутствовали) + 1 warning (формулировка дельты baseline) - все исправлены
   в этом документе и YAML; хэши закрыты транскриптом выше (песочница
   reviewer'а не имела права на shasum - поэтому машинный транскрипт, а не
   ручной пересчёт). Повторный прогон: 0 блокеров в части фиксов; единственный
   остаток («11 тестов» в YAML-note) синхронизирован тем же исправлением.

Gate: 0 blockers после исправлений; финальная линия защиты остаётся в PA-41
(re-hash перед каждым копированием, mismatch = abort).
