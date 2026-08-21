# Technical Debt & Known Deviations

## 1. Replit Docker Healthcheck Workaround

**Проблема.** Docker healthchecks (`CMD` / `CMD-SHELL`) исполняются через `docker exec`, который внутри использует системный вызов `setns` для входа в namespace контейнера. Replit блокирует `setns` на уровне sandbox. Любой healthcheck гарантированно завершается ошибкой:
```
OCI runtime exec failed: unable to start container process:
error executing setns process: exit status 1: unknown
```
Исчерпание попыток → статус `unhealthy` → зависимые сервисы с `condition: service_healthy` не стартуют.

**Принятое решение (dev compose).**
- Блоки `healthcheck:` полностью удалены у `db` и `redis`.
- `condition: service_healthy` заменён на `condition: service_started` во всех `depends_on`.
- На `backend` и `worker` добавлено `restart: unless-stopped` как механизм самовосстановления при гонке состояний на старте.

**Последствие.** В dev-окружении не гарантируется, что PostgreSQL/Redis полностью готовы принимать подключения в момент старта `backend`/`worker`. На практике компенсируется `restart: unless-stopped`.

---

## 2. Различия Dev Compose и Будущего Production Compose

| Аспект | Dev (текущий) | Production (необходимо) |
|--------|---------------|------------------------|
| Healthchecks | Отсутствуют | `CMD pg_isready` / `CMD redis-cli ping` с `condition: service_healthy` |
| uvicorn command | `--reload` включён (hot reload) | Без `--reload`; указать `--workers N` |
| Bind mounts кода | `./backend:/app`, `./frontend:/app` | Убрать; код запекать в образ через `COPY . .` |
| Анонимные volumes | `/app/node_modules`, `/app/.next` | Убрать вместе с bind mounts |
| Секреты / defaults | `POSTGRES_PASSWORD=devpassword` в defaults | Без небезопасных defaults; Docker Secrets или внешний `.env` |
| `NEXT_PUBLIC_API_URL` default | `http://localhost:8000` | Публичный URL сервиса (`https://api.example.com`) |
| `GEOCODING_PROVIDER` default | `backend`: `nominatim`, `worker`: `mock` (разные!) | Одинаково явно задан в обоих сервисах |
| Restart policy у `db`/`redis` | Отсутствует | `restart: unless-stopped` |
| Сетевая изоляция | Единая дефолтная bridge-сеть | Отдельные `networks:` (frontend-tier / backend-tier) |
| Проброс портов DB/Redis | `5432:5432`, `6379:6379` открыты на хосте | Закрыть от хоста; доступ только внутри сети compose |

---

## 3. Production Risks (зафиксированы по состоянию на дату написания)

| # | Риск | Где | Критичность |
|---|------|-----|-------------|
| 1 | Слабый default-пароль БД (`devpassword`) виден в compose | `db`, `backend`, `worker` env | Высокая |
| 2 | `uvicorn --reload` в CMD Dockerfile — неприемлем в production (повышенный CPU, сканирование FS) | `backend` Dockerfile | Высокая |
| 3 | Bind mounts исходников (`./backend:/app`, `./frontend:/app`) — код не запечён в образ | `backend`, `worker`, `frontend` | Высокая |
| 4 | `NEXT_PUBLIC_API_URL` default `http://localhost:8000` — браузер пользователя не достигает localhost сервера | `frontend` | Высокая |
| 5 | Отсутствие readiness checks — `backend`/`worker` могут стартовать раньше готовности БД/Redis | `backend`, `worker` depends_on | Средняя |
| 6 | Нет `restart:` у `db` и `redis` — не перезапустятся автоматически после падения | `db`, `redis` | Средняя |
| 7 | Разные defaults `GEOCODING_PROVIDER` у `backend` (`nominatim`) и `worker` (`mock`) | `backend`, `worker` | Средняя |
| 8 | Единая bridge-сеть — `db` и `redis` видны фронтенду и любому другому сервису | все | Низкая |
| 9 | Порты `5432` и `6379` проброшены на хост — БД и Redis доступны извне контейнера | `db`, `redis` | Средняя |
