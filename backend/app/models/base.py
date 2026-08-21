"""
Declarative base for all SQLAlchemy ORM models.

All model classes inherit from Base. Importing this module does not open
a database connection and does not execute any DDL.
"""
from __future__ import annotations

import uuid
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Project-wide SQLAlchemy declarative base."""


class UUIDPkMixin:
    """
    Provides a UUID primary key with both Python-side and server-side defaults.

    Python-side default (uuid4): the id attribute is populated immediately on
    object construction, before flush, so it can be referenced without a DB
    round-trip.

    server_default gen_random_uuid(): the DB column carries a native DEFAULT so
    raw-SQL inserts and Alembic data migrations receive auto-generated UUIDs
    without explicitly specifying id.  gen_random_uuid() is a PostgreSQL 16
    built-in — no pgcrypto extension required.
    """

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        server_default=text("gen_random_uuid()"),
    )
