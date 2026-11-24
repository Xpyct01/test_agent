"""Shared fixtures: catalogue fakes, fixture weather, the ToolSet."""

import pytest

from trip_planner.app.agents.tools import core as tools_lib
from trip_planner.app.config import weather as weather_config_lib
from trip_planner.app.ml.environment import run_context as run_context_lib
from trip_planner.app.ml.equipment_check import core as equipment_check_lib
from trip_planner.app.ml.fitness_assessment import core as fitness_lib
from trip_planner.app.ml.trail_selection import core as trail_selection_lib
from trip_planner.app.ml.weather_forecast import fixture as fixture_lib
from trip_planner.unit_test import fakes


@pytest.fixture
def trail_repository() -> fakes.FakeTrailRepository:
    return fakes.FakeTrailRepository()


@pytest.fixture
def equipment_repository() -> fakes.FakeEquipmentItemRepository:
    return fakes.FakeEquipmentItemRepository()


@pytest.fixture
def weather_forecast() -> fixture_lib.FixtureWeatherForecast:
    return fixture_lib.FixtureWeatherForecast(
        weather_config_lib.WeatherConfiguration(variant='fixture')
    )


@pytest.fixture
def provider() -> run_context_lib.RunContextProvider:
    return run_context_lib.RunContextProvider()


@pytest.fixture
def tool_set(
    provider, trail_repository, equipment_repository, weather_forecast
) -> tools_lib.ToolSet:
    return tools_lib.ToolSet(
        run_context_provider=provider,
        fitness_assessment=fitness_lib.FitnessAssessment(),
        trail_selection=trail_selection_lib.TrailSelection(trail_repository),
        equipment_check=equipment_check_lib.EquipmentCheck(
            equipment_repository
        ),
        weather_forecast=weather_forecast,
        trail_repository=trail_repository,
        equipment_repository=equipment_repository,
        guide_repository=fakes.FakeGuideRepository(),
        simulation_config=fakes.simulation_config(max_tool_attempts=3),
    )
