# Data Pipeline Architecture v0.1

## 1. Purpose

Data Ingestion Pipeline отвечает за получение данных об объектах недвижимости
из внешних источников, сохранение исходных данных, нормализацию и подготовку
данных для последующей оценки стоимости.

---

## 2. Data Flow

```text
External Source
        |
        ↓
SourceAdapter
        |
        ↓
Collector
        |
        ↓
IngestionService
        |
        ↓
RawListingRepository
        |
        ↓
`raw_listings` table
        |
        ↓
Normalizer
        |
        ↓
Building / Property / Listing
        |
        ↓
Comparable Engine
```

---

## 3. Architectural Principles

### Raw data is immutable

Таблица `raw_listings` хранит неизменяемый raw payload для текущей source
identity.

После сохранения:

- `raw_data` не изменяется;
- сохраняется внешний идентификатор источника;
- сохраняется время получения данных.

В текущем MVP `(source_id, external_id)` уникален. Поэтому `raw_listings`
содержит одну строку на source listing identity, а не append-only журнал каждой
повторной выгрузки. Повторные изменения цены представлены через current-state
`Listing` и append-only `ListingPriceHistory`.

Если в будущем потребуются исторические raw snapshots, нужен отдельный
observation/version model. Текущая схема в рамках processing pipeline не
меняется.

---

### Normalized data

Нормализованные сущности:

**Building:**

- физическое здание;
- адрес;
- координаты;
- характеристики дома.

**Property:**

- конкретный объект недвижимости;
- площадь;
- комнаты;
- этаж.

**Listing:**

- объявление конкретного источника;
- цена;
- статус;
- ссылка на источник.

---

## 4. Source Adapter Layer

Source Adapter скрывает различия между источниками данных.

Каждый источник должен иметь единый интерфейс:

- `collect()`;
- `parse()`;

Adapter отвечает за получение и первичный разбор данных.
Normalizer отвечает за приведение к доменной модели.

Примеры реализаций:

- `MockAdapter`;
- `CIANAdapter` (future);
- `AvitoAdapter` (future);
- `YandexAdapter` (future).

---

## 5. Collector Layer

Collector отвечает за оркестрацию получения сырых объявлений через
`SourceAdapter`.

Collector:

- принимает `SourceAdapter` как dependency;
- вызывает `SourceAdapter.collect()`;
- передаёт raw listing payloads дальше без изменения.

Collector не отвечает за:

- доступ к базе данных;
- создание ORM-объектов;
- нормализацию;
- дедупликацию.

Текущая реализация:

- `Collector`;
- `MockCollector`.

---

## 6. Repository Layer

Repository Layer определяет persistence contract для сырых объявлений.

`RawListingRepository` отвечает только за сохранение raw listing payload.
`SQLAlchemyRawListingRepository` реализует этот контракт через SQLAlchemy:

- создаёт `RawListing`;
- добавляет объект в переданную session;
- выполняет `flush()`.

Repository Layer не отвечает за:

- создание `Source`;
- нормализацию;
- дедупликацию;
- orchestration сбора данных.

---

## 7. Ingestion Service

`IngestionService` связывает Collector и RawListingRepository.

Service:

- вызывает `collector.collect()`;
- обрабатывает каждый raw listing dictionary;
- формирует persistence payload:

```python
{
    "source_id": UUID,
    "external_id": str,
    "raw_data": dict,
}
```

- передаёт payload в `repository.save()`.

Service не создаёт ORM-объекты, не работает с SQLAlchemy session,
не нормализует и не дедуплицирует объявления.

Для normalized persistence ingestion layer отдельно предоставляет
`ListingPersistenceOrchestrator`. Он не меняет raw-ingestion контракт:

1. находит существующий Listing и захватывает его текущую цену;
2. сохраняет current Listing state;
3. записывает новую цену в history только при изменении существующего Listing;
4. оставляет transaction lifecycle внешнему caller.

Worker-facing `persist_refreshed_listing()` использует эту boundary и связывает
оба persistence-сервиса с одной caller-owned Session. Сама scheduled
`refresh_recent_locations()` пока остаётся stub до реализации выборки locations.

---

## 8. Application Listing Processing Pipeline

`ListingProcessingPipeline` связывает уже существующие application boundaries
для одного raw source observation:

```text
RawListing
        ↓
NormalizationService
        ↓
BuildingResolutionService
        ↓
BuildingPersistenceService
        ↓
PropertyResolutionService
        ↓
PropertyPersistenceService
        ↓
ListingPersistenceOrchestrator
        ├── Listing current state
        └── ListingPriceHistory
```

Authoritative source identity передаётся pipeline отдельно как `source_key`.
Authoritative `external_id` передаётся отдельно от `raw_data`; значение
`external_id` внутри raw payload не определяет identity. Для persisted
`RawListing` caller передаёт его `external_id` и неизменяемую копию `raw_data`.
Повторный fixture с той же source identity может содержать новый raw payload,
не переписывая сохранённую строку `raw_listings`.

Building и Property resolution используют существующие matchers. Unique exact
match переиспользуется, отсутствие безопасного match приводит к созданию, а
ambiguity завершается ошибкой до downstream persistence.

`ListingPersistenceOrchestrator` остаётся единственным владельцем Listing
identity lookup, current-price update и решения о создании price-history row.
Сам pipeline не реализует price comparison и не создаёт
`ListingPriceHistory` напрямую.

SQLAlchemy Session и enclosing transaction принадлежат caller. Pipeline и все
вызванные сервисы могут выполнять `flush()`, но не вызывают `commit()`,
`rollback()` или `close()`.

Cross-source duplicate detection и scheduled refresh не входят в этот pipeline.

---

## 9. Normalization Strategy

```text
RawListing
        ↓
Normalizer
        ↓
Building
        ↓
Property
        ↓
Listing
```

Правила:

**RawListing:**

- хранит оригинальный payload;
- является источником истины;
- не изменяется после создания.

**Building:**

- идентификация по адресу и координатам;
- дубликаты не создаются при повторной загрузке.

MVP identity matching основан на:

- normalized address;
- географической близости координат.

Полная стратегия дедупликации развивается отдельно.

**Property:**

- связан с `Building`;
- описывает физический объект недвижимости.

**Listing:**

- каждое объявление источника хранится отдельно;
- история изменений сохраняется.

---

## 10. Data Ownership

| Layer | Owner | Storage |
|------|------|---------|
| Raw data | Collector | `raw_listings` |
| Building identity | Normalizer | `buildings` |
| Property identity | Normalizer | `properties` |
| Market offer | Source Adapter + Normalizer | `listings` |

---

## 11. Current Implementation Status

### Completed

- PostgreSQL/PostGIS database;
- SQLAlchemy models;
- Alembic migrations;
- Initial database schema migration applied;
- 9 core domain tables created.
- Task #4 completed — ingestion pipeline foundation implemented;
- `SourceAdapter`;
- `MockAdapter`;
- `Collector`;
- `MockCollector`;
- `RawListingRepository`;
- `SQLAlchemyRawListingRepository`;
- `IngestionService`;
- `ListingPersistenceOrchestrator`;
- `ListingProcessingPipeline`;
- worker-facing normalized Listing persistence boundary;
- ingestion pipeline tests.

### Planned

- Normalizer;
- Real source integrations.

---

## 12. Out of Scope

Task #4 не включает:

- реальные scraper реализации;
- подключение ЦИАН/Авито;
- оценку стоимости;
- Comparable Engine;
- пользовательский API;
- UI.