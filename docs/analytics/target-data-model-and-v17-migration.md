# Целевая модель данных и миграция V17

> **Статус документа:** `unreleased / analytical proposal`  
> **Назначение:** аналитические предложения PMM-59 по товарной модели, grain, source authority и возможной эволюции хранения. **Не является канонической архитектурой Proxima и не является планом физической миграции.**  
> **Канон проекта на 09.09.2026:** `ARCHITECTURE-SPINE.md`, решения D18/D26/D33/D34 и текущий `main`. Каноническая граница данных — `tenant_id`; `seller_account_id` ниже рассматривается только как кандидат атрибута/сущности кабинета внутри tenant. Новые fact-таблицы, миграции и parallel storage из этого документа не создаются без отдельного архитектурного решения/change request.  
> **Доказательная база:** data-quality run `20260903T162418_b4b34738`, PMM-58/59 и анализ V17. Физические DDL ниже — иллюстрация требований к grain/keys, а не approved schema.  

## 0. Аналитическое предложение

V17 уже правильно отделяет тяжёлый сбор и расчёты от web-процесса, однако текущая таблица `daily_fact` является универсальной JSON-витриной, а не полноценным нормализованным хранилищем событий. Предлагаемая модель сохраняет сильные стороны V17 — immutable raw, отдельный builder, prepared snapshots и web `SELECT only` — и добавляет четыре недостающих слоя:

```text
immutable raw artifacts
        ↓
typed domain facts + dimensions
        ↓
versioned marts
        ↓
prepared snapshots / API compatibility layer
        ↓
web UI
```

Главное изменение — создание единой товарной модели и разделение событий по их естественному grain:

```text
nmId                 = конкретная карточка WB
imtID                = текущая контентная склейка WB
business_product_id  = стабильная внутренняя товарная группа
chrtId / barcode     = вариант карточки
```

`daily_fact` не удаляется сразу. На переходном периоде он остаётся compatibility cache, но перестаёт быть источником истины.

---

# 1. Текущее хранение V17

## 1.1. Канонический поток

Текущая реализация использует следующий контур:

```text
внешние API / локальные первичные файлы
        ↓
фоновые ingest-процессы
        ↓
SQLite: normalized daily facts
        ↓
фоновые расчёты
        ↓
prepared_snapshot + prepared_row
        ↓
JSON/CSV mirrors
        ↓
web-процесс только читает готовые данные
```

Основная база:

```text
data/v17/control_center.sqlite3
```

Файловые слои:

```text
data/v17/raw/        — первичные данные и API artifacts
data/v17/prepared/   — snapshot.json и rows.csv
data/v17/exports/    — пользовательские выгрузки
data/v17/logs/       — журналы фоновых процессов
data/v17/manifest.json
```

## 1.2. Основные таблицы

### `source_registry`

Хранит регистрацию источника:

- вид источника;
- раздел;
- бренд;
- marketplace;
- путь или endpoint;
- период;
- время получения;
- SHA-256;
- размер;
- число строк;
- parser version;
- статус и ошибку;
- произвольные metadata в JSON.

### `daily_fact`

Универсальный дневной слой:

```text
section
brand
marketplace
mode
day
entity_key
entity_json
metrics_json
source_ids_json
calc_version
updated_at
```

Primary key:

```text
(section, brand, marketplace, mode, day, entity_key)
```

### `prepared_snapshot` / `prepared_row`

Хранят готовую выдачу для UI:

- раздел и контекст;
- период;
- статус;
- completeness;
- summary;
- columns;
- source IDs;
- lineage;
- checksum;
- упорядоченные строки витрины.

### Служебные таблицы

- `custom_period_request`;
- `diagnostic_run`;
- `diagnostic_check`;
- `audit_event`;
- `meta`.

## 1.3. Текущее поведение записи

`replace_daily()` удаляет весь раздел для выбранного контекста и вставляет его заново:

```text
DELETE FROM daily_fact
WHERE section + brand + marketplace + mode
```

После этого загружается новый набор строк.

`upsert_daily()` обновляет отдельные дневные строки, но основная архитектура всё равно опирается на универсальные JSON-факты.

## 1.4. Текущие разделы builder

Основной builder материализует:

```text
stocks
ads
finance
orders_sales
```

Дополнительно строятся:

```text
FBS
costs
unit_economics
stock history
exports
```

## 1.5. Товарная логика сейчас

В коде используются функции:

```text
canonical_article()
family_of()
product_key()
```

Для большинства товарных серий внутреннее объединение строится по семейству артикула. Серия `901` является отдельным hard-coded исключением.

Это полезная бизнес-логика, но сейчас она:

- зашита в Python;
- не имеет истории;
- не позволяет ручное переопределение без изменения кода;
- не разделяет карточку WB, WB-склейку и внутреннюю товарную группу.

## 1.6. Что в V17 сохраняется без изменений

Целевая модель сохраняет следующие решения:

- web-процесс не читает Excel и не вызывает marketplace API;
- web-процесс не выполняет тяжёлые расчёты;
- raw artifacts остаются неизменяемыми;
- source registry и SHA-256 остаются обязательными;
- standard-period snapshots готовятся в фоне;
- custom period считается из нормализованных фактов;
- при неуспешной сборке предыдущая опубликованная витрина продолжает работать;
- неизвестные значения не заменяются искусственным нулём.

---

# 2. Проблемы `daily_fact` и JSON

## 2.1. `daily_fact` смешивает разные grains

Один универсальный формат не может корректно заменить:

- один Order event с PK `srid`;
- один Sale/Return event с PK `saleID`;
- одну Finance operation с PK `rrdId`;
- один Funnel snapshot `nmId × business_day × retrieved_at`;
- один Stock snapshot `nmId × chrtId × warehouse × retrieved_at`;
- одну строку Paid Storage;
- одну карточку или вариант товара.

Дневная агрегация подходит для mart, но теряет event-level lineage.

## 2.2. JSON не даёт строгих контрактов

`entity_json` и `metrics_json` позволяют быстро добавлять поля, но не обеспечивают:

- типизацию денег и дат;
- `NOT NULL` на ключевых полях;
- foreign keys;
- уникальность естественных event IDs;
- эффективные индексы по `nmId`, `srid`, `saleID`, `rrdId`;
- декларативные проверки диапазонов;
- безопасные schema migrations;
- прозрачный SQL для аналитики.

## 2.3. Бренд подменяет кабинет

Текущий контекст часто определяется как:

```text
brand + marketplace
```

Но один seller account может содержать несколько брендов. Поэтому обязательны две отдельные сущности:

```text
seller_account
brand
```

Бренд является атрибутом товара, а не идентификатором подключения API.

## 2.4. Артикул подменяет товарный ключ

Артикул продавца удобен для человека, но не является надёжным глобальным ключом:

- он может повторяться между кабинетами;
- может меняться;
- форматируется по-разному;
- разные marketplaces используют разные IDs;
- одна внутренняя группа может включать несколько `nmId`.

Для WB основной внешний ключ карточки — `nmId`; внутри БД факты должны ссылаться на `product_sk`.

## 2.5. Orders и Sales объединены логически

Раздел `orders_sales` затрудняет корректную модель:

```text
Orders: PK = srid; business date = order date
Sales:  PK = saleID; FK = srid; business date = sale/return date
```

Sale и Return не являются обновлением Order. Это отдельные события lifecycle.

## 2.6. Полная перезапись ухудшает доказуемость

`replace_daily()` удаляет ранее материализованный раздел целиком. Это создаёт риски:

- потеря предыдущей версии нормализованных данных;
- сложность расследования revisions;
- невозможность восстановить, каким был источник на момент старого сигнала;
- большой blast radius ошибки parser;
- невозможность атомарно сравнивать old/new candidate.

Для mutable источников требуется append-only snapshot history и отдельная current view.

## 2.7. Lineage хранится слишком укрупнённо

`source_ids_json` связывает строку с набором источников, но не указывает:

- какое конкретное поле пришло из какого source;
- к какому raw object относится факт;
- какой normalization rule применён;
- какая версия mapping использовалась;
- какой release опубликовал строку.

## 2.8. Prepared contract связан с текущим физическим хранением

UI уже правильно читает prepared snapshots, но часть compatibility-адаптеров знает детали старых разделов. Переключение на typed facts должно происходить за неизменным API-контрактом.

---

# 3. Целевые принципы

1. **Raw неизменяем.** Любой нормализованный факт восстанавливается до raw artifact.
2. **Один grain — одна таблица.** Orders, Sales, Finance, Funnel и Stocks не смешиваются.
3. **Внутренние surrogate keys.** Факты используют `seller_account_id`, `product_sk`, `variant_sk`, `warehouse_sk`.
4. **Внешние business IDs сохраняются.** `nmId`, `srid`, `saleID`, `rrdId`, `reportId` не заменяются внутренними ключами и индексируются.
5. **Dimensions отделены от facts.** Бренд, предмет, категория и товар не копируются как основной справочник в каждом факте.
6. **История отдельно от current.** Изменяемые источники не перезаписываются.
7. **Marts не являются первичной истиной.** Дневные показатели рассчитываются из typed facts.
8. **Prepared snapshots сохраняются.** UI продолжает читать готовые данные.
9. **Quality и finality независимы.** Полный, но ещё не финальный источник возможен.
10. **Unknown остаётся unknown.** Missing row, отсутствующая классификация или неподтверждённая формула не превращаются в ноль.

---

# 4. `dim_seller_account`

## 4.1. Назначение

Одна строка — одно подключение продавца к marketplace.

Кабинет отделяется от бренда. Это позволяет:

- хранить несколько брендов в одном кабинете;
- подключить один бренд в разных кабинетах;
- не смешивать одинаковые `nmId`/артикулы разных seller contexts;
- хранить timezone, currency и connection status отдельно от товара.

## 4.2. DDL

```sql
CREATE TABLE dim_seller_account (
    seller_account_id      INTEGER PRIMARY KEY,
    marketplace            TEXT NOT NULL,
    external_account_key   TEXT NOT NULL,
    account_name           TEXT NOT NULL,
    legal_entity_name      TEXT,
    timezone_name          TEXT NOT NULL DEFAULT 'Europe/Moscow',
    currency_code          TEXT NOT NULL DEFAULT 'RUB',
    connection_status      TEXT NOT NULL DEFAULT 'ACTIVE',
    first_seen_at          TEXT NOT NULL,
    last_seen_at           TEXT NOT NULL,
    created_at             TEXT NOT NULL,
    updated_at             TEXT NOT NULL,
    UNIQUE (marketplace, external_account_key),
    CHECK (connection_status IN ('ACTIVE','PAUSED','REVOKED','UNKNOWN'))
);

CREATE INDEX ix_seller_account_marketplace
    ON dim_seller_account(marketplace, connection_status);
```

`external_account_key` должен быть безопасным surrogate/hashed identifier; реальные секреты и API tokens в этой таблице не хранятся.

---

# 5. `dim_nomenclature`

## 5.1. Grain

Одна строка — одна конкретная marketplace-карточка в одном seller account.

Для WB:

```text
seller_account_id + nm_id
```

Для Ozon позднее используется тот же внутренний `product_sk`, но отдельный marketplace external ID.

## 5.2. Состав

```sql
CREATE TABLE dim_brand (
    brand_id        INTEGER PRIMARY KEY,
    normalized_name TEXT NOT NULL UNIQUE,
    display_name    TEXT NOT NULL,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);

CREATE TABLE dim_category (
    category_id       INTEGER PRIMARY KEY,
    marketplace       TEXT NOT NULL,
    external_category_id TEXT,
    category_name     TEXT NOT NULL,
    parent_category_id INTEGER REFERENCES dim_category(category_id),
    created_at        TEXT NOT NULL,
    updated_at        TEXT NOT NULL,
    UNIQUE (marketplace, external_category_id, category_name)
);

CREATE TABLE dim_subject (
    subject_id          INTEGER PRIMARY KEY,
    marketplace         TEXT NOT NULL,
    external_subject_id TEXT,
    subject_name        TEXT NOT NULL,
    category_id         INTEGER REFERENCES dim_category(category_id),
    created_at          TEXT NOT NULL,
    updated_at          TEXT NOT NULL,
    UNIQUE (marketplace, external_subject_id, subject_name)
);

CREATE TABLE dim_nomenclature (
    product_sk             INTEGER PRIMARY KEY,
    seller_account_id      INTEGER NOT NULL REFERENCES dim_seller_account(seller_account_id),
    marketplace            TEXT NOT NULL,
    nm_id                  TEXT NOT NULL,
    nm_uuid                TEXT,
    supplier_article       TEXT,
    supplier_article_norm  TEXT,
    title                  TEXT,
    brand_id               INTEGER REFERENCES dim_brand(brand_id),
    subject_id             INTEGER REFERENCES dim_subject(subject_id),
    category_id            INTEGER REFERENCES dim_category(category_id),
    current_imt_id         TEXT,
    business_product_id    INTEGER,
    is_active              INTEGER NOT NULL DEFAULT 1,
    first_seen_at          TEXT NOT NULL,
    last_seen_at           TEXT NOT NULL,
    source_run_id          TEXT NOT NULL,
    created_at             TEXT NOT NULL,
    updated_at             TEXT NOT NULL,
    UNIQUE (seller_account_id, marketplace, nm_id),
    CHECK (is_active IN (0,1))
);

CREATE INDEX ix_nomenclature_article
    ON dim_nomenclature(seller_account_id, supplier_article_norm);
CREATE INDEX ix_nomenclature_brand
    ON dim_nomenclature(seller_account_id, brand_id, is_active);
CREATE INDEX ix_nomenclature_subject
    ON dim_nomenclature(seller_account_id, subject_id, is_active);
CREATE INDEX ix_nomenclature_category
    ON dim_nomenclature(seller_account_id, category_id, is_active);
CREATE INDEX ix_nomenclature_imt
    ON dim_nomenclature(seller_account_id, current_imt_id);
CREATE INDEX ix_nomenclature_business_product
    ON dim_nomenclature(seller_account_id, business_product_id);
```

## 5.3. Правила наполнения

Приоритет источников для current attributes:

1. Content/catalog source;
2. проверенный reference catalog;
3. Funnel product metadata;
4. Statistics Orders/Sales;
5. Finance;
6. ручное значение с блокировкой автоматического overwrite.

Каждое обновление должно сохранять:

- source run;
- source priority;
- время first/last seen;
- признак manual override;
- конфликт значений, если источники расходятся.

---

# 6. `imtID` и история склеек

## 6.1. Разделение понятий

`imtID` — marketplace-контентная группа. Она может изменяться со временем и не должна использоваться как стабильная внутренняя товарная группа.

Нужно хранить:

- текущий `imtID` в `dim_nomenclature` для быстрых фильтров;
- полную историю членства в отдельной bridge-table.

## 6.2. DDL

```sql
CREATE TABLE dim_wb_content_group (
    wb_content_group_sk INTEGER PRIMARY KEY,
    seller_account_id   INTEGER NOT NULL REFERENCES dim_seller_account(seller_account_id),
    imt_id              TEXT NOT NULL,
    subject_id          INTEGER REFERENCES dim_subject(subject_id),
    first_seen_at       TEXT NOT NULL,
    last_seen_at        TEXT NOT NULL,
    is_current          INTEGER NOT NULL DEFAULT 1,
    source_run_id       TEXT NOT NULL,
    UNIQUE (seller_account_id, imt_id),
    CHECK (is_current IN (0,1))
);

CREATE TABLE bridge_nm_imt_history (
    product_sk           INTEGER NOT NULL REFERENCES dim_nomenclature(product_sk),
    wb_content_group_sk  INTEGER NOT NULL REFERENCES dim_wb_content_group(wb_content_group_sk),
    valid_from           TEXT NOT NULL,
    valid_to             TEXT,
    is_current           INTEGER NOT NULL,
    source_run_id        TEXT NOT NULL,
    change_reason        TEXT,
    PRIMARY KEY (product_sk, wb_content_group_sk, valid_from),
    CHECK (is_current IN (0,1)),
    CHECK (valid_to IS NULL OR valid_to >= valid_from)
);

CREATE UNIQUE INDEX ux_nm_one_current_imt
    ON bridge_nm_imt_history(product_sk)
    WHERE is_current = 1;
CREATE INDEX ix_imt_membership_current
    ON bridge_nm_imt_history(wb_content_group_sk, is_current);
```

## 6.3. Обновление

При изменении `imtID`:

1. текущая запись bridge закрывается `valid_to`;
2. добавляется новая запись;
3. `dim_nomenclature.current_imt_id` обновляется;
4. создаётся audit event;
5. старые факты не переписываются.

---

# 7. `business_product_id`

## 7.1. Назначение

`business_product_id` — стабильная внутренняя группа для бизнес-аналитики. Она может объединять:

- разные оттенки одной серии;
- несколько `nmId`;
- разные `imtID`;
- карточки одного товара на разных marketplaces.

Она не должна автоматически меняться вслед за WB-склейкой.

## 7.2. DDL

```sql
CREATE TABLE dim_business_product (
    business_product_id   INTEGER PRIMARY KEY,
    business_product_code TEXT NOT NULL UNIQUE,
    display_name          TEXT NOT NULL,
    brand_id              INTEGER REFERENCES dim_brand(brand_id),
    subject_id            INTEGER REFERENCES dim_subject(subject_id),
    grouping_policy       TEXT NOT NULL DEFAULT 'MANUAL',
    is_active             INTEGER NOT NULL DEFAULT 1,
    created_by            TEXT NOT NULL,
    created_at            TEXT NOT NULL,
    updated_at            TEXT NOT NULL,
    CHECK (grouping_policy IN ('MANUAL','ARTICLE_FAMILY','CONTENT_GROUP','IMPORTED','HYBRID')),
    CHECK (is_active IN (0,1))
);

CREATE TABLE bridge_nm_business_product (
    product_sk             INTEGER NOT NULL REFERENCES dim_nomenclature(product_sk),
    business_product_id    INTEGER NOT NULL REFERENCES dim_business_product(business_product_id),
    valid_from             TEXT NOT NULL,
    valid_to               TEXT,
    is_current             INTEGER NOT NULL,
    mapping_source         TEXT NOT NULL,
    mapping_confidence     REAL,
    rule_id                INTEGER,
    comment                TEXT,
    PRIMARY KEY (product_sk, business_product_id, valid_from),
    CHECK (mapping_source IN ('MANUAL','ARTICLE_FAMILY','CONTENT_GROUP','IMPORTED')),
    CHECK (mapping_confidence IS NULL OR (mapping_confidence >= 0 AND mapping_confidence <= 1)),
    CHECK (is_current IN (0,1))
);

CREATE UNIQUE INDEX ux_nm_one_current_business_product
    ON bridge_nm_business_product(product_sk)
    WHERE is_current = 1;

CREATE TABLE product_group_rule (
    rule_id                    INTEGER PRIMARY KEY,
    seller_account_id          INTEGER REFERENCES dim_seller_account(seller_account_id),
    brand_id                   INTEGER REFERENCES dim_brand(brand_id),
    rule_type                  TEXT NOT NULL,
    pattern                    TEXT NOT NULL,
    target_business_product_id INTEGER NOT NULL REFERENCES dim_business_product(business_product_id),
    priority                   INTEGER NOT NULL DEFAULT 100,
    enabled                    INTEGER NOT NULL DEFAULT 1,
    created_at                 TEXT NOT NULL,
    updated_at                 TEXT NOT NULL,
    CHECK (rule_type IN ('ARTICLE_PREFIX','ARTICLE_REGEX','EXACT_ARTICLE','IMT_ID')),
    CHECK (enabled IN (0,1))
);

CREATE INDEX ix_group_rule_lookup
    ON product_group_rule(seller_account_id, brand_id, enabled, priority);
```

## 7.3. Перенос текущей логики

Текущие функции `family_of()` и `product_key()` используются только для первичного seed:

```text
501/1 → группа 501
501/2 → группа 501
...
901/* → индивидуальные правила
```

После seed результат хранится в таблицах. Ручное сопоставление всегда имеет приоритет над автоматическим правилом.

---

# 8. Варианты и баркоды

## 8.1. Почему нужны отдельные таблицы

У одного `nmId` могут встречаться несколько `barcode`, `techSize` и `chrtId`. Баркод нельзя хранить одним атрибутом карточки.

## 8.2. DDL

```sql
CREATE TABLE dim_product_variant (
    variant_sk        INTEGER PRIMARY KEY,
    product_sk        INTEGER NOT NULL REFERENCES dim_nomenclature(product_sk),
    chrt_id           TEXT,
    tech_size         TEXT,
    variant_name      TEXT,
    is_current        INTEGER NOT NULL DEFAULT 1,
    first_seen_at     TEXT NOT NULL,
    last_seen_at      TEXT NOT NULL,
    source_run_id     TEXT NOT NULL,
    UNIQUE (product_sk, chrt_id, tech_size),
    CHECK (is_current IN (0,1))
);

CREATE INDEX ix_variant_product
    ON dim_product_variant(product_sk, is_current);
CREATE INDEX ix_variant_chrt
    ON dim_product_variant(chrt_id);

CREATE TABLE bridge_variant_barcode (
    variant_sk       INTEGER NOT NULL REFERENCES dim_product_variant(variant_sk),
    barcode          TEXT NOT NULL,
    valid_from       TEXT NOT NULL,
    valid_to         TEXT,
    is_current       INTEGER NOT NULL,
    source_run_id    TEXT NOT NULL,
    PRIMARY KEY (variant_sk, barcode, valid_from),
    CHECK (is_current IN (0,1))
);

CREATE INDEX ix_barcode_lookup
    ON bridge_variant_barcode(barcode, is_current);
```

Текущий основной barcode определяется только catalog/content source или ручным подтверждением, а не «последним встретившимся заказом».

---

# 9. Typed domain facts

## 9.1. Общие технические поля

Каждая fact-table должна содержать:

```text
seller_account_id
source_run_id
source_artifact_id / source_registry_id
retrieved_at
quality_status
finality_status
normalizer_version
created_at
```

Для сохранения неизвестных новых API-полей допустимо временно хранить `raw_payload_json`, но ключи и business-critical metrics должны быть типизированы.

## 9.2. Statistics Orders

```sql
CREATE TABLE fact_order_statistics (
    seller_account_id      INTEGER NOT NULL REFERENCES dim_seller_account(seller_account_id),
    srid                   TEXT NOT NULL,
    product_sk             INTEGER REFERENCES dim_nomenclature(product_sk),
    variant_sk             INTEGER REFERENCES dim_product_variant(variant_sk),
    order_at               TEXT NOT NULL,
    last_change_at         TEXT,
    warehouse_name         TEXT,
    warehouse_type         TEXT,
    country_name           TEXT,
    federal_district_name  TEXT,
    region_name            TEXT,
    g_number               TEXT,
    income_id              TEXT,
    total_price            NUMERIC,
    discount_percent       NUMERIC,
    spp_percent            NUMERIC,
    finished_price         NUMERIC,
    price_with_disc        NUMERIC,
    is_cancel              INTEGER NOT NULL DEFAULT 0,
    cancel_at              TEXT,
    sticker                TEXT,
    source_run_id          TEXT NOT NULL,
    source_registry_id     INTEGER,
    retrieved_at           TEXT NOT NULL,
    quality_status         TEXT NOT NULL,
    finality_status        TEXT NOT NULL,
    normalizer_version     TEXT NOT NULL,
    raw_payload_json       TEXT,
    created_at             TEXT NOT NULL,
    updated_at             TEXT NOT NULL,
    PRIMARY KEY (seller_account_id, srid),
    CHECK (is_cancel IN (0,1))
);

CREATE INDEX ix_order_business_day
    ON fact_order_statistics(seller_account_id, order_at);
CREATE INDEX ix_order_product_day
    ON fact_order_statistics(seller_account_id, product_sk, order_at);
CREATE INDEX ix_order_warehouse_day
    ON fact_order_statistics(seller_account_id, warehouse_type, warehouse_name, order_at);
CREATE INDEX ix_order_group
    ON fact_order_statistics(seller_account_id, g_number);
```

## 9.3. Marketplace FBS Orders

```sql
CREATE TABLE fact_order_fbs (
    seller_account_id    INTEGER NOT NULL REFERENCES dim_seller_account(seller_account_id),
    marketplace_order_id TEXT NOT NULL,
    order_uid            TEXT,
    product_sk           INTEGER REFERENCES dim_nomenclature(product_sk),
    variant_sk           INTEGER REFERENCES dim_product_variant(variant_sk),
    warehouse_sk         INTEGER,
    created_at_marketplace TEXT NOT NULL,
    closed_at_marketplace  TEXT,
    status               TEXT,
    source_run_id        TEXT NOT NULL,
    retrieved_at         TEXT NOT NULL,
    quality_status       TEXT NOT NULL,
    finality_status      TEXT NOT NULL,
    raw_payload_json     TEXT,
    created_at           TEXT NOT NULL,
    updated_at           TEXT NOT NULL,
    PRIMARY KEY (seller_account_id, marketplace_order_id)
);

CREATE INDEX ix_fbs_order_uid
    ON fact_order_fbs(seller_account_id, order_uid);
CREATE INDEX ix_fbs_order_product_time
    ON fact_order_fbs(seller_account_id, product_sk, created_at_marketplace);
```

```sql
CREATE TABLE bridge_order_crosswalk (
    seller_account_id      INTEGER NOT NULL REFERENCES dim_seller_account(seller_account_id),
    statistics_srid        TEXT NOT NULL,
    marketplace_order_id   TEXT NOT NULL,
    match_method           TEXT NOT NULL,
    match_confidence       REAL NOT NULL,
    evidence_json          TEXT NOT NULL,
    verified_at            TEXT,
    PRIMARY KEY (seller_account_id, statistics_srid, marketplace_order_id),
    CHECK (match_confidence >= 0 AND match_confidence <= 1)
);
```

Общая orders mart строится только после crosswalk и дедупликации.

## 9.4. Sales / Returns

```sql
CREATE TABLE fact_sale_event (
    seller_account_id    INTEGER NOT NULL REFERENCES dim_seller_account(seller_account_id),
    sale_id              TEXT NOT NULL,
    srid                 TEXT NOT NULL,
    event_type           TEXT NOT NULL,
    product_sk           INTEGER REFERENCES dim_nomenclature(product_sk),
    variant_sk           INTEGER REFERENCES dim_product_variant(variant_sk),
    event_at             TEXT NOT NULL,
    last_change_at       TEXT,
    warehouse_name       TEXT,
    warehouse_type       TEXT,
    price_with_disc      NUMERIC,
    finished_price       NUMERIC,
    payment_sale_amount  NUMERIC,
    for_pay              NUMERIC,
    spp_percent          NUMERIC,
    g_number             TEXT,
    source_run_id        TEXT NOT NULL,
    retrieved_at         TEXT NOT NULL,
    quality_status       TEXT NOT NULL,
    finality_status      TEXT NOT NULL,
    raw_payload_json     TEXT,
    created_at           TEXT NOT NULL,
    updated_at           TEXT NOT NULL,
    PRIMARY KEY (seller_account_id, sale_id),
    CHECK (event_type IN ('SALE','RETURN','UNKNOWN'))
);

CREATE INDEX ix_sale_srid
    ON fact_sale_event(seller_account_id, srid);
CREATE INDEX ix_sale_product_time
    ON fact_sale_event(seller_account_id, product_sk, event_at);
```

Дедупликация по `srid` запрещена.

## 9.5. Finance reports и operations

```sql
CREATE TABLE fact_finance_report (
    seller_account_id       INTEGER NOT NULL REFERENCES dim_seller_account(seller_account_id),
    report_id               TEXT NOT NULL,
    report_type             TEXT,
    date_from               TEXT NOT NULL,
    date_to                 TEXT NOT NULL,
    create_date             TEXT NOT NULL,
    currency_code           TEXT,
    report_status           TEXT NOT NULL,
    retail_amount_sum       NUMERIC,
    for_pay_sum             NUMERIC,
    delivery_service_sum    NUMERIC,
    paid_storage_sum        NUMERIC,
    paid_acceptance_sum     NUMERIC,
    deduction_sum           NUMERIC,
    penalty_sum             NUMERIC,
    additional_payment_sum  NUMERIC,
    bank_payment_sum        NUMERIC,
    source_run_id           TEXT NOT NULL,
    raw_payload_json        TEXT,
    PRIMARY KEY (seller_account_id, report_id)
);

CREATE INDEX ix_finance_report_period
    ON fact_finance_report(seller_account_id, date_from, date_to, report_status);
```

```sql
CREATE TABLE fact_finance_event (
    seller_account_id       INTEGER NOT NULL REFERENCES dim_seller_account(seller_account_id),
    rrd_id                  TEXT NOT NULL,
    report_id               TEXT,
    srid                    TEXT,
    product_sk              INTEGER REFERENCES dim_nomenclature(product_sk),
    variant_sk              INTEGER REFERENCES dim_product_variant(variant_sk),
    doc_type_name           TEXT,
    seller_oper_name        TEXT,
    bonus_type_name         TEXT,
    order_at                TEXT,
    sale_at                 TEXT,
    accounting_at           TEXT NOT NULL,
    quantity                NUMERIC,
    retail_price_with_disc  NUMERIC,
    retail_amount           NUMERIC,
    for_pay                 NUMERIC,
    acquiring_fee           NUMERIC,
    delivery_service        NUMERIC,
    paid_storage            NUMERIC,
    paid_acceptance         NUMERIC,
    deduction               NUMERIC,
    penalty                 NUMERIC,
    additional_payment      NUMERIC,
    rebill_logistic_cost    NUMERIC,
    rebill_logistic_org     TEXT,
    operation_class         TEXT NOT NULL,
    p_and_l_treatment       TEXT NOT NULL,
    source_run_id           TEXT NOT NULL,
    retrieved_at            TEXT NOT NULL,
    quality_status          TEXT NOT NULL,
    finality_status         TEXT NOT NULL,
    classifier_version      TEXT NOT NULL,
    raw_payload_json        TEXT,
    created_at              TEXT NOT NULL,
    updated_at              TEXT NOT NULL,
    PRIMARY KEY (seller_account_id, rrd_id)
);

CREATE INDEX ix_finance_srid
    ON fact_finance_event(seller_account_id, srid);
CREATE INDEX ix_finance_product_accounting
    ON fact_finance_event(seller_account_id, product_sk, accounting_at);
CREATE INDEX ix_finance_report
    ON fact_finance_event(seller_account_id, report_id);
CREATE INDEX ix_finance_class
    ON fact_finance_event(seller_account_id, operation_class, accounting_at);
```

Новые неизвестные `sellerOperName + bonusTypeName` получают `UNKNOWN_REVIEW`, а не автоматически попадают в `other expenses`.

## 9.6. Funnel history

```sql
CREATE TABLE fact_funnel_snapshot (
    seller_account_id        INTEGER NOT NULL REFERENCES dim_seller_account(seller_account_id),
    product_sk               INTEGER NOT NULL REFERENCES dim_nomenclature(product_sk),
    business_day             TEXT NOT NULL,
    retrieved_at             TEXT NOT NULL,
    open_count               INTEGER,
    cart_count               INTEGER,
    order_count              INTEGER,
    order_sum                NUMERIC,
    buyout_count             INTEGER,
    buyout_sum               NUMERIC,
    buyout_percent           NUMERIC,
    add_to_cart_conversion   NUMERIC,
    cart_to_order_conversion NUMERIC,
    wishlist_count           INTEGER,
    source_run_id            TEXT NOT NULL,
    quality_status           TEXT NOT NULL,
    finality_status          TEXT NOT NULL,
    revision_hash            TEXT NOT NULL,
    raw_payload_json         TEXT,
    PRIMARY KEY (seller_account_id, product_sk, business_day, retrieved_at)
);

CREATE INDEX ix_funnel_current_lookup
    ON fact_funnel_snapshot(seller_account_id, product_sk, business_day, retrieved_at DESC);
CREATE INDEX ix_funnel_day
    ON fact_funnel_snapshot(seller_account_id, business_day);
```

Current Funnel — view с последним snapshot. История не перезаписывается.

## 9.7. Stocks snapshots

```sql
CREATE TABLE dim_warehouse (
    warehouse_sk        INTEGER PRIMARY KEY,
    seller_account_id   INTEGER REFERENCES dim_seller_account(seller_account_id),
    marketplace         TEXT NOT NULL,
    external_warehouse_id TEXT,
    warehouse_name      TEXT NOT NULL,
    warehouse_type      TEXT NOT NULL,
    region_name         TEXT,
    is_aggregate        INTEGER NOT NULL DEFAULT 0,
    is_active           INTEGER NOT NULL DEFAULT 1,
    UNIQUE (seller_account_id, marketplace, external_warehouse_id, warehouse_name),
    CHECK (is_aggregate IN (0,1)),
    CHECK (is_active IN (0,1))
);
```

```sql
CREATE TABLE fact_stock_snapshot (
    seller_account_id  INTEGER NOT NULL REFERENCES dim_seller_account(seller_account_id),
    product_sk         INTEGER NOT NULL REFERENCES dim_nomenclature(product_sk),
    variant_sk         INTEGER REFERENCES dim_product_variant(variant_sk),
    warehouse_sk       INTEGER NOT NULL REFERENCES dim_warehouse(warehouse_sk),
    retrieved_at       TEXT NOT NULL,
    quantity           NUMERIC,
    in_way_to_client   NUMERIC,
    in_way_from_client NUMERIC,
    source_run_id      TEXT NOT NULL,
    quality_status     TEXT NOT NULL,
    finality_status    TEXT NOT NULL,
    raw_payload_json   TEXT,
    PRIMARY KEY (seller_account_id, product_sk, variant_sk, warehouse_sk, retrieved_at)
);

CREATE INDEX ix_stock_latest_product
    ON fact_stock_snapshot(seller_account_id, product_sk, retrieved_at DESC);
CREATE INDEX ix_stock_latest_warehouse
    ON fact_stock_snapshot(seller_account_id, warehouse_sk, retrieved_at DESC);
```

Отсутствие строки не материализуется как `quantity=0` без полного catalog universe и подтверждённого endpoint contract.

## 9.8. Остальные typed facts

Следующие таблицы проектируются по тому же принципу:

```text
fact_price_snapshot
fact_ad_day
fact_storage_event
fact_acceptance_event
fact_inventory_1c
fact_cost_snapshot
```


---

# 10. Правила source authority

| Бизнес-вопрос | Authority | Дополнительный источник | Запрещённая подмена |
|---|---|---|---|
| Event-level Statistics demand | Statistics Orders `flag=1` | Funnel для диагностики | `Funnel.orderCount` вместо Orders |
| Full FBS operational order contour | Marketplace FBS Orders после аудита | Statistics Orders + crosswalk | простое сложение двух источников |
| Sale / Return lifecycle | Statistics Sales | Finance detailed | дедупликация Sales по `srid` |
| Финальные деньги закрытой недели | Finance weekly exact report | Finance daily для provenance | daily как final после появления weekly |
| Текущие деньги открытой недели | Finance daily | Sales для раннего lifecycle | объявление `SETTLED` до weekly report |
| Buyer funnel | Funnel | Orders/Sales для cross-check | использование Funnel как raw Orders count |
| Текущий WB stock | WB Stocks snapshot | catalog universe | missing row = zero |
| FBS stock по складу | Seller Stocks | 1С для operational comparison | объединение складов без warehouse key |
| SKU storage cost | Paid Storage | Finance weekly total | повторное списание обоих источников |
| FBS processing | Finance detailed | Acceptance при наличии FBW rows | вся `paidAcceptance` как единая статья без classifier |
| Product attributes | Content/catalog | Orders/Funnel/Finance fallback | регулярное переопределение по последнему факту |
| Internal product grouping | `dim_business_product` | article rules как seed | использование текущего `imtID` как стабильной группы |

---

# 11. Quality и finality statuses

## 11.1. Quality status

```text
UNKNOWN       — источник ещё не проверен
VALID         — обязательные проверки пройдены
PARTIAL       — ответ полезен, но coverage неполный
INVALID       — нарушен контракт или ключевая сверка
QUARANTINED   — данные сохранены, но не допускаются в release
NO_DATA       — корректный пустой ответ или отсутствующий источник
STALE         — превышен freshness SLA
```

## 11.2. Finality status

```text
PROVISIONAL   — данные доступны, но могут дозагружаться/пересчитываться
SETTLING      — наблюдается стабилизация, но порог finality не достигнут
SETTLED       — источник достиг определённого domain rule
SUPERSEDED    — существует более новая финальная версия
ROLLED_BACK   — версия снята с active release
NOT_APPLICABLE
```

## 11.3. Разделение

Примеры:

```text
Finance daily:
quality = VALID
finality = PROVISIONAL

Finance weekly после report list/exact-detail сверки:
quality = VALID
finality = SETTLED

Stocks 117/124:
quality = PARTIAL
finality = NOT_APPLICABLE

Funnel свежего дня:
quality = VALID
finality = PROVISIONAL или SETTLING
```

## 11.4. DDL-ограничение

Для SQLite возможны `CHECK`; в PostgreSQL позднее статусы выносятся в enums или reference tables.

---

# 12. Нужные продуктовые и служебные разделы

## 12.1. Первичные домены

1. **Каталог и товары** — `nmId`, `imtID`, артикул, бренд, предмет, категория, внутренняя группа, варианты и баркоды.
2. **Заказы** — Statistics Orders, Marketplace FBS Orders, дедуплицированная mart.
3. **Продажи и возвраты** — sale/return lifecycle.
4. **Воронка** — traffic, cart, order, buyout, revisions.
5. **Остатки** — WB, seller/FBS, 1С, товары в пути.
6. **Финансы** — report registry, atomic events, settled facts.
7. **Реклама** — кампании, расходы, бонусные расходы, статистика по SKU.
8. **Цены и промо** — seller price, buyer price, СПП, Wallet, promotions.
9. **Хранение и приёмка** — SKU-level costs и сверка с Finance.
10. **Себестоимость** — cost history с effective dates.


## 12.2. Производные бизнес-разделы

1. **Главный dashboard и сигналы**.
2. **Unit Economics**.
3. **FBS Operations**.
4. **Потребность, закупки и перемещения**.
5. **Basket / товары вместе** через `gNumber`.
6. **Product Performance** по `nmId`, `imtID`, `business_product_id`, subject, brand, category.
7. **P&L** по кабинету, бренду, предмету, группе, `nmId`, FBO/FBS.
8. **Data completeness dashboard** для оператора.

## 12.3. Служебные разделы

1. **Data Quality** — completeness, duplicates, lags, revisions, UNKNOWN mappings.
2. **Sources & Provenance** — run, endpoint, request params, SHA, parser/normalizer version.
3. **Reference Data Management** — product mappings, taxonomy overrides, warehouse mappings, Finance classifier.
4. **Release Management** — candidate, active, superseded, rollback.
5. **Operations Health** — timers, collectors, last success, last error, backup/restore evidence.
6. **Photo manager** — остаётся отдельным операционным инструментом, не analytics fact domain.

---

# 13. Dual-write и backfill

## Phase 0 — Freeze contracts

- зафиксировать текущий prepared API contract;
- сохранить контрольные V17 snapshots;
- зафиксировать primary evidence run;
- включить feature flags:

```text
TYPED_FACTS_WRITE
TYPED_FACTS_READ
SHADOW_RECONCILIATION
```

## Phase 1 — MDM schema

Создать:

```text
dim_seller_account
dim_brand
dim_category
dim_subject
dim_nomenclature
dim_wb_content_group
bridge_nm_imt_history
dim_business_product
bridge_nm_business_product
dim_product_variant
bridge_variant_barcode
dim_warehouse
```

Наполнить справочники из доступных исторических источников. Неизвестные карточки получают placeholder product с `quality_status=PARTIAL`, но факт не теряется.

## Phase 2 — Typed facts dual-write

Каждый ingest пишет одновременно:

```text
старый daily_fact
+
новую typed fact-table
```

Ошибка новой записи не должна разрушать старый production path. Ошибка старого path при успешном typed path также фиксируется отдельно.

## Phase 3 — Historical backfill

Порядок:

1. Orders;
2. Sales;
3. Finance reports/events;
4. Funnel snapshots;
5. Stocks snapshots;
6. Paid Storage;
7. Costs/1С;
8. Ads/prices после готовности sources.

Для каждого batch:

- source artifact ID;
- run ID;
- normalizer version;
- row counts;
- min/max business date;
- duplicate counts;
- checksum.

Backfill идемпотентен по естественному PK.

## Phase 4 — Shadow marts

Строятся параллельные mart tables/views:

```text
mart_orders_daily_v2
mart_sales_lifecycle_v2
mart_finance_weekly_v2
mart_stock_current_v2
mart_product_performance_v2
mart_unit_economics_v2
```

Они не видны пользователю до прохождения сверок.

## Phase 5 — Shadow prepared snapshots

Новый builder создаёт:

```text
prepared_snapshot calc_version = V18_TYPED_SHADOW
```

Старый V17 snapshot остаётся active. Диагностика сравнивает обе версии.

## Phase 6 — Cutover

Переключение выполняется отдельно по разделам:

```text
catalog → stocks → orders → sales → finance → unit economics → FBS
```

Условие cutover:

- три последовательных успешных фоновых цикла;
- row-count reconciliation;
- metric reconciliation;
- accepted performance;
- UI contract compatibility;
- rollback tested.

## Phase 7 — Deprecation

После согласованного наблюдаемого периода:

- `daily_fact` остаётся read-only compatibility layer;
- write-path отключается;
- старые adapters помечаются deprecated;
- удаление выполняется только отдельным решением и после backup/restore drill.

---

# 14. План переключения UI

## 14.1. API не меняется одномоментно

Текущий endpoint:

```text
/api/v17/section/<section>
```

сохраняет response contract. Меняется только источник prepared snapshot.

## 14.2. Compatibility adapter

Новый mart-to-prepared adapter должен выдавать те же:

- `summary`;
- `columns`;
- `rows`;
- `status`;
- `completeness`;
- pagination metadata;
- download contracts.

## 14.3. Feature flag per section

```text
READ_SOURCE_STOCKS=V17|TYPED
READ_SOURCE_ORDERS=V17|TYPED
READ_SOURCE_FINANCE=V17|TYPED
...
```

Переключение независимо по доменам.

## 14.4. Shadow comparison

До UI cutover каждый запрос может сравнивать metadata двух snapshot без выдачи второго пользователю:

```text
row_count
checksum
summary metrics
missing entities
quality/finality
build duration
```

## 14.5. Rollback

Rollback — смена release pointer/feature flag на предыдущий snapshot. Повторный backfill или ручное восстановление таблиц для обычного UI rollback не требуется.

---

# 15. DDL и индексы: обязательный минимальный набор

Основной DDL приведён в разделах 4–9. Дополнительно обязательны:

## 15.1. Release registry

```sql
CREATE TABLE data_release (
    release_id         INTEGER PRIMARY KEY,
    release_name       TEXT NOT NULL UNIQUE,
    status             TEXT NOT NULL,
    candidate_run_id   TEXT NOT NULL,
    created_at         TEXT NOT NULL,
    activated_at       TEXT,
    superseded_at      TEXT,
    rolled_back_at     TEXT,
    manifest_json      TEXT NOT NULL,
    checksum           TEXT NOT NULL,
    CHECK (status IN ('CANDIDATE','ACTIVE','SUPERSEDED','QUARANTINED','ROLLED_BACK'))
);

CREATE UNIQUE INDEX ux_one_active_release
    ON data_release(status)
    WHERE status = 'ACTIVE';
```

## 15.2. Fact-to-release membership

```sql
CREATE TABLE release_domain_pointer (
    release_id       INTEGER NOT NULL REFERENCES data_release(release_id),
    domain_name      TEXT NOT NULL,
    domain_version   TEXT NOT NULL,
    source_run_id    TEXT NOT NULL,
    quality_status   TEXT NOT NULL,
    finality_status  TEXT NOT NULL,
    row_count        INTEGER NOT NULL,
    checksum         TEXT NOT NULL,
    PRIMARY KEY (release_id, domain_name)
);
```

## 15.3. Attribute conflict queue

```sql
CREATE TABLE reference_conflict (
    conflict_id       INTEGER PRIMARY KEY,
    seller_account_id INTEGER NOT NULL,
    product_sk        INTEGER,
    attribute_name    TEXT NOT NULL,
    value_a           TEXT,
    source_a          TEXT,
    value_b           TEXT,
    source_b          TEXT,
    status            TEXT NOT NULL DEFAULT 'OPEN',
    resolution        TEXT,
    created_at        TEXT NOT NULL,
    resolved_at       TEXT,
    CHECK (status IN ('OPEN','RESOLVED','IGNORED'))
);

CREATE INDEX ix_reference_conflict_open
    ON reference_conflict(status, attribute_name, created_at);
```

## 15.4. Finance mapping

```sql
CREATE TABLE finance_operation_rule (
    rule_id              INTEGER PRIMARY KEY,
    seller_oper_name     TEXT,
    bonus_type_name      TEXT,
    doc_type_name        TEXT,
    operation_class      TEXT NOT NULL,
    p_and_l_treatment    TEXT NOT NULL,
    sign_rule            TEXT NOT NULL,
    priority             INTEGER NOT NULL,
    enabled              INTEGER NOT NULL DEFAULT 1,
    rule_version         TEXT NOT NULL,
    created_at           TEXT NOT NULL,
    updated_at           TEXT NOT NULL
);

CREATE INDEX ix_finance_rule_match
    ON finance_operation_rule(enabled, priority, seller_oper_name, bonus_type_name, doc_type_name);
```

## 15.5. Индексная стратегия

Обязательные индексы должны покрывать:

- `seller_account + business date`;
- `seller_account + product + date`;
- `srid` lifecycle;
- `saleID`, `rrdId`, `reportId` uniqueness;
- latest snapshot by product/warehouse;
- current bridge membership;
- open conflicts;
- release pointer.

JSON indexes на первом SQLite-этапе не являются заменой typed columns.

---

# 16. Acceptance criteria

## AC-01 — seller account separation

Два бренда одного кабинета и одинаковые артикулы разных кабинетов не смешиваются.

## AC-02 — nomenclature lookup

По `seller_account_id + nmId` однозначно находятся product, brand, subject, category и internal group.

## AC-03 — content group history

При смене `imtID` старая membership закрывается, новая создаётся, исторические факты не переписываются.

## AC-04 — business group independence

Изменение `imtID` не меняет `business_product_id` без отдельного mapping decision.

## AC-05 — barcode history

Несколько barcode одного `nmId` сохраняются без потери; current barcode определяется по подтверждённому source.

## AC-06 — Orders uniqueness

Повторная загрузка одного `srid` не создаёт дубликат.

## AC-07 — Sales uniqueness

`S...` и `R...` одного `srid` сохраняются как два события; дедупликация выполняется только по `saleID`.

## AC-08 — Finance uniqueness

Повторная загрузка `rrdId` идемпотентна.

## AC-09 — source authority

Funnel никогда не заменяет event-level Orders count в demand mart.

## AC-10 — Finance finality

При появлении weekly report closed-week mart переключается с daily provisional на weekly settled.

## AC-11 — missing stocks

Отсутствующая stock row не создаёт synthetic zero без catalog rule.

## AC-12 — mutable snapshots

Funnel и Stocks сохраняют history; current view выбирает последнюю версию.

## AC-13 — raw lineage

Каждый typed fact содержит `source_run_id` и восстанавливается до source registry/raw artifact.

## AC-14 — release atomicity

Incomplete или invalid domain не активирует candidate release.

## AC-15 — rollback

Предыдущий prepared release восстанавливается сменой pointer без пересчёта raw.

## AC-16 — UI compatibility

Существующие экраны и exports получают прежний контракт после переключения на typed marts.

## AC-17 — no heavy web work

Web не выполняет parsing, API calls, Excel scan или mart calculation.

## AC-18 — unknown classification

Неизвестная Finance operation попадает в `UNKNOWN_REVIEW`, а не в скрытый расход.

## AC-19 — cross-source evidence

Orders↔Sales, Sales↔Finance, Finance daily↔weekly и Storage↔Finance проверки выполняются автоматически.

## AC-20 — migration reversibility

До завершения observation period любой раздел может быть возвращён на V17 snapshot feature flag.

---

# 17. Тесты и сверки

## 17.1. Schema tests

- обязательные таблицы и индексы существуют;
- natural key constraints работают;
- FK violations блокируются;
- только одна current membership для `imtID` и business product;
- только один ACTIVE release.

## 17.2. Unit tests

- нормализация `nmId` и артикулов;
- приоритет источников справочника;
- создание/закрытие history intervals;
- hard-coded 901-rule перенесён в data rules;
- Finance classifier;
- finality state transitions;
- missing stock semantics.

## 17.3. Idempotency tests

Повторная загрузка одного raw artifact:

- не увеличивает Orders count;
- не увеличивает Sales count;
- не увеличивает Finance count;
- не дублирует bridge membership;
- создаёт audit event повторного ingest.

## 17.4. Migration tests

- backfill можно перезапустить после падения;
- batch checkpoint сохраняется;
- старый `daily_fact` остаётся доступным;
- schema upgrade не блокирует read-only web;
- rollback возвращает старый prepared snapshot.

## 17.5. Cross-source tests на primary evidence

Ожидаемые контрольные значения:

```text
Orders: 894, srid unique 894/894
Sales: 766, saleID unique 766/766
Sales↔Finance: 766/766 matched
Orders↔Sales common-window: 516 matched
Finance daily closed week: 2125
Finance weekly: 2125
Finance exact report detail: 2125
Paid Storage: 1434.846636 ₽
Finance paidStorage: 1434.80 ₽
```

Finance detailed schema test:

```text
union fields = 91
row field count = 89 or 90
rebillLogisticOrg is conditional
```

## 17.6. Performance tests

На текущем объёме целевые ориентиры:

- lookup по `nmId` < 50 мс;
- daily mart по одному кабинету/месяцу < 2 с в background build;
- UI prepared snapshot read < 300 мс без network latency;
- custom period не открывает raw Excel/API files;
- full backfill выполняется batch-wise без удержания долгой write lock.

## 17.7. UI regression

Проверить:

- все стандартные периоды;
- custom period queue;
- finance compatibility endpoint;
- exports;
- pagination;
- empty/partial/stale statuses;
- отображение previous snapshot при failed candidate.

## 17.8. Security and privacy tests

- tokens отсутствуют в DB/report/log;
- raw client IDs не попадают в docs;
- surrogate seller account используется в published artifacts;
- debug export не раскрывает secrets;
- SQL queries parameterized.

---

# 18. Разбиение реализации на Jira-задачи

Ниже — инженерный backlog после закрытия PMM-58/PMM-59 как аналитических/docs-only задач.

| Порядок | Предлагаемая задача | Scope | Зависимости | DoD |
|---:|---|---|---|---|
| 1 | **Data model foundation: seller account + nomenclature MDM** | `dim_seller_account`, taxonomy, `dim_nomenclature`, migrations | PMM-59 | schema tests, seed, lookup API |
| 2 | **Product hierarchy: imt history + business groups + variants** | content groups, history bridge, business mappings, barcode history | задача 1 | current/history tests, manual override |
| 3 | **Typed Orders/Sales facts** | separate event tables, dual-write, idempotency | задачи 1–2, PMM-61 | 894/766 evidence reconciliation |
| 4 | **Typed Finance facts and classifier** | reports, events, weekly finality, UNKNOWN queue | задача 1 | 2125/2125/2125 reconciliation |
| 5 | **Snapshot facts: Funnel, Stocks, Storage** | append-only revisions, current views | задачи 1–2 | revision and missing-row tests |
| 6 | **Marts and source-authority layer** | daily demand, lifecycle, P&L, stocks, product performance | задачи 3–5 | trust-map encoded and tested |
| 7 | **Prepared snapshot V2 + UI compatibility** | adapters, feature flags, shadow snapshots | задача 6 | pixel/API regression, exports |
| 8 | **Backfill, release controller and cutover** | batch backfill, checksums, release pointer, rollback | задачи 3–7 | three green cycles, rollback drill |
| 9 | **Internal provenance audit** | raw → typed fact → mart → prepared → UI | задача 8, PMM-62 | orphan checks, SourceRef trace |
| 10 | **Arrival-lag/finality calibration** | longitudinal Orders/Sales SLA | PMM-60 | time-to-95/99 and PROVISIONAL rule |

---

# 19. План принятия решения

PMM-58 и PMM-59 могут быть закрыты как законченные аналитические/docs-only deliverables при наличии трёх документов:

```text
docs/analytics/2026-09-03-data-quality.md
docs/analytics/2026-09-03-wb-data-dictionary.md
docs/architecture/target-data-model-and-v17-migration.md
```

Их закрытие **не означает**, что physical migration уже реализована в production. Реализация намеренно разложена на отдельные инженерные задачи раздела 18.

Финальный архитектурный вердикт:

> V17 сохраняется как надёжный prepared-data shell. Источник истины постепенно переносится из универсального `daily_fact`/JSON в dimensions и typed domain facts. Переключение выполняется через dual-write, shadow reconciliation, per-section feature flags и release pointer, без одномоментного переписывания приложения.
