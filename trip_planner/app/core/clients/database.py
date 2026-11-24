"""Connection pool and transactions of the trip planner database."""

from collections.abc import AsyncIterator
import contextlib

from sqlalchemy.ext import asyncio as sa_asyncio

from trip_planner.app.config import database as database_lib


class DatabaseClient:
    """Connection pool of the service's own PostgreSQL database.

    The engine connects lazily, so building the client never needs the
    database to be up; the first statement does.
    """

    def __init__(self, database_config: database_lib.DatabaseConfiguration):
        """Initializes the client.

        Args:
            database_config: Connection and pool settings.
        """
        self._engine = sa_asyncio.create_async_engine(
            database_config.url,
            echo=database_config.echo,
            pool_size=database_config.pool_size,
            # Drops connections the server closed while they sat in the pool.
            pool_pre_ping=True,
        )
        self._session_factory = sa_asyncio.async_sessionmaker(
            self._engine, expire_on_commit=False
        )

    @contextlib.asynccontextmanager
    async def transaction(self) -> AsyncIterator[sa_asyncio.AsyncSession]:
        """Opens a session inside one transaction.

        Yields:
            The session. Its work is committed when the block exits and
            rolled back when the block raises.
        """
        async with self._session_factory() as session, session.begin():
            yield session

    async def close(self) -> None:
        """Closes every pooled connection."""
        await self._engine.dispose()
