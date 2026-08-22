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
Source Adapter
        |
        ↓
Collector
        |
        ↓
Raw Listing Storage
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

Таблица `raw_listings` является неизменяемым журналом входящих данных.

После сохранения:

- `raw_data` не изменяется;
- сохраняется внешний идентификатор источника;
- сохраняется время получения данных.

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

## 5. Normalization Strategy

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

## 6. Data Ownership

| Layer | Owner | Storage |
|------|------|---------|
| Raw data | Collector | `raw_listings` |
| Building identity | Normalizer | `buildings` |
| Property identity | Normalizer | `properties` |
| Market offer | Source Adapter + Normalizer | `listings` |

---

## 7. Current Implementation Status

### Completed

- PostgreSQL/PostGIS database;
- SQLAlchemy models;
- Alembic migrations;
- Initial database schema migration applied;
- 9 core domain tables created.

### Planned

- Source Adapter Interface;
- `MockAdapter`;
- Collector;
- Normalizer;
- External sources integration.

---

## 8. Out of Scope

Task #4 не включает:

- реальные scraper реализации;
- подключение ЦИАН/Авито;
- оценку стоимости;
- Comparable Engine;
- пользовательский API;
- UI.