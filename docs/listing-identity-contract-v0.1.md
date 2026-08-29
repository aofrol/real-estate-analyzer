# Listing Identity Contract v0.1

## 1. Purpose

Этот документ фиксирует контракт идентичности и будущего persistence поведения
для нормализованных объявлений недвижимости.

Документ является design/domain contract для следующих границ:

```text
RawListing
    ↓
NormalizedListing
    ↓
Building / Property
    ↓
Listing identity + persistence
    ↓
Price history / cross-source deduplication
```

Цель контракта — не смешивать:

- физический объект недвижимости;
- объявление одного источника;
- сырой payload, полученный при сборе;
- гипотезу о том, что объявления из разных источников представляют одно
  коммерческое предложение.

Этот документ не реализует Listing persistence, price history или
deduplication.

## 2. Terminology

### Property

Физическая квартира или иной unit внутри Building. Один Property может быть
связан с несколькими объявлениями.

### Source

Marketplace или иной источник, который владеет namespace внешних идентификаторов
объявлений.

### RawListing

Сырой source payload, сохранённый ingestion layer. Он нужен для повторной
нормализации и аудита входных данных.

### Listing

Нормализованная identity-запись одного объявления конкретного Source.

### Commercial offer

Гипотеза о конкретном рыночном предложении. Она не является hard identity
Listing и может быть определена только отдельным deduplication/classification
слоем.

## 3. Identity layers

В системе существуют три разные identity:

### 3.1. Physical Property identity

Представляет реальную квартиру/unit и принадлежит `Property`.

Её ключ — `Property.id`.

### 3.2. Source Listing identity

Представляет одно объявление в namespace конкретного источника.

Hard key:

```text
(source_id, external_id)
```

`external_id` meaningful только внутри одного Source namespace.

### 3.3. Cross-source offer identity

Представляет гипотезу, что два разных source listings описывают одно
коммерческое предложение.

Это не hard identity. Эквивалентность может быть эвристической и должна
определяться отдельным deduplication/classification layer.

## 4. Current Listing ORM schema relevant to identity

Фактическая модель `Listing` содержит:

| Поле | ORM type | NULL | Default | Контракт |
|---|---|---:|---|---|
| `id` | UUID primary key | no | UUID application/default | Стабильный внутренний идентификатор Listing |
| `property_id` | UUID FK → `properties.id` | no | — | Текущий физический Property объявления |
| `source_id` | UUID FK → `sources.id` | no | — | Source namespace объявления |
| `external_id` | `String(200)` | no | — | Source-native opaque advertisement identifier |
| `url` | `Text` | yes | — | Mutable source metadata |
| `asking_price` | `BigInteger` | no | — | Текущая цена в kopecks |
| `asking_price_per_sqm` | `BigInteger` | no | — | Текущая цена за м² в kopecks |
| `status` | `String(10)` | no | `"active"` | Текущее состояние объявления |
| `listed_at` | `DateTime(timezone=True)` | yes | — | Source-reported publication timestamp |
| `removed_at` | `DateTime(timezone=True)` | yes | — | Source-reported removal timestamp, если есть |
| `location` | PostGIS `Geography(Point, 4326)` | yes | — | Координаты объявления, не identity |
| `duplicate_of_id` | UUID self-FK → `listings.id` | yes | — | Связь с canonical Listing при классификации duplicate |
| `extra` | JSONB | yes | `'{}'` | Source-specific metadata |
| `created_at` | `DateTime(timezone=True)` | no | `now()` | System audit timestamp |
| `updated_at` | `DateTime(timezone=True)` | no | `now()` | System audit timestamp |

### 4.1. Listing constraints and indexes

Unique constraint:

```text
uq_listings_source_external
UNIQUE(source_id, external_id)
```

Indexes:

```text
PRIMARY KEY (id)
UNIQUE (source_id, external_id)
ix_listings_location_active
    GiST(location)
    WHERE duplicate_of_id IS NULL AND status = 'active'
ix_listings_status
    BTREE(status)
ix_listings_listed_at
    BTREE(listed_at)
ix_listings_property_id
    BTREE(property_id)
ix_listings_duplicate_of_id_notnull
    BTREE(duplicate_of_id)
    WHERE duplicate_of_id IS NOT NULL
```

`property_id` не уникален и не должен становиться unique constraint.

## 5. Hard Listing identity

Hard Listing identity определяется только парой:

```text
(source_id, external_id)
```

Правила:

- одинаковые `source_id` и `external_id` означают один Listing identity;
- одинаковый `external_id` в разных Sources означает разные Listing identities;
- разные `external_id` в одном Source означают разные Listing identities;
- `property_id` не является Listing identity;
- `url` не является Listing identity;
- `source_id + external_id` нельзя заменять нормализованным URL, адресом,
  ценой или характеристиками Property;
- `external_id` opaque: нельзя предполагать, что он numeric, globally unique
  или содержит бизнес-смысл.

Уже существующая database unique constraint соответствует этому контракту.

## 6. Relationship to Property

`Listing.property_id` — это физический Property, с которым сейчас связано
объявление.

Каждый Listing указывает ровно на один Property, потому что
`property_id` является `NOT NULL` FK.

Один Property может иметь:

- один Listing;
- несколько Listings одного Source;
- Listings разных Sources;
- Listings, которые позднее окажутся duplicates;
- Listings, которые являются разными коммерческими предложениями.

Пример допустимой структуры:

```text
Property A
├── Source X / external 100
├── Source X / external 200
└── Source Y / external ABC
```

Listings нельзя объединять только потому, что у них одинаковый `property_id`.

## 7. Relationship to Source

`Listing.source_id` — Source, который владеет внешней identity объявления.

Source-relevant fields:

| Поле Source | ORM type | NULL | Контракт |
|---|---|---:|---|
| `id` | UUID primary key | no | Namespace identifier |
| `name` | `String(100)` | no | Unique human-readable name |
| `base_url` | `Text` | yes | Source metadata, не identity Listing |
| `is_active` | Boolean | no | Управляет активностью Source |
| `adapter_class` | `String(200)` | no | Adapter configuration |
| `config` | JSONB | yes | Adapter-specific configuration |

`source_id` нельзя менять у уже существующего Listing в ходе обычной
persistence. Перенос Listing между Source namespaces требует отдельной
операции/миграции identity.

## 8. External ID contract

`external_id` — стабильный source-native идентификатор объявления.

Требования:

- не пустой;
- meaningful только внутри namespace `source_id`;
- opaque application value;
- не обязан быть numeric;
- не обязан быть globally unique;
- разные source IDs нельзя canonicalize в один общий ID;
- изменение `external_id` означает другую source Listing identity.

Обычная Listing persistence не должна менять `external_id`.

## 9. Same-source reobservation behavior

Если повторно получена та же пара:

```text
source_id + external_id
```

это повторное наблюдение существующего Listing, а не новый Listing.

Ожидаемое поведение будущего Listing persistence:

1. найти существующий Listing;
2. сохранить его `id`;
3. проверить source identity;
4. проверить, что Property не изменился неожиданно;
5. обновить разрешённые mutable marketplace fields;
6. не создавать вторую строку;
7. отдельно обработать изменение цены через price-history boundary;
8. не менять `source_id`, `external_id` или `duplicate_of_id` обычным side
   effect.

Повторная загрузка не должна порождать новый Listing только потому, что
объявление было снова собрано.

## 10. Listing field classification

### 10.1. Identity / stable fields

```text
id
source_id
external_id
```

Они сохраняются при повторной обработке того же source listing identity.

### 10.2. Relational fields

```text
property_id
duplicate_of_id
```

`property_id` связывает объявление с физическим Property.
`duplicate_of_id` принадлежит отдельному deduplication/classification процессу.

### 10.3. Mutable marketplace state

```text
url
asking_price
asking_price_per_sqm
status
listed_at
removed_at
location
extra
```

Их можно обновлять при повторном наблюдении согласно отдельной persistence
политике и source payload.

### 10.4. Audit / system fields

```text
created_at
updated_at
```

`created_at` должен оставаться временем создания Listing.
`updated_at` отражает системное изменение строки.

## 11. Status contract

Текущий ORM использует обычный `String(10)` с default `"active"`.

В модели и применённой Alembic migration нет DB CHECK constraint, который
закрывал бы список значений. Комментарии модели и design docs называют
текущими значениями:

```text
active
sold
removed
```

Это documented vocabulary, но не enforced closed enum.

До появления отдельного status contract нельзя придумывать дополнительные
значения или превращать строковое поле в enum без отдельного решения.

При повторной collection `status` может обновляться, если source действительно
сообщает новое состояние. История всех status transitions текущей схемой не
представлена.

## 12. Listed-at and observation time

`listed_at` означает source-reported original publication timestamp.

Он не означает время последнего наблюдения и не должен автоматически
перезаписываться текущим временем collection.

Если source сообщает новую publication value, возможность её обновления должна
быть отдельной явно принятой policy. Обычная collection time не является
значением `listed_at`.

У `Listing` нет отдельного `last_seen_at` или `observed_at`.

Это gap для будущего ingestion/persistence дизайна: время последнего наблюдения
нельзя надёжно выразить в текущей Listing schema.

## 13. Price and money units

Текущие поля:

```text
Listing.asking_price           BIGINT
Listing.asking_price_per_sqm   BIGINT
ListingPriceHistory.asking_price BIGINT
```

Модель и design docs явно указывают, что эти значения хранятся в kopecks.

Canonical application values:

```text
NormalizedListing.asking_price_kopecks
NormalizedListing.asking_price_per_sqm_kopecks
```

Task #5.18 должен переносить эти значения по имени и смыслу напрямую:

```text
asking_price           ← asking_price_kopecks
asking_price_per_sqm   ← asking_price_per_sqm_kopecks
```

Persistence не должна повторно пересчитывать `asking_price_per_sqm`, если
отдельный контракт не потребует этого. Оба значения должны оставаться
согласованными с canonical normalized input.

## 14. Price-change behavior

Если существующий Listing снова наблюдается с другой ценой:

1. его Listing identity остаётся прежней;
2. `Listing.id` сохраняется;
3. текущие `asking_price` и `asking_price_per_sqm` обновляются;
4. изменение фиксируется в `ListingPriceHistory`;
5. новый Listing не создаётся только из-за изменения цены.

Price update и Listing identity — разные concerns.

## 15. ListingPriceHistory semantics

Фактическая модель `ListingPriceHistory` содержит:

| Поле | ORM type | NULL | Default | Контракт |
|---|---|---:|---:|---|
| `id` | UUID primary key | no | UUID application/default | History row identity |
| `listing_id` | UUID FK → `listings.id` | no | — | Listing whose price changed |
| `asking_price` | `BigInteger` | no | — | Price in kopecks |
| `recorded_at` | `DateTime(timezone=True)` | no | `now()` | Time the price change was recorded |

FK behavior:

```text
ON DELETE CASCADE
ON UPDATE CASCADE
```

Индекс:

```text
ix_listing_price_history_listing_recorded
BTREE(listing_id, recorded_at DESC)
```

Model docstring говорит, что history row создаётся при каждом обновлении
`asking_price`. Текущая модель не различает snapshots и changes отдельным
полем. Историческая persistence изолирована в `ListingPriceHistoryService`;
`ListingPersistenceService` отвечает только за current Listing state.

Правило MVP:

```text
создавать ListingPriceHistory row только когда persisted current price
изменился
```

Это избегает повторных одинаковых rows при неизменной цене и согласуется с
текущим смыслом «хронология изменений цены».

## 16. duplicate_of_id semantics

`duplicate_of_id` означает:

> этот Listing классифицирован как duplicate другого Listing, который
> представляет то же коммерческое предложение.

Он не означает:

- тот же Property;
- тот же source identity;
- superseded Listing;
- предыдущую версию Listing;
- predecessor цены;
- lineage RawListing snapshot;
- повторное наблюдение.

Listings не удаляются; duplicate relationship сохраняется отдельным
self-reference.

### 16.1. Canonical Listing

Canonical Listing:

```text
duplicate_of_id IS NULL
```

Duplicate Listing:

```text
duplicate_of_id указывает прямо на canonical Listing
```

Для MVP запрещены duplicate chains:

```text
нежелательно: A -> B -> C
предпочтительно: B -> A
                C -> A
```

Текущая schema не содержит DB-enforced защиты от chain. Это будущий
deduplication persistence guardrail.

Обычная Listing persistence должна:

- создавать новый Listing с `duplicate_of_id=None`;
- сохранять существующий `duplicate_of_id` при reuse;
- не очищать и не переписывать `duplicate_of_id`;
- не принимать deduplication decisions.

## 17. Property reassignment conflict

Если существующая hard Listing identity:

```text
source_id + external_id
```

при очередном наблюдении разрешается в другой Property, это
data-consistency conflict.

Обычная persistence должна fail closed:

```text
existing Listing + different property_id
    → ValueError
```

Нельзя молча менять `property_id`, потому что это может переместить одну
source identity между физическими объектами.

Будущее явное исправление может быть оформлено отдельным review/rematching/
reassignment workflow.

## 18. RawListing identity behavior

Фактическая модель `RawListing` содержит:

| Поле | ORM type | NULL | Default |
|---|---|---:|---|
| `id` | UUID primary key | no | UUID application/default |
| `source_id` | UUID FK → `sources.id` | no | — |
| `external_id` | `String(200)` | no | — |
| `raw_data` | JSONB | no | — |
| `collected_at` | `DateTime(timezone=True)` | no | `now()` |
| `is_processed` | Boolean | no | `false` |
| `created_at` | `DateTime(timezone=True)` | no | `now()` |

Constraint:

```text
uq_raw_listings_source_external
UNIQUE(source_id, external_id)
```

Index:

```text
ix_raw_listings_processed_collected
BTREE(is_processed, collected_at)
```

`SQLAlchemyRawListingRepository` всегда создаёт новый `RawListing`, вызывает
`add()` и `flush()`. Он не выполняет reuse/update logic.

`IngestionService` передаёт каждый raw payload в repository с application-
supplied `source_id` и `external_id`; он не занимается нормализацией,
дедупликацией или reconciliation.

## 19. Is RawListing a real immutable journal?

Нет, текущая schema не может хранить несколько отдельных наблюдений с одной и
той же парой:

```text
source_id + external_id
```

Второй insert нарушит `UNIQUE(source_id, external_id)`.

Поэтому фактическое значение текущей RawListing schema:

```text
одна raw record на source listing identity
```

а не:

```text
immutable multi-observation journal
```

Есть документационный конфликт:

- model/documents называют `raw_listings` immutable и audit journal;
- database uniqueness разрешает только одну запись на source listing identity;
- repository не реализует history/snapshot storage.

Следовательно, слово «immutable» сейчас означает, что сохранённый payload не
изменяется после записи, но не означает, что все collection observations
сохраняются.

## 20. Raw journal recommendation

### Option A — сохранить текущую uniqueness

```text
UNIQUE(source_id, external_id)
```

Semantics:

```text
latest/first raw source record per source listing identity
```

Плюсы:

- простая схема;
- idempotent identity;
- нет миграции;
- Listing persistence может двигаться дальше без блокировки.

Минусы:

- нет immutable multi-observation history;
- невозможно восстановить каждый исходный payload во времени;
- сложнее расследовать изменения source payload.

### Option B — разрешить несколько observations

Возможные identity fields:

```text
source_id + external_id + collected_at
```

или:

```text
source_id + external_id + content_hash + collected_at
```

Плюсы:

- настоящий raw audit journal;
- изменения source payload сохраняются;
- replay и debugging проще.

Минусы:

- нужна schema/migration работа;
- больше storage;
- потребуется отдельная ingestion idempotency policy;
- необходимо решить, допускаются ли одинаковые payload snapshots.

### Рекомендация

Для MVP временно оставить Option A и явно считать RawListing:

```text
latest/first raw source record per source listing identity
```

Не считать её полноценным immutable journal.

Технический долг:

```text
RawListing observation history / immutable ingestion journal
```

должен быть решён отдельной задачей после стабилизации MVP ingestion semantics.

## 21. Listing uniqueness and concurrency

Listing schema уже содержит:

```text
UNIQUE(source_id, external_id)
```

Это закрывает schema-hardening gap для hard Listing identity и защищает от
конкурентного создания двух Listing rows с одной source identity.

Однако application flow:

```text
lookup(source_id, external_id)
if absent:
    create
```

сам по себе всё равно не является достаточным: два concurrent workers могут
одновременно увидеть отсутствие строки.

Database unique constraint является финальным race-condition guardrail.
Task #5.18 должен быть готов обработать unique violation/concurrent reuse
согласно transaction policy верхнего уровня, не создавая вторую Listing.

Для RawListing такой же unique constraint существует, но он выражает
одну-record-per-source-identity policy, а не multi-observation journal.

## 22. Recommended Task #5.18 API

Рекомендуемая сигнатура:

```python
class ListingPersistenceService:
    def persist(
        self,
        *,
        source_id: UUID,
        property_id: UUID,
        listing: NormalizedListing,
    ) -> Listing:
        ...
```

Причины выбора UUID вместо opaque string keys:

- `ListingPersistenceService` будет ORM-aware, как
  `PropertyPersistenceService`;
- `Source` и `Property` являются UUID FK targets;
- Building/Property application keys уже парсятся на persistence boundary;
- типы `source_id` и `property_id` можно проверить до ORM access;
- hard Listing lookup естественно выражается через `source_id` и
  `listing["external_id"]`.

Сервис должен принимать injected Session и не владеть transaction lifecycle.

## 23. Future Task #5.18 behavior

### 23.1. Create case

Если Listing не существует по:

```text
source_id + listing["external_id"]
```

будущий сервис должен:

1. проверить Source;
2. проверить Property;
3. создать Listing;
4. установить `duplicate_of_id=None`;
5. перенести canonical marketplace state;
6. перенести:
   ```text
   asking_price_kopecks
   asking_price_per_sqm_kopecks
   source_url → url
   listed_at
   ```
7. установить `property_id` и `source_id`;
8. добавить объект;
9. выполнить `flush()`;
10. не выполнять `commit()`.

Не следует использовать `url`, Property fields, address, price или
`source_id` отдельно как Listing identity.

### 23.2. Reuse case

Если Listing уже существует для той же source identity:

1. вернуть и сохранить тот же `Listing.id`;
2. проверить `source_id` и `external_id`;
3. проверить совпадение `property_id`;
4. при mismatch fail closed;
5. обновить разрешённые mutable fields;
6. сохранить существующий `duplicate_of_id`;
7. не создавать новый Listing;
8. выполнять `flush()` только согласно явной implementation policy;
9. не выполнять `commit()`.

`source_id` и `external_id` не изменяются.

### 23.3. Property conflict

```text
existing Listing + different property_id
    → ValueError
```

Не выполнять молчаливое reassignment.

### 23.4. Duplicate behavior

Task #5.18 не принимает cross-source dedup decisions:

- новый Listing создаётся с `duplicate_of_id=None`;
- reuse сохраняет существующий `duplicate_of_id`;
- обычная persistence не очищает и не переписывает duplicate relationship.

## 24. PriceHistory boundary

Отдельный сервис исторической persistence:

```python
class ListingPriceHistoryService:
    ...
```

Его ответственность:

- принять предыдущую и новую текущую цену;
- сравнить их и вернуть `None`, если цена не изменилась;
- добавить `ListingPriceHistory`, если цена изменилась;
- сохранить новую наблюдаемую цену в `ListingPriceHistory.asking_price`;
- выполнить `add()` и один `flush()` только для изменения;
- использовать kopecks;
- не определять Listing identity;
- не менять `property_id`;
- не выполнять deduplication;
- не владеть transaction lifecycle.

`ListingPersistenceService` сохраняет только current Listing state: identity,
Property consistency, current prices, URL, `listed_at` и
`duplicate_of_id` preservation. Он не создаёт history rows и не вызывает
`ListingPriceHistoryService`.

Для существующего Listing orchestration выполняет операции в таком порядке:

1. захватывает persisted previous asking price;
2. определяет новую canonical price;
3. сохраняет или обновляет current Listing state;
4. вызывает `ListingPriceHistoryService`, если previous и new price различаются;
5. caller commits enclosing transaction.

Обе persistence-операции участвуют в одной транзакции, которой владеет caller.
Если history persistence завершается ошибкой, внешний orchestration может
откатить всю транзакцию.

Фактическая application boundary — `ListingPersistenceOrchestrator` в ingestion
layer. Она:

- вызывает `ListingPersistenceService.find_existing()` до любой мутации;
- захватывает `existing.asking_price` и incoming canonical price;
- вызывает `ListingPersistenceService.persist()` для current state;
- вызывает `ListingPriceHistoryService.record_change()` только для
  существующего Listing с изменившейся ценой;
- не вызывает `commit()`, `rollback()` или `close()`.

Worker-facing boundary `persist_refreshed_listing()` принимает caller-owned
`Session` и строит оба persistence-сервиса на ней через
`ListingPersistenceOrchestrator.from_session()`. Запланированная Celery-задача
пока остаётся stub до появления выборки locations, но индивидуальная normalized
Listing write boundary уже не позволяет обойти общий orchestration-поток.
Ошибка history persistence не перехватывается внутренними сервисами и может
откатить всю caller-owned transaction.

## 25. Future Task #5.20 Dedup boundary

Cross-source deduplication должна быть отдельной цепочкой:

```text
Listing candidates
    ↓
Dedup Matcher / Classifier
    ↓
Dedup Resolution
    ↓
duplicate_of_id assignment
```

Deduplication нельзя выводить автоматически из:

- одинакового `property_id`;
- одинаковой цены;
- одинаковой площади;
- одинакового URL pattern;
- одинакового адреса;
- одинаковых source external IDs;
- одинакового status.

Только отдельный dedup classifier может предложить relationship, а отдельная
persistence policy — применить её.

## 26. Decision table

| Case | `source_id` | `external_id` | Property | Price | Expected result |
|---|---|---|---|---|---|
| 1 | same | same | same | same | Reuse the same Listing |
| 2 | same | same | same | changed | Reuse Listing; later record price change |
| 3 | same | same | different | any | Consistency error; do not silently reassign |
| 4 | same | different | same | any | Different Listing rows |
| 5 | different | same | same | any | Different Listing rows |
| 6 | different | different | same | any | Different Listing rows |
| 7 | different Listing rows later classified as same offer | — | — | — | Keep separate rows; later set `duplicate_of_id` through dedup layer |
| 8 | same | same | same or unchanged | repeated observation | Stable `Listing.id`; no new row |
| 9 | same | same | same | URL changed | Reuse Listing; URL is mutable metadata |
| 10 | same | same | same | status changed | Reuse Listing; update mutable status if source reports it |

## 27. Unresolved technical debt

### 27.1. RawListing observation journal

Current unique constraint prevents multiple immutable RawListing observations
for the same source identity.

Recommended future work:

```text
RawListing observation history / immutable ingestion journal
```

### 27.2. Listing status enforcement

Current `status` is a plain string with a default and documented vocabulary,
but no DB CHECK constraint. A future task should decide whether to enforce
allowed states.

### 27.3. Last observation timestamp

Listing has `listed_at`, but no `last_seen_at` or `observed_at`. Collection time
cannot be represented without overloading `listed_at`.

### 27.4. Duplicate chain prevention

The current self-FK permits conceptual chains such as `A -> B -> C`. A future
dedup persistence design should decide whether to enforce direct canonical
targets with application validation, a constraint, or a trigger.

### 27.5. Concurrent persistence error handling

The unique constraint protects hard identity, but concurrent lookup/create
requires an explicit retry or conflict handling policy in the future
ListingPersistenceService.

### 27.6. Source-reported field freshness

The future persistence layer should define whether `url`, `status`,
`removed_at`, `location`, `extra`, and `listed_at` are overwritten when the
source omits them or sends `NULL`.

## 28. Explicit non-goals

This document does not:

- add or change ORM models;
- add Alembic migrations;
- modify database schema;
- implement Listing deduplication;
- assign `duplicate_of_id`;
- change RawListing ingestion behavior;
- add `last_seen_at`;
- change `status` into an enum;
- change source or external IDs;
- change Property matching or persistence;
- modify frontend behavior;
- modify transaction ownership rules.
