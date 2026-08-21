"""
Declarative base for all SQLAlchemy ORM models.

All model classes inherit from Base. Importing this module does not open
a database connection and does not execute any DDL.
"""
from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Project-wide SQLAlchemy declarative base."""
