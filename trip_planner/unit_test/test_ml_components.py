"""Tests of the deterministic ML components and the fault injector."""

import pytest

from trip_planner.app.core import errors
from trip_planner.app.core.schemas import trip
from trip_planner.app.ml.equipment_check import core as equipment_check_lib
from trip_planner.app.ml.fault_injection import core as fault_injection_lib
from trip_planner.app.ml.fitness_assessment import core as fitness_lib
from trip_planner.app.ml.trail_selection import core as trail_selection_lib
from trip_planner.unit_test import fakes


def test_fitness_reduces_elevation_for_knee_injury():
    profile = fitness_lib.FitnessAssessment().assess(
        45, 'moderate', ['mild left-knee injury']
    )
    assert profile.max_distance_km == 14.0
    assert profile.max_elevation_gain_m == 490
    assert profile.max_difficulty == 'moderate'
    assert profile.needs_trekking_poles and profile.has_joint_issues


def test_fitness_caps_difficulty_for_heart_condition():
    profile = fitness_lib.FitnessAssessment().assess(
        65, 'high', ['heart condition']
    )
    assert profile.max_difficulty == 'easy'


async def test_trail_selection_ranks_interests_then_length(
    trail_repository,
):
    options, excluded = await trail_selection_lib.TrailSelection(
        trail_repository
    ).select(14.0, 490, 'moderate', ['lakes', 'gorge'])
    assert [o.trail.trail_id for o in options] == [
        'ruta_del_cares', 'bulnes_poncebos', 'lagos_covadonga',
        'fuente_de_aliva',
    ]
    assert excluded == 4


async def test_trail_selection_skips_trails_without_ascent():
    class _Repository:
        async def list_all(self):
            return [trip.Trail(
                trail_id='PR-PNPE 26', name='x', massif=None,
                start_point=None, distance_km=4.0, elevation_gain_m=None,
                duration_h=1.5, difficulty='easy', route_type=None,
                highlights=[], rockfall_risk=False, source_url='u',
            )]

    options, excluded = await trail_selection_lib.TrailSelection(
        _Repository()
    ).select(14.0, 490, 'moderate', [])
    assert options == [] and excluded == 1


async def test_fixture_forecast_maps_days_and_scores(weather_forecast):
    days = await weather_forecast.forecast(fakes.PLANNING_DATE)
    assert days[0].date == fakes.PLANNING_DATE
    best = max(days, key=lambda d: d.hiking_score)
    assert best.date.isoformat() == '2026-11-29'


async def test_equipment_check_splits_gear(
    equipment_repository, trail_repository, weather_forecast
):
    days = await weather_forecast.forecast(fakes.PLANNING_DATE)
    result = await equipment_check_lib.EquipmentCheck(
        equipment_repository
    ).check(
        await trail_repository.get('bulnes_poncebos'),
        days[4],
        ['hiking boots', 'a rain jacket', 'backpack', 'lucky charm'],
        has_joint_issues=True,
    )
    assert result.already_owned == ['hiking_boots', 'backpack']
    assert result.missing_rentable == [
        'map_or_gps', 'trekking_poles', 'helmet'
    ]
    assert result.missing_to_buy == [
        'water_2l', 'sun_protection', 'first_aid_kit'
    ]
    assert result.unrecognized_owned == ['lucky charm']


def test_fault_injector_is_reproducible_per_seed():
    def pattern(seed):
        injector = fault_injection_lib.FaultInjector(seed, {'a': 0.5})
        outcome = []
        for _ in range(20):
            try:
                injector.maybe_fail('a')
                outcome.append(True)
            except errors.TransientActionError:
                outcome.append(False)
        return outcome

    assert pattern(1) == pattern(1)
    assert pattern(1) != pattern(2)
    assert not all(pattern(1)) and any(pattern(1))


def test_fault_injector_ignores_unlisted_actions():
    fault_injection_lib.FaultInjector(0, {'a': 1.0}).maybe_fail('b')
    with pytest.raises(errors.TransientActionError):
        fault_injection_lib.FaultInjector(0, {'a': 1.0}).maybe_fail('a')
