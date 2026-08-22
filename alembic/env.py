"""Alembic migration environment for ОценитьКвартиру.рф.

Key design decisions
────────────────────
* DATABASE_URL is read exclusively from the OS environment; it is never stored
  in alembic.ini so credentials stay out of version control.

* NullPool is used for online migrations so each invocation acquires exactly
  one connection and releases it immediately after the transaction, without
  leaving pooled connections open.

* GeoAlchemy2 hooks (render_item, include_object) are registered so that
  Geography columns render correctly in generated revision files and PostGIS
  system tables are excluded from autogenerate comparison.

* compare_type=True instructs autogenerate to detect column type changes.
  Geography type comparison depends on the GeoAlchemy2 hooks; always review
  type-change operations in generated revisions before applying them.

* Naming convention: the convention cannot be applied retroactively to
  Base.metadata after model classes are already registered without modifying
  backend/app/models/base.py (out of scope for this setup task).  All
  existing constraints are already explicitly named following the project
  convention (uq_*, ix_*, fk_*).  See alembic/README for details and the
  recommended future action.

* FIRST REVISION NOTE: the very first revision must call
      op.execute("CREATE EXTENSION IF NOT EXISTS postgis")
  *before* any CREATE TABLE statement for a geography column.
  PostgreSQL 16 has gen_random_uuid() as a core function — do NOT add pgcrypto.
"""

from __future__ import annotations

import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine
from sqlalchemy.pool import NullPool

# ── Path setup ──────────────────────────────────────────────────────────────
# alembic/ lives at the workspace root; backend/ is a sibling directory.
# We insert it so that `from app.models import ...` resolves correctly when
# Alembic is invoked from the workspace root.
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, ".."))
_BACKEND = os.path.join(_ROOT, "backend")
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

# ── Model imports ────────────────────────────────────────────────────────────
# Importing all nine model modules registers their tables into Base.metadata.
# This import block must stay in sync with backend/app/models/__init__.py.
from app.models import (  # noqa: E402
    Base,
    Building,
    Listing,
    ListingPriceHistory,
    Property,
    RawListing,
    SearchRequest,
    Source,
    ValuationComparable,
    ValuationResult,
)

# Sanity-check: exactly 9 tables must be registered.
_EXPECTED_TABLE_COUNT = 9
_actual_table_count = len(Base.metadata.tables)
if _actual_table_count != _EXPECTED_TABLE_COUNT:
    raise RuntimeError(
        f"Expected {_EXPECTED_TABLE_COUNT} tables in Base.metadata, "
        f"got {_actual_table_count}: {sorted(Base.metadata.tables)}"
    )

target_metadata = Base.metadata

# ── GeoAlchemy2 / PostGIS hooks ─────────────────────────────────────────────
# render_item  — renders Geography/Geometry column types in revision files.
# include_object — excludes PostGIS internal system tables (geometry_columns,
#                  spatial_ref_sys, …) from autogenerate comparison.
try:
    from geoalchemy2 import alembic_helpers as _geo_helpers

    _geo_render_item = _geo_helpers.render_item
    _geo_include_object = _geo_helpers.include_object
except ImportError:  # pragma: no cover — geoalchemy2 is a hard requirement
    _geo_render_item = None
    _geo_include_object = None

# ── Alembic config object ────────────────────────────────────────────────────
config = context.config

# Wire up Python logging from alembic.ini [loggers] section.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Inject DATABASE_URL from environment into the Alembic config at runtime.
# The URL is intentionally NOT logged here to avoid credentials in log output.
_database_url = os.environ.get("DATABASE_URL")
if _database_url:
    config.set_main_option("sqlalchemy.url", _database_url)
# If DATABASE_URL is absent:
#   • offline mode (--sql) still works — no connection is required.
#   • online mode will raise at engine creation time with a clear error.


# ── Migration functions ──────────────────────────────────────────────────────

def run_migrations_offline() -> None:
    """Render migration SQL to stdout without a live database connection.

    Useful for reviewing SQL before applying it, or for generating scripts
    to hand to a DBA.  Invoke with:  alembic upgrade head --sql
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        render_item=_geo_render_item,
        include_object=_geo_include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Apply migrations against a live database connection.

    NullPool ensures the connection is released immediately after the
    migration transaction; no connection remains open in the pool.
    """
    connectable = create_engine(
        config.get_main_option("sqlalchemy.url"),
        poolclass=NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            render_item=_geo_render_item,
            include_object=_geo_include_object,
        )
        with context.begin_transaction():
            context.run_migrations()


# ── Entry point ──────────────────────────────────────────────────────────────
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
