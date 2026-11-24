"""CLI entry point: plays the scenario N times and prints the summary.

Usage:
    uv run python -m trip_planner.app.simulation_launcher --runs 5
"""

import argparse
import asyncio
import logging
import sys

from trip_planner.app import config
from trip_planner.app.config import weather as weather_lib
from trip_planner.app.core.schemas import api
from trip_planner.app.core.schemas import simulation
from trip_planner.app.inference.services import core as services_lib

logger = logging.getLogger(__name__)


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--runs', type=int, default=5,
                        help='Runs in a row (default: 5).')
    parser.add_argument('--scenario', default=None,
                        help='Scenario file stem under data/scenarios.')
    parser.add_argument('--weather', choices=['open_meteo', 'fixture'],
                        default=None, help='Override TRIP_WEATHER_VARIANT.')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='Debug logging.')
    return parser.parse_args(argv)


async def _run(args: argparse.Namespace) -> simulation.BatchSummary:
    configuration = config.Configuration()
    if args.weather:
        configuration.weather = weather_lib.WeatherConfiguration(
            variant=args.weather
        )
    service = await services_lib.InferenceService.create(configuration)
    try:
        response = await service.simulation.run_batch(
            api.SimulationRequest(runs=args.runs, scenario=args.scenario)
        )
    finally:
        await service.close()
    for trajectory in response.trajectories:
        print(
            f'run {trajectory.run_index}: {trajectory.status:<9} '
            f'ticks={trajectory.metrics.ticks:<3} '
            f'faults={trajectory.metrics.injected_failures:<2} '
            f'tokens={trajectory.metrics.prompt_tokens + trajectory.metrics.completion_tokens:<6} '
            f'outcome={trajectory.outcome_key}'
        )
    return response.summary


def main() -> None:
    """Runs the CLI."""
    args = _parse_args(sys.argv[1:])
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format='%(asctime)s %(levelname)s %(name)s: %(message)s',
    )
    for noisy in ('httpx', 'openai', 'httpcore'):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    summary = asyncio.run(_run(args))
    print(summary.model_dump_json(indent=2, exclude={'trajectory_files'}))
    print(f'Trajectories: {summary.trajectory_files[0].rsplit("run_", 1)[0]}')


if __name__ == '__main__':
    main()
