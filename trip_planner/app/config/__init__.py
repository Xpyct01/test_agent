"""Configuration of the trip planner service."""

import pydantic

from trip_planner.app.config import agents as agents_lib
from trip_planner.app.config import observability as observability_lib
from trip_planner.app.config import openai as openai_lib
from trip_planner.app.config import simulation as simulation_lib
from trip_planner.app.config import weather as weather_lib


class Configuration(pydantic.BaseModel):
    """Every settings section of the service.

    Attributes:
        agents: LLM agents and simulated humans.
        observability: Langfuse tracing.
        openai: OpenAI client.
        simulation: Discrete-time simulation.
        weather: Weather forecast.
    """

    agents: agents_lib.AgentsConfiguration = pydantic.Field(
        default_factory=agents_lib.AgentsConfiguration
    )
    observability: observability_lib.ObservabilityConfiguration = (
        pydantic.Field(
            default_factory=observability_lib.ObservabilityConfiguration
        )
    )
    openai: openai_lib.OpenAIConfiguration = pydantic.Field(
        default_factory=openai_lib.OpenAIConfiguration
    )
    simulation: simulation_lib.SimulationConfiguration = pydantic.Field(
        default_factory=simulation_lib.SimulationConfiguration
    )
    weather: weather_lib.WeatherConfiguration = pydantic.Field(
        default_factory=weather_lib.WeatherConfiguration
    )
