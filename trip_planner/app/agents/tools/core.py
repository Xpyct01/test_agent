"""Container of every tool concern the agents of the module can use."""

from trip_planner.app.agents.tools import booking as booking_lib
from trip_planner.app.agents.tools import communication as communication_lib
from trip_planner.app.agents.tools import equipment as equipment_lib
from trip_planner.app.agents.tools import health as health_lib
from trip_planner.app.agents.tools import trails as trails_lib
from trip_planner.app.agents.tools import weather as weather_lib
from trip_planner.app.config import simulation as simulation_config_lib
from trip_planner.app.core.repositories.local_store import (
    equipment as equipment_repository_lib,
)
from trip_planner.app.core.repositories.local_store import (
    guide as guide_repository_lib,
)
from trip_planner.app.core.repositories.local_store import (
    trail as trail_repository_lib,
)
from trip_planner.app.ml.environment import run_context as run_context_lib
from trip_planner.app.ml.equipment_check import core as equipment_check_lib
from trip_planner.app.ml.fitness_assessment import core as fitness_lib
from trip_planner.app.ml.trail_selection import core as trail_selection_lib
from trip_planner.app.ml.weather_forecast import abstract as forecast_lib


class ToolSet:
    """Every tool concern of the module, built once and shared by the agents.

    Attributes:
        booking: Guide availability and bookings.
        communication: Messages to the connected participants.
        equipment: Gear requirements, rental stock and reservations.
        health: Fitness limits of the customer.
        trails: Trail search and status.
        weather: Weather forecast.
    """

    def __init__(
        self,
        run_context_provider: run_context_lib.RunContextProvider,
        fitness_assessment: fitness_lib.FitnessAssessment,
        trail_selection: trail_selection_lib.TrailSelection,
        equipment_check: equipment_check_lib.EquipmentCheck,
        weather_forecast: forecast_lib.AbstractWeatherForecast,
        trail_repository: trail_repository_lib.TrailRepository,
        equipment_repository: equipment_repository_lib.EquipmentRepository,
        guide_repository: guide_repository_lib.GuideRepository,
        simulation_config: simulation_config_lib.SimulationConfiguration,
    ):
        """Initializes the tool set and builds every concern.

        Args:
            run_context_provider: Gives access to the active run.
            fitness_assessment: Rule-based fitness limits.
            trail_selection: Ranks trails against a fitness profile.
            equipment_check: Rule-based gear requirements.
            weather_forecast: Daily forecast of the park.
            trail_repository: The trail catalogue.
            equipment_repository: The gear catalogue.
            guide_repository: The guide roster.
            simulation_config: Retry settings of the faulty actions.
        """
        base_kwargs = {
            'run_context_provider': run_context_provider,
            'max_attempts': simulation_config.max_tool_attempts,
            'retry_base_delay_s': simulation_config.retry_base_delay_s,
        }
        self.booking = booking_lib.BookingTools(
            guide_repository, trail_repository, **base_kwargs
        )
        self.communication = communication_lib.CommunicationTools(
            **base_kwargs
        )
        self.equipment = equipment_lib.EquipmentTools(
            equipment_check, equipment_repository, trail_repository,
            weather_forecast, **base_kwargs
        )
        self.health = health_lib.HealthTools(fitness_assessment, **base_kwargs)
        self.trails = trails_lib.TrailTools(
            trail_selection, trail_repository, **base_kwargs
        )
        self.weather = weather_lib.WeatherTools(weather_forecast, **base_kwargs)
