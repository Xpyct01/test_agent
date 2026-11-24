"""The one object the entry points talk to: builds and owns the runtime."""

import asyncio
import dataclasses
import logging

import httpx
from langchain_openai import ChatOpenAI
from langgraph.checkpoint import memory

from trip_planner.app import config
from trip_planner.app.agents.callbacks import observability as observability_lib
from trip_planner.app.agents.customer_assistant import core as customer_lib
from trip_planner.app.agents.operations_assistant import core as operations_lib
from trip_planner.app.agents.tools import core as tools_lib
from trip_planner.app.core.clients import database as database_lib
from trip_planner.app.core.clients import storage as storage_lib
from trip_planner.app.core.providers import source_data as source_data_lib
from trip_planner.app.core.repositories.local_store import (
    equipment as equipment_lib,
)
from trip_planner.app.core.repositories.local_store import guide as guide_lib
from trip_planner.app.core.repositories.local_store import (
    scenario as scenario_lib,
)
from trip_planner.app.core.repositories.local_store import trail as trail_lib
from trip_planner.app.core.repositories.postgres import (
    gear_category as gear_category_db_lib,
)
from trip_planner.app.core.repositories.postgres import (
    gear_product as gear_product_db_lib,
)
from trip_planner.app.core.repositories.postgres import trail as trail_db_lib
from trip_planner.app.inference.services import agui as agui_lib
from trip_planner.app.inference.services import indexing as indexing_lib
from trip_planner.app.inference.services import simulation as simulation_lib
from trip_planner.app.ml.environment import run_context as run_context_lib
from trip_planner.app.ml.equipment_check import core as equipment_check_lib
from trip_planner.app.ml.evaluation import core as evaluation_lib
from trip_planner.app.ml.fitness_assessment import core as fitness_lib
from trip_planner.app.ml.source_data_indexing import (
    core as source_data_indexing_lib,
)
from trip_planner.app.ml.trail_selection import core as trail_selection_lib
from trip_planner.app.ml.weather_forecast import abstract as forecast_lib
from trip_planner.app.ml.weather_forecast import fixture as fixture_lib
from trip_planner.app.ml.weather_forecast import open_meteo as open_meteo_lib
from trip_planner.app.pipelines.source_data_indexing import (
    core as source_data_pipeline_lib,
)

logger = logging.getLogger(__name__)


@dataclasses.dataclass
class _Runtime:
    simulation: simulation_lib.SimulationService
    agui: agui_lib.AgUiService
    indexing: indexing_lib.IndexingService
    database: database_lib.DatabaseClient
    weather_forecast: forecast_lib.AbstractWeatherForecast
    observability: observability_lib.ObservabilityCallbacks


class InferenceService:
    """Holds the request services and the clients they share.

    Attributes:
        simulation: Runs and reads simulation batches.
        agui: Streams live runs to the UI over AG-UI.
        indexing: Loads source data files from MinIO into the database.
    """

    def __init__(self, runtime: _Runtime):
        """Initializes the service; use `create` instead.

        Args:
            runtime: The built components.
        """
        self.simulation = runtime.simulation
        self.agui = runtime.agui
        self.indexing = runtime.indexing
        self._database = runtime.database
        self._weather_forecast = runtime.weather_forecast
        self._observability = runtime.observability

    @classmethod
    async def create(
        cls, configuration: config.Configuration
    ) -> 'InferenceService':
        """Builds the runtime off the event loop and returns the service."""
        runtime = await asyncio.to_thread(_build_runtime, configuration)
        return cls(runtime)

    async def close(self) -> None:
        """Closes every client and flushes the traces."""
        await self._weather_forecast.close()
        await self._database.close()
        await asyncio.to_thread(self._observability.close)


def _build_runtime(configuration: config.Configuration) -> _Runtime:
    simulation_config = configuration.simulation
    agents_config = configuration.agents
    data_dir = simulation_config.data_dir

    trail_repository = trail_lib.TrailRepository(data_dir / 'trails.json')
    equipment_repository = equipment_lib.EquipmentRepository(
        data_dir / 'equipment.json'
    )
    guide_repository = guide_lib.GuideRepository(data_dir / 'guides.json')
    scenario_repository = scenario_lib.ScenarioRepository(
        simulation_config.scenario_path
    )

    weather_config = configuration.weather
    if weather_config.variant == 'open_meteo':
        weather_forecast = open_meteo_lib.OpenMeteoWeatherForecast(
            weather_config, httpx.AsyncClient()
        )
    else:
        weather_forecast = fixture_lib.FixtureWeatherForecast(weather_config)
    logger.info('Weather forecast variant: %s', weather_config.variant)

    run_context_provider = run_context_lib.RunContextProvider()
    tool_set = tools_lib.ToolSet(
        run_context_provider=run_context_provider,
        fitness_assessment=fitness_lib.FitnessAssessment(),
        trail_selection=trail_selection_lib.TrailSelection(trail_repository),
        equipment_check=equipment_check_lib.EquipmentCheck(
            equipment_repository
        ),
        weather_forecast=weather_forecast,
        trail_repository=trail_repository,
        equipment_repository=equipment_repository,
        guide_repository=guide_repository,
        simulation_config=simulation_config,
    )
    observability = observability_lib.ObservabilityCallbacks(
        configuration.observability
    )
    agent_kwargs = {
        'chat_model': _chat_model(configuration, agents_config.model_name),
        'tool_set': tool_set,
        'run_context_provider': run_context_provider,
        'observability': observability,
        'recursion_limit': agents_config.recursion_limit,
    }
    agents = [
        customer_lib.CustomerAssistantAgent(
            checkpointer=memory.InMemorySaver(), **agent_kwargs
        ),
        operations_lib.OperationsAssistantAgent(
            checkpointer=memory.InMemorySaver(), **agent_kwargs
        ),
    ]
    simulation_service = simulation_lib.SimulationService(
        agents=agents,
        human_chat_model=_chat_model(
            configuration, agents_config.human_model_name
        ),
        run_context_provider=run_context_provider,
        observability=observability,
        scenario_repository=scenario_repository,
        evaluator=evaluation_lib.BatchEvaluator(),
        simulation_config=simulation_config,
        agents_config=agents_config,
    )
    database = database_lib.DatabaseClient(configuration.database)
    return _Runtime(
        simulation=simulation_service,
        agui=agui_lib.AgUiService(simulation_service, simulation_config),
        indexing=_indexing_service(
            database, storage_lib.StorageClient(configuration.storage)
        ),
        database=database,
        weather_forecast=weather_forecast,
        observability=observability,
    )


def _indexing_service(
    database: database_lib.DatabaseClient,
    storage: storage_lib.StorageClient,
) -> indexing_lib.IndexingService:
    source_data_indexing = source_data_indexing_lib.SourceDataIndexing(
        trail_repository=trail_db_lib.TrailRepository(database),
        gear_category_repository=gear_category_db_lib.GearCategoryRepository(
            database
        ),
        gear_product_repository=gear_product_db_lib.GearProductRepository(
            database
        ),
    )
    return indexing_lib.IndexingService(
        source_data_pipeline_lib.SourceDataIndexingPipeline(
            source_data_lib.SourceDataProvider(storage),
            source_data_indexing,
        )
    )


def _chat_model(configuration: config.Configuration, model: str) -> ChatOpenAI:
    agents_config = configuration.agents
    return ChatOpenAI(
        model=model,
        temperature=agents_config.temperature,
        seed=agents_config.seed,
        max_retries=agents_config.max_retries,
        timeout=agents_config.request_timeout_s,
        api_key=configuration.openai.api_key,
        base_url=configuration.openai.base_url,
    )
