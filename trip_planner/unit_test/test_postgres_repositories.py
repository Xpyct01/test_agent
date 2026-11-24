"""Tests of the Postgres repositories the agents read, without a server."""

import decimal

from sqlalchemy.dialects import postgresql

from trip_planner.app.core.repositories.postgres import (
    equipment_item as equipment_item_lib,
)
from trip_planner.app.core.repositories.postgres import guide as guide_lib
from trip_planner.app.core.repositories.postgres import (
    rental_stock as rental_stock_lib,
)
from trip_planner.app.core.repositories.postgres import trail as trail_lib
from trip_planner.app.core.sql_models import equipment
from trip_planner.app.core.sql_models import guide
from trip_planner.app.core.sql_models import trail


class _FakeDatabase:
    """Returns canned rows and records the statements it was given."""

    def __init__(self, rows):
        self.statements = []
        self._rows = rows

    def transaction(self):
        database = self

        class _Result:

            def all(self):
                return database._rows

        class _Session:

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                del args  # Unused.

            async def scalars(self, statement):
                database.statements.append(statement)
                return _Result()

            async def execute(self, statement):
                database.statements.append(statement)
                return _Result()

        return _Session()

    def sql(self, index=0):
        return str(
            self.statements[index].compile(
                dialect=postgresql.dialect(),
                compile_kwargs={'literal_binds': True},
            )
        )


def _park_trail(**overrides):
    values = dict(
        code='PR-PNPE 26', name='Sin Desnivel',
        trail_type=trail.TrailType.SHORT_DISTANCE, length_km=4.0,
        duration_h=1.5, difficulty=trail.TrailDifficulty.VERY_HARD,
        source_url='https://x/26',
    )
    return trail.Trail(**{**values, **overrides})


async def test_trail_uses_code_as_id_and_keeps_uncurated_fields_empty():
    database = _FakeDatabase([_park_trail()])

    trails = await trail_lib.TrailRepository(database).list_all()

    assert trails[0].trail_id == 'PR-PNPE 26'
    assert trails[0].difficulty == 'very_hard'
    assert trails[0].elevation_gain_m is None
    assert trails[0].massif is None and trails[0].route_type is None
    assert trails[0].highlights == []
    assert 'ORDER BY trails.id' in database.sql()


async def test_trail_get_filters_by_code():
    curated = _park_trail(
        code='ruta_del_cares', ascent_m=350, massif='Central',
        route_type=trail.RouteType.LINEAR, highlights=['gorge'],
        rockfall_risk=True, difficulty=trail.TrailDifficulty.MODERATE,
    )
    database = _FakeDatabase([curated])

    found = await trail_lib.TrailRepository(database).get('ruta_del_cares')

    assert found.elevation_gain_m == 350
    assert found.route_type == 'linear'
    assert found.rockfall_risk
    assert "trails.code = 'ruta_del_cares'" in database.sql()
    assert await trail_lib.TrailRepository(_FakeDatabase([])).get('x') is None


async def test_equipment_item_maps_slug_and_price():
    database = _FakeDatabase([
        equipment.EquipmentItem(
            slug='helmet', name='Climbing helmet',
            required_when=equipment.RequiredWhen.ROCKFALL,
            aliases=['helmet'], rentable=True,
            rental_price_eur=decimal.Decimal('5.00'),
        ),
        equipment.EquipmentItem(
            slug='sun_hat', name='Sun hat',
            required_when=equipment.RequiredWhen.HOT,
        ),
    ])

    items = await equipment_item_lib.EquipmentItemRepository(
        database
    ).list_all()

    assert [i.item_id for i in items] == ['helmet', 'sun_hat']
    assert items[0].required_when == 'rockfall'
    assert items[0].rental_price_eur == 5.0
    assert not items[1].rentable and items[1].rental_price_eur == 0.0


async def test_guide_maps_iso_weekdays_and_skips_inactive():
    database = _FakeDatabase([
        guide.Guide(
            full_name='Lucia Prieto', max_party_size=6,
            unavailable_weekdays=[2, 1],
        )
    ])
    repository = guide_lib.GuideRepository(database)

    found = await repository.get('  lucia PRIETO ')

    assert found.name == 'Lucia Prieto'
    assert found.unavailable_weekdays == ['Monday', 'Tuesday']
    assert found.max_party_size == 6
    where = database.sql().split('WHERE')[1]
    assert 'guides.is_active' in where
    assert "lower(guides.full_name) = 'lucia prieto'" in where


async def test_rental_stock_by_item_slug():
    database = _FakeDatabase([('hiking_boots', 5), ('helmet', 2)])

    units = await rental_stock_lib.RentalStockRepository(
        database
    ).units_by_item()

    assert units == {'hiking_boots': 5, 'helmet': 2}
    assert 'JOIN rental_stock' in database.sql()
