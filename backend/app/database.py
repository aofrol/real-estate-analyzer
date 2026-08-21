"""
SQLAlchemy engine and session factory.

Reads DATABASE_URL from the environment at module load time.
No connection is established at import — create_engine() is lazy.
No DDL is executed here; schema management belongs to Alembic.
"""
from __future__ import annotations

import os
import warnings

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

DATABASE_URL: str | None = os.environ.get("DATABASE_URL")

if DATABASE_URL is None:
    warnings.warn(
        "DATABASE_URL environment variable is not set. "
        "All database operations will fail at runtime.",
        RuntimeWarning,
        stacklevel=1,
    )
    # Placeholder keeps create_engine() from raising at import time.
    DATABASE_URL = "postgresql://localhost/placeholder"

# pool_pre_ping issues a lightweight SELECT 1 before each checkout so that
# stale connections (e.g. after a DB restart) are transparently recycled.
# The actual connection pool is not opened until the first checkout.
engine: Engine = create_engine(DATABASE_URL, pool_pre_ping=True)

SessionLocal: sessionmaker[Session] = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


def get_session() -> Session:
    """Return a new ORM session. The caller is responsible for closing it."""
    return SessionLocal()
