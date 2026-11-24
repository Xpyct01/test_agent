"""Settings of the MinIO object storage that holds the source data files."""

import pydantic
import pydantic_settings

from trip_planner.app.config import base


class StorageConfiguration(base.ConfigurationSection):
    """Object storage settings, read from the `TRIP_STORAGE_` variables.

    The storage is the MinIO of `docker-compose.yml`. The source data files
    (`trails.csv`, `gear_items.csv`, with the columns of the DVC datasets)
    are uploaded to `bucket` and indexed by name.

    Attributes:
        endpoint: MinIO S3 API address, `host:port`, without a scheme.
        access_key: MinIO user.
        secret_key: Password of `access_key`.
        secure: Whether to connect over HTTPS.
        bucket: Bucket holding the source data CSV files.
    """

    model_config = pydantic_settings.SettingsConfigDict(
        env_prefix='TRIP_STORAGE_'
    )

    # Host port of the compose MinIO (`MINIO_PORT`).
    endpoint: str = 'localhost:9090'
    # Match the compose defaults; set real ones outside local development.
    access_key: str = 'minio'
    secret_key: pydantic.SecretStr = pydantic.SecretStr('miniosecret')
    secure: bool = False
    bucket: str = 'trip-planner-data'
