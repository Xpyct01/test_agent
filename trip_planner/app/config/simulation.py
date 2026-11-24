"""Settings of the discrete-time simulation."""

import pathlib

import pydantic
import pydantic_settings

from trip_planner.app.config import base

_DATA_DIR = pathlib.Path(__file__).resolve().parents[2] / 'data'


def _default_failure_rates() -> dict[str, float]:
    return {
        'get_weather_forecast': 0.3,
        'get_trail_status': 0.3,
        'check_guide_availability': 0.2,
        'create_booking': 0.3,
        'reserve_rental_gear': 0.2,
    }


class SimulationConfiguration(base.ConfigurationSection):
    """Simulation settings, read from the `TRIP_SIMULATION_` variables.

    Attributes:
        max_ticks: Ticks after which a run stops with status `timeout`.
        base_seed: Seed of run 0; run `i` uses `base_seed + i` for faults.
        failure_rates: Probability that one attempt of an action fails,
            by action name (a JSON object in the environment).
        max_tool_attempts: Attempts of a faulty action before the tool
            reports the failure to the LLM.
        retry_base_delay_s: First back-off delay between attempts; doubles
            on each retry.
        data_dir: Directory with the trails, equipment and calendar data.
        scenario_path: Scenario used when a request names none.
        output_dir: Directory the trajectories and summaries are written to.
        live_input_timeout_s: How long a live (AG-UI) run waits for the
            user's next message before it gives up and stalls.
        max_live_runs: Live runs allowed at the same time.
    """

    model_config = pydantic_settings.SettingsConfigDict(
        env_prefix='TRIP_SIMULATION_'
    )

    # The default scenario converges in ~8 ticks.
    max_ticks: int = 20
    base_seed: int = 7
    failure_rates: dict[str, float] = pydantic.Field(
        default_factory=_default_failure_rates
    )
    max_tool_attempts: int = 3
    retry_base_delay_s: float = 0.2
    data_dir: pathlib.Path = _DATA_DIR
    scenario_path: pathlib.Path = _DATA_DIR / 'scenarios' / 'default.yaml'
    output_dir: pathlib.Path = pathlib.Path('trajectories')
    live_input_timeout_s: float = 1800.0
    max_live_runs: int = 20
