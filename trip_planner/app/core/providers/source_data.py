"""Provides the source data CSV files stored in the MinIO bucket."""

import asyncio
import csv
import io
from typing import TypeVar

import pydantic

from trip_planner.app.core import errors
from trip_planner.app.core.clients import storage as storage_lib
from trip_planner.app.core.schemas import source_data

_Record = TypeVar('_Record', bound=pydantic.BaseModel)
_CSV_SUFFIX = '.csv'


class SourceDataProvider:
    """Reads and validates the trails and gear CSV files of the bucket."""

    def __init__(self, storage_client: storage_lib.StorageClient):
        """Initializes the provider.

        Args:
            storage_client: The bucket holding the files.
        """
        self._storage = storage_client

    async def read_trails(
        self, object_name: str
    ) -> list[source_data.TrailRecord]:
        """Returns the rows of a trails file (`picos_trails/trails.csv`).

        Args:
            object_name: Key of the CSV file in the bucket.

        Raises:
            errors.InvalidRequestError: The file is missing, is not a CSV
                file, or a row does not match the trails columns.
        """
        return await self._read(object_name, source_data.TrailRecord)

    async def read_gear_items(
        self, object_name: str
    ) -> list[source_data.GearItemRecord]:
        """Returns the rows of a gear file (`hiking_gear/gear_items.csv`).

        Args:
            object_name: Key of the CSV file in the bucket.

        Raises:
            errors.InvalidRequestError: The file is missing, is not a CSV
                file, or a row does not match the gear columns.
        """
        return await self._read(object_name, source_data.GearItemRecord)

    async def _read(
        self, object_name: str, record_type: type[_Record]
    ) -> list[_Record]:
        if not object_name.lower().endswith(_CSV_SUFFIX):
            raise errors.InvalidRequestError(
                f'Not a CSV file: {object_name!r}'
            )
        try:
            content = await self._storage.read_bytes(object_name)
        except storage_lib.ObjectNotFoundError as e:
            raise errors.InvalidRequestError(str(e)) from e
        return await asyncio.to_thread(
            _parse_csv, object_name, content, record_type
        )


def _parse_csv(
    object_name: str, content: bytes, record_type: type[_Record]
) -> list[_Record]:
    """Validates every row of a CSV file with a header line.

    Raises:
        errors.InvalidRequestError: The file is not UTF-8, lacks a column
            of `record_type`, or a row has an invalid value.
    """
    try:
        text = content.decode('utf-8-sig')
    except UnicodeDecodeError as e:
        raise errors.InvalidRequestError(
            f'{object_name!r} is not UTF-8 text'
        ) from e
    reader = csv.DictReader(io.StringIO(text, newline=''))
    missing = set(record_type.model_fields) - set(reader.fieldnames or ())
    if missing:
        raise errors.InvalidRequestError(
            f'{object_name!r} lacks the columns {sorted(missing)!r}'
        )
    records = []
    # Line 1 is the header.
    for line, row in enumerate(reader, start=2):
        try:
            records.append(record_type.model_validate(row))
        except pydantic.ValidationError as e:
            raise errors.InvalidRequestError(
                f'{object_name!r}, line {line}: {_first_error(e)}'
            ) from e
    return records


def _first_error(error: pydantic.ValidationError) -> str:
    detail = error.errors()[0]
    location = '.'.join(str(part) for part in detail['loc'])
    return f'{location}: {detail["msg"]}'
