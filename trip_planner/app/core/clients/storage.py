"""Reads objects from the MinIO bucket of the source data files."""

import asyncio

import minio
from minio import error as minio_error

from trip_planner.app.config import storage as storage_lib

_MISSING_CODES = frozenset({'NoSuchKey', 'NoSuchBucket'})


class ObjectNotFoundError(LookupError):
    """The bucket or the object does not exist."""


class StorageClient:
    """Access to one bucket of the MinIO object storage.

    Attributes:
        bucket: Name of the bucket the client reads.
    """

    def __init__(self, storage_config: storage_lib.StorageConfiguration):
        """Initializes the client; no request is made until the first read.

        Args:
            storage_config: Address, credentials and bucket.
        """
        self.bucket = storage_config.bucket
        self._client = minio.Minio(
            storage_config.endpoint,
            access_key=storage_config.access_key,
            secret_key=storage_config.secret_key.get_secret_value(),
            secure=storage_config.secure,
        )

    async def read_bytes(self, object_name: str) -> bytes:
        """Returns the content of one object of the bucket.

        Args:
            object_name: Key of the object, e.g. `trails.csv`.

        Raises:
            ObjectNotFoundError: The bucket or the object does not exist.
            minio_error.S3Error: Any other storage failure.
        """
        return await asyncio.to_thread(self._read_bytes, object_name)

    def _read_bytes(self, object_name: str) -> bytes:
        try:
            response = self._client.get_object(
                bucket_name=self.bucket, object_name=object_name
            )
        except minio_error.S3Error as e:
            if e.code in _MISSING_CODES:
                raise ObjectNotFoundError(
                    f'No object {object_name!r} in bucket {self.bucket!r}'
                ) from e
            raise
        try:
            return response.read()
        finally:
            response.close()
            response.release_conn()
