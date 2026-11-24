"""Alembic environment of the trip planner database.

Run from the repository root (the config lives in `pyproject.toml`):

    uv run alembic upgrade head
    uv run alembic revision --autogenerate -m "<change>"

The connection URL is read from the `TRIP_DATABASE_` settings.
"""

import asyncio
import logging

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import base as engine_base
from sqlalchemy.ext import asyncio as sa_asyncio

from trip_planner.app.config import database as database_lib
# Imported for their side effect: each module registers its tables.
from trip_planner.app.core.sql_models import base
from trip_planner.app.core.sql_models import booking  # pylint: disable=unused-import
from trip_planner.app.core.sql_models import customer  # pylint: disable=unused-import
from trip_planner.app.core.sql_models import equipment  # pylint: disable=unused-import
from trip_planner.app.core.sql_models import guide  # pylint: disable=unused-import
from trip_planner.app.core.sql_models import simulation  # pylint: disable=unused-import
from trip_planner.app.core.sql_models import trail  # pylint: disable=unused-import

logging.basicConfig(
    level=logging.INFO, format='%(levelname)s %(name)s %(message)s'
)

_TARGET_METADATA = base.METADATA


def _configure_context(**kwargs) -> None:
    context.configure(
        target_metadata=_TARGET_METADATA,
        compare_type=True,
        compare_server_default=True,
        **kwargs,
    )


def _run_migrations_offline(url: str) -> None:
    """Prints the SQL instead of running it (`alembic upgrade head --sql`)."""
    _configure_context(
        url=url, literal_binds=True, dialect_opts={'paramstyle': 'named'}
    )
    with context.begin_transaction():
        context.run_migrations()


def _do_run_migrations(connection: engine_base.Connection) -> None:
    _configure_context(connection=connection)
    with context.begin_transaction():
        context.run_migrations()


async def _run_migrations_online(url: str) -> None:
    engine = sa_asyncio.create_async_engine(url, poolclass=pool.NullPool)
    async with engine.connect() as connection:
        await connection.run_sync(_do_run_migrations)
    await engine.dispose()


def main() -> None:
    """Runs the migrations against the configured database."""
    url = database_lib.DatabaseConfiguration().url.render_as_string(
        hide_password=False
    )
    if context.is_offline_mode():
        _run_migrations_offline(url)
    else:
        asyncio.run(_run_migrations_online(url))


main()
