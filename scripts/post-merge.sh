#!/usr/bin/env bash

set -Eeuo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

compose=(docker compose)

echo "Starting database and Redis..."
"${compose[@]}" up -d db redis

echo "Waiting for PostgreSQL..."
for attempt in $(seq 1 30); do
    if pg_isready -h 127.0.0.1 -p 5432 >/dev/null 2>&1; then
        break
    fi

    if [[ "$attempt" -eq 30 ]]; then
        echo "PostgreSQL did not become ready within 30 seconds." >&2
        exit 1
    fi

    sleep 1
done

echo "Building backend and worker images..."
"${compose[@]}" build backend worker

echo "Applying database migrations..."
if [[ ! -x .venv/bin/python ]]; then
    echo "Managed workspace Python is unavailable at .venv/bin/python." >&2
    exit 1
fi

DATABASE_URL="$(
    "${compose[@]}" config --format json |
        .venv/bin/python -c '
import json
import sys

config = json.load(sys.stdin)
print(config["services"]["backend"]["environment"]["DATABASE_URL"])
'
)"
export DATABASE_URL="${DATABASE_URL/@db:/@127.0.0.1:}"
.venv/bin/python -m alembic upgrade head

echo "Starting rebuilt backend and worker..."
"${compose[@]}" up -d backend worker

echo "Post-merge setup completed."