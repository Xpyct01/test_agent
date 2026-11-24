"""Settings of the trip planner PostgreSQL database."""

import pydantic
import pydantic_settings
from sqlalchemy import engine

from trip_planner.app.config import base


class DatabaseConfiguration(base.ConfigurationSection):
    """Database settings, read from the `TRIP_DATABASE_` variables.

    The database is the service's own PostgreSQL (`trip-planner-postgres` in
    `docker-compose.yml`), never the one Langfuse uses.

    Attributes:
        host: Database host.
        port: Database port.
        user: Database user.
        password: Password of `user`.
        name: Database name.
        echo: Whether SQLAlchemy logs every statement.
        pool_size: Connections the engine keeps open.
    """

    model_config = pydantic_settings.SettingsConfigDict(
        env_prefix='TRIP_DATABASE_'
    )

    host: str = 'localhost'
    # Host port of the compose service; 5432 is left to the Langfuse database.
    port: int = 5433
    user: str = 'trip_planner'
    # Matches the compose default; set a real one outside local development.
    password: pydantic.SecretStr = pydantic.SecretStr('trip_planner')
    name: str = 'trip_planner'
    echo: bool = False
    pool_size: int = 5

    @property
    def url(self) -> engine.URL:
        """Returns the asyncpg connection URL of the database."""
        return engine.URL.create(
            drivername='postgresql+asyncpg',
            username=self.user,
            password=self.password.get_secret_value(),
            host=self.host,
            port=self.port,
            database=self.name,
        )
