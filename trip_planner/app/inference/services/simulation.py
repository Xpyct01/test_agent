"""Runs batches of simulations and stores their trajectories."""

import asyncio
from collections.abc import Sequence
import datetime
import logging
import pathlib
import re
import uuid

from langchain_core import language_models

from trip_planner.app.agents import abstract as agent_lib
from trip_planner.app.agents.callbacks import observability as observability_lib
from trip_planner.app.config import agents as agents_config_lib
from trip_planner.app.config import simulation as simulation_config_lib
from trip_planner.app.core import errors
from trip_planner.app.core.repositories.local_store import (
    booking as booking_lib,
)
from trip_planner.app.core.repositories.local_store import (
    rental_stock as rental_stock_lib,
)
from trip_planner.app.core.repositories.local_store import (
    scenario as scenario_lib,
)
from trip_planner.app.core.repositories.postgres import (
    rental_stock as rental_stock_db_lib,
)
from trip_planner.app.core.repositories.local_store import (
    trail_status as trail_status_lib,
)
from trip_planner.app.core.schemas import api
from trip_planner.app.core.schemas import simulation
from trip_planner.app.ml.environment import core as environment_lib
from trip_planner.app.ml.environment import message_bus as message_bus_lib
from trip_planner.app.ml.environment import participant as participant_lib
from trip_planner.app.ml.environment import run_context as run_context_lib
from trip_planner.app.ml.environment import trajectory as trajectory_lib
from trip_planner.app.ml.evaluation import core as evaluation_lib
from trip_planner.app.ml.fault_injection import core as fault_injection_lib
from trip_planner.app.ml.simulated_human import core as simulated_human_lib

logger = logging.getLogger(__name__)

CUSTOMER_ID = 'human_a'
_GUIDE_ID = 'human_b'
_SUMMARY_FILE = 'summary.json'
_LIVE_DIR = 'live'
_BATCH_ID_PATTERN = re.compile(r'^batch-[0-9]{8}-[0-9]{6}-[0-9a-f]{6}$')


class SimulationService:
    """Plays a scenario several times in a row and evaluates the batch.

    Runs are sequential, as the task asks for "5 runs in a row"; inside a
    run the participants act concurrently. Run `i` injects faults with seed
    `base_seed + i`, so each run meets different failures.
    """

    def __init__(
        self,
        agents: Sequence[agent_lib.AbstractAgent],
        human_chat_model: language_models.BaseChatModel,
        run_context_provider: run_context_lib.RunContextProvider,
        observability: observability_lib.ObservabilityCallbacks,
        scenario_repository: scenario_lib.ScenarioRepository,
        rental_stock_repository: rental_stock_db_lib.RentalStockRepository,
        evaluator: evaluation_lib.BatchEvaluator,
        simulation_config: simulation_config_lib.SimulationConfiguration,
        agents_config: agents_config_lib.AgentsConfiguration,
    ):
        """Initializes the service.

        Args:
            agents: The two assistants, shared by every run.
            human_chat_model: The LLM playing the humans.
            run_context_provider: Makes the active run visible to tools.
            observability: Tracing callbacks.
            scenario_repository: The test scenarios.
            rental_stock_repository: Units of rental gear the company owns;
                every run starts from them.
            evaluator: Summarises a batch.
            simulation_config: Simulation settings.
            agents_config: Agent settings; token prices are read.
        """
        self._agents = list(agents)
        self._human_chat_model = human_chat_model
        self._run_context_provider = run_context_provider
        self._observability = observability
        self._scenario_repository = scenario_repository
        self._rental_stock_repository = rental_stock_repository
        self._evaluator = evaluator
        self._simulation_config = simulation_config
        self._agents_config = agents_config

    @property
    def run_context_provider(self) -> run_context_lib.RunContextProvider:
        """Makes the active run visible to tools and participants."""
        return self._run_context_provider

    async def run_batch(
        self, request: api.SimulationRequest
    ) -> api.SimulationResponse:
        """Plays the requested scenario `runs` times and evaluates it.

        Raises:
            errors.InvalidRequestError: The scenario does not exist.
        """
        scenario = self._scenario_repository.load(request.scenario)
        batch_id = self.new_batch_id()
        batch_dir = self._simulation_config.output_dir / batch_id
        await asyncio.to_thread(batch_dir.mkdir, parents=True, exist_ok=True)
        planning_date = scenario.start_date or datetime.date.today()
        logger.info(
            'Batch %s: %d runs of %r, planning date %s',
            batch_id, request.runs, scenario.name, planning_date,
        )

        trajectories, files = [], []
        for run_index in range(request.runs):
            run = await self.build_run(batch_id, run_index, scenario)
            trajectory = await run.run()
            path = batch_dir / f'run_{run_index}.json'
            await asyncio.to_thread(
                path.write_text, trajectory.model_dump_json(indent=2),
                encoding='utf-8',
            )
            trajectories.append(trajectory)
            files.append(str(path))
            logger.info(
                'Run %d: %s, outcome %s, %d ticks',
                run_index, trajectory.status, trajectory.outcome_key,
                trajectory.metrics.ticks,
            )
        self._observability.flush()

        summary = self._evaluator.summarize(
            batch_id, scenario.name, trajectories, files
        )
        await asyncio.to_thread(
            (batch_dir / _SUMMARY_FILE).write_text,
            summary.model_dump_json(indent=2),
            encoding='utf-8',
        )
        return api.SimulationResponse(
            summary=summary, trajectories=trajectories
        )

    async def get_batch(self, batch_id: str) -> api.SimulationResponse:
        """Returns a stored batch.

        Raises:
            errors.InvalidRequestError: No batch has that id.
        """
        batch_dir = self._simulation_config.output_dir / batch_id
        summary_path = batch_dir / _SUMMARY_FILE
        if not _BATCH_ID_PATTERN.match(batch_id) or not summary_path.is_file():
            raise errors.InvalidRequestError(f'Unknown batch: {batch_id!r}')
        summary = simulation.BatchSummary.model_validate_json(
            await asyncio.to_thread(summary_path.read_text, encoding='utf-8')
        )
        trajectories = [
            simulation.Trajectory.model_validate_json(
                await asyncio.to_thread(
                    pathlib.Path(path).read_text, encoding='utf-8'
                )
            )
            for path in summary.trajectory_files
        ]
        return api.SimulationResponse(
            summary=summary, trajectories=trajectories
        )

    def load_scenario(self, name: str | None) -> simulation.Scenario:
        """Returns a scenario by file stem, or the default one.

        Raises:
            errors.InvalidRequestError: The scenario does not exist.
        """
        return self._scenario_repository.load(name)

    def new_batch_id(self, prefix: str = 'batch') -> str:
        """Returns a fresh, time-ordered batch id."""
        now = datetime.datetime.now()
        return f'{prefix}-{now:%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:6]}'

    async def build_run(
        self,
        batch_id: str,
        run_index: int,
        scenario: simulation.Scenario,
        customer: participant_lib.Participant | None = None,
    ) -> environment_lib.Simulation:
        """Builds one run of a scenario, ready to `run()`.

        Args:
            batch_id: Batch the run belongs to.
            run_index: Position in the batch; picks the fault seed.
            scenario: The scenario to play.
            customer: Who plays Human A; the simulated persona if omitted.

        Returns:
            The simulation; its `run_context` can be observed before it runs.
        """
        config = self._simulation_config
        fault_seed = config.base_seed + run_index
        planning_date = scenario.start_date or datetime.date.today()
        context = run_context_lib.RunContext(
            run_id=f'{batch_id}-run{run_index}',
            batch_id=batch_id,
            run_index=run_index,
            scenario=scenario,
            planning_date=planning_date,
            fault_seed=fault_seed,
            bus=message_bus_lib.MessageBus(),
            recorder=trajectory_lib.TrajectoryRecorder(
                self._agents_config.input_cost_per_million,
                self._agents_config.output_cost_per_million,
            ),
            fault_injector=fault_injection_lib.FaultInjector(
                fault_seed, config.failure_rates
            ),
            trail_status=trail_status_lib.TrailStatusRepository(
                scenario.trail_closures
            ),
            bookings=booking_lib.BookingRepository(),
            rental_stock=rental_stock_lib.RentalStockRepository(
                await self._rental_stock_repository.units_by_item()
            ),
        )
        humans = [
            customer
            or self._human(CUSTOMER_ID, 'agent_a', scenario.customer, True),
            self._human(_GUIDE_ID, 'agent_b', scenario.guide, False),
        ]
        return environment_lib.Simulation(
            participants=[*self._agents, *humans],
            initiators=[CUSTOMER_ID, _GUIDE_ID],
            run_context=context,
            run_context_provider=self._run_context_provider,
            max_ticks=config.max_ticks,
        )

    async def save_live_trajectory(
        self, trajectory: simulation.Trajectory
    ) -> pathlib.Path:
        """Writes the trajectory of a live run under `<output_dir>/live/`."""
        live_dir = self._simulation_config.output_dir / _LIVE_DIR
        await asyncio.to_thread(live_dir.mkdir, parents=True, exist_ok=True)
        path = live_dir / f'{trajectory.run_id}.json'
        await asyncio.to_thread(
            path.write_text, trajectory.model_dump_json(indent=2),
            encoding='utf-8',
        )
        self._observability.flush()
        return path

    def _human(
        self,
        participant_id: str,
        assistant_id: str,
        persona: simulation.Persona,
        closes_scenario: bool,
    ) -> simulated_human_lib.SimulatedHuman:
        return simulated_human_lib.SimulatedHuman(
            participant_id=participant_id,
            assistant_id=assistant_id,
            persona=persona,
            closes_scenario=closes_scenario,
            chat_model=self._human_chat_model,
            run_context_provider=self._run_context_provider,
            observability=self._observability,
        )
