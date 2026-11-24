"""Live daily forecast from the Open-Meteo API (no API key needed)."""

import datetime
import logging

import httpx

from trip_planner.app.config import weather as weather_lib
from trip_planner.app.core import errors
from trip_planner.app.core.schemas import trip
from trip_planner.app.ml.weather_forecast import base

logger = logging.getLogger(__name__)

_DAILY_VARIABLES = (
    'weather_code,temperature_2m_max,temperature_2m_min,'
    'precipitation_probability_max,precipitation_sum,wind_speed_10m_max'
)
# WMO weather interpretation codes, grouped.
_WMO_CODES = {
    0: 'clear sky', 1: 'mainly clear', 2: 'partly cloudy', 3: 'overcast',
    45: 'fog', 48: 'fog', 51: 'drizzle', 53: 'drizzle', 55: 'drizzle',
    56: 'freezing drizzle', 57: 'freezing drizzle', 61: 'rain', 63: 'rain',
    65: 'heavy rain', 66: 'freezing rain', 67: 'freezing rain', 71: 'snow',
    73: 'snow', 75: 'heavy snow', 77: 'snow grains', 80: 'rain showers',
    81: 'rain showers', 82: 'violent rain showers', 85: 'snow showers',
    86: 'snow showers', 95: 'thunderstorm', 96: 'thunderstorm with hail',
    99: 'thunderstorm with hail',
}


class OpenMeteoWeatherForecast(base.BaseWeatherForecast):
    """Forecast for the configured point of the park."""

    def __init__(
        self,
        weather_config: weather_lib.WeatherConfiguration,
        http_client: httpx.AsyncClient,
    ):
        """Initializes the forecast.

        Args:
            weather_config: Weather settings.
            http_client: Client the requests are sent with; closed by
                `close()`.
        """
        super().__init__(weather_config)
        self._http_client = http_client
        self._url = weather_config.forecast_url
        self._latitude = weather_config.latitude
        self._longitude = weather_config.longitude
        self._timeout_s = weather_config.timeout_s

    async def close(self) -> None:
        await self._http_client.aclose()

    async def _fetch(
        self, start_date: datetime.date
    ) -> list[trip.DailyForecast]:
        end_date = start_date + datetime.timedelta(days=self._forecast_days - 1)
        params = {
            'latitude': self._latitude,
            'longitude': self._longitude,
            'daily': _DAILY_VARIABLES,
            'timezone': 'Europe/Madrid',
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat(),
        }
        try:
            response = await self._http_client.get(
                self._url, params=params, timeout=self._timeout_s
            )
            response.raise_for_status()
            daily = response.json()['daily']
        except (httpx.HTTPError, KeyError, ValueError) as error:
            logger.warning('Open-Meteo request failed: %s', error)
            raise errors.TransientActionError(
                f'Weather service unavailable: {error}'
            ) from error
        return [
            trip.DailyForecast(
                date=datetime.date.fromisoformat(daily['time'][i]),
                weather=_WMO_CODES.get(daily['weather_code'][i], 'unknown'),
                temperature_max_c=daily['temperature_2m_max'][i],
                temperature_min_c=daily['temperature_2m_min'][i],
                precipitation_probability=(
                    daily['precipitation_probability_max'][i] or 0
                ),
                precipitation_mm=daily['precipitation_sum'][i] or 0.0,
                wind_speed_max_kmh=daily['wind_speed_10m_max'][i],
            )
            for i in range(len(daily['time']))
        ]
