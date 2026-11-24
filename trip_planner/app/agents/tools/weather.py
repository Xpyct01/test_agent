"""Tools over the weather forecast."""

from trip_planner.app.agents.tools import base
from trip_planner.app.core.schemas import tools
from trip_planner.app.ml.weather_forecast import abstract as weather_lib

_MAX_BEST_DATES = 3


class WeatherTools(base.BaseTools):
    """Weather tools the agents can call."""

    def __init__(
        self,
        weather_forecast: weather_lib.AbstractWeatherForecast,
        **base_kwargs,
    ):
        """Initializes the tools.

        Args:
            weather_forecast: Daily forecast of the park.
            **base_kwargs: Arguments of `base.BaseTools`.
        """
        super().__init__(**base_kwargs)
        self._weather_forecast = weather_forecast

    async def get_weather_forecast(self) -> dict[str, object]:
        """Gets the 7-day weather forecast for Picos de Europa.

        Returns:
            Each day's weather with a hiking score (higher is better), and
            best_dates: the 3 best dates for hiking, best first. May fail
            transiently; then retry.
        """
        context = self._run_context_provider.current()

        async def fetch() -> tools.ForecastResult:
            days = await self._weather_forecast.forecast(context.planning_date)
            ranked = sorted(days, key=lambda d: (-d.hiking_score, d.date))
            return tools.ForecastResult(
                days=days,
                best_dates=[d.date for d in ranked[:_MAX_BEST_DATES]],
            )

        return base.to_result(
            await self._call_with_faults('get_weather_forecast', fetch)
        )
