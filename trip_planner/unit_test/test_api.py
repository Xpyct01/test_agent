"""Tests of the HTTP routes with the service replaced."""

from fastapi import testclient
import pytest

from trip_planner.app import service_launcher
from trip_planner.app.core import errors
from trip_planner.app.core.schemas import api
from trip_planner.app.core.schemas import simulation
from trip_planner.app.inference.routers import state


class _FakeSimulationService:

    async def run_batch(self, request):
        summary = simulation.BatchSummary(
            batch_id='batch-x', scenario='default', runs=request.runs,
            statuses={'converged': request.runs}, outcome_counts={},
            modal_outcome=None, convergence_rate=1.0, success_rate=1.0,
            mean_ticks=8, mean_wall_time_s=1, p95_wall_time_s=1,
            mean_llm_calls=10, total_tokens=0, total_cost_usd=0,
            injected_failures=0, failure_recovery_rate=1.0,
            trajectory_files=[],
        )
        return api.SimulationResponse(summary=summary, trajectories=[])

    async def get_batch(self, batch_id):
        raise errors.InvalidRequestError(f'Unknown batch: {batch_id!r}')


@pytest.fixture
def client():
    app = service_launcher.app
    app.dependency_overrides[state.simulation_service] = (
        lambda: _FakeSimulationService()
    )
    with testclient.TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_live_probe(client):
    assert client.get('/health/live').status_code == 200


def test_run_simulations(client):
    response = client.post('/simulations', json={'runs': 2})
    assert response.status_code == 200
    assert response.json()['summary']['runs'] == 2


def test_runs_are_bounded(client):
    assert client.post('/simulations', json={'runs': 50}).status_code == 422


def test_unknown_batch_is_400(client):
    response = client.get('/simulations/nope')
    assert response.status_code == 400
    assert 'Unknown batch' in response.json()['detail']


def test_ready_is_503_until_built():
    app = service_launcher.app
    app.state.application_state = state.ApplicationState()
    response = testclient.TestClient(app).get('/health/ready')
    assert response.status_code == 503
