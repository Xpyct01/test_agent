"""Shared upsert logic of the repositories backed by PostgreSQL."""

from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import sqlmodel

from trip_planner.app.core.clients import database as database_lib

# Kept from the first insert when a row is written again.
_PRESERVED_COLUMNS = frozenset({'id', 'created_at'})


class BasePostgresRepository:
    """Runs statements against the trip planner database."""

    def __init__(self, database_client: database_lib.DatabaseClient):
        """Initializes the repository.

        Args:
            database_client: Pool the statements run on.
        """
        self._database = database_client

    async def _upsert(
        self,
        rows: Sequence[sqlmodel.SQLModel],
        conflict_columns: Sequence[str],
        returning: Sequence[str],
        preserved_columns: Sequence[str] = (),
    ) -> list[sa.Row[Any]]:
        """Inserts rows of one table, updating those whose key exists.

        All rows are written in one statement and one transaction, so no two
        rows may share a key.

        Args:
            rows: Rows of one table model; a None primary key is left to
                the database.
            conflict_columns: Unique key that identifies an existing row.
            returning: Columns returned for every written row.
            preserved_columns: Columns an existing row keeps (besides `id`
                and `created_at`), e.g. ones curated by hand.

        Returns:
            The `returning` columns of each written row.
        """
        if not rows:
            return []
        table = type(rows[0]).__table__
        values = [_column_values(table, row) for row in rows]
        statement = postgresql.insert(table).values(values)
        kept = _PRESERVED_COLUMNS.union(conflict_columns, preserved_columns)
        updated = {
            name: statement.excluded[name]
            for name in values[0]
            if name not in kept
        }
        if not updated:
            # A no-op update, so RETURNING still reports existing rows
            # (`DO NOTHING` would skip them).
            key = conflict_columns[0]
            updated = {key: statement.excluded[key]}
        statement = statement.on_conflict_do_update(
            index_elements=list(conflict_columns), set_=updated
        ).returning(*(table.c[name] for name in returning))
        async with self._database.transaction() as session:
            result = await session.execute(statement)
            return list(result.all())


def _column_values(table: sa.Table, row: sqlmodel.SQLModel) -> dict[str, Any]:
    """Returns the row's column values, without a primary key left unset."""
    return {
        column.name: getattr(row, column.name)
        for column in table.columns
        if not (column.primary_key and getattr(row, column.name) is None)
    }
