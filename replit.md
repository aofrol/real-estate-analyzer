# ОценитьКвартиру.рф — Real Estate Price Analyzer

## Project Overview

MVP сервис автоматизированной оценки рыночной стоимости квартир по адресу и параметрам.

**Stack:**
- Frontend: Next.js 14 + TypeScript + Tailwind CSS
- Backend API: Python 3.12 + FastAPI
- Worker: Celery (same image as backend)
- Database: PostgreSQL 16 + PostGIS
- Cache / Broker: Redis 7
- Deployment: Docker Compose (dev & production Linux VPS)

## How to Run

### On Replit (development)
Use the **"Start application"** workflow (one click). It runs:
```bash
docker compose up -d db redis backend worker --build
cd frontend && ([ -d node_modules ] || npm install) && npm run dev
```
Backend services (db, redis, api, worker) run in Docker. Next.js runs natively so Replit Preview can detect port 5000 directly.

**Service URLs:**
| Service | URL |
|---------|-----|
| Frontend (Next.js) | http://localhost:5000 (Replit Preview) |
| Backend API (FastAPI) | http://localhost:8000 |
| API docs (Swagger) | http://localhost:8000/docs |

### On a production Linux VPS
```bash
cp .env.example .env   # fill in real values
docker compose up --build -d   # starts ALL services including frontend container
```

## Architecture

Modular monolith. All services run in Docker Compose. No microservices.

**Main request flow (synchronous):**
```
POST /api/v1/valuate
  → Geocoding → Pipeline (collect→normalize→dedup) → ComparableEngine → ValuationEngine
  → ValuationResponse (all prices in RUB)
```

**Celery** is used only for periodic background refresh of listing data (every 4 h by default).

## Key Conventions

### Money
- **Database:** all monetary values stored as `BIGINT` in **kopecks** (1 RUB = 100 kopecks)
- **API layer:** Pydantic schemas convert to **RUB (float)** on the way out (`kopecks / 100`)
- **No other layer** performs money conversion

### Valuation model
- Primary value: `weighted_median_price_per_sqm × target_area`
- Primary range: `P25_price_per_sqm × area` – `P75_price_per_sqm × area` (not min–max)
- Outlier filter: IQR on `price_per_sqm` (not absolute price), multiplier = 1.5

### UI language
- All user-visible text in **Russian**
- Rooms: Студия / 1 / 2 / 3 / 4 / 5+
- Confidence shown as "Надёжность оценки" (not a formal statistical CI)

## Environment Variables

See `.env.example` for the full list with descriptions.

Key vars:
- `GEOCODING_PROVIDER`: `mock` (dev, no key) | `nominatim` (free) | `yandex` (needs key)
- `IQR_MULTIPLIER`: outlier filter multiplier (default 1.5)
- `PIPELINE_REFRESH_INTERVAL_HOURS`: background refresh frequency (default 4)

## Task Sequence

| Task | Title | Depends on |
|------|-------|-----------|
| #2 | Project foundation & Docker setup | — |
| #3 | Database schema & migrations | #2 |
| #4 | Backend core: geocoding & adapter interface | #3 |
| #5 | Data pipeline: collector, normalizer & deduplication | #4 |
| #6 | Comparable Engine & Valuation Engine | #5 |
| #7 | Valuation REST API | #6 |
| #8 | Frontend: Next.js valuation UI | #7 |

## User Preferences
- Модульный монолит, без микросервисов
- Docker Compose для разработки и production VPS
- Никаких LLM, ChatGPT, авторизации, платежей, CRM, сложных карт в MVP
