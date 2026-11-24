"""Tests of source data indexing with MinIO and the database replaced."""

from fastapi import testclient
import pytest
from sqlalchemy.dialects import postgresql

from trip_planner.app import service_launcher
from trip_planner.app.config import database as database_config_lib
from trip_planner.app.config import storage as storage_config_lib
from trip_planner.app.core import errors
from trip_planner.app.core.clients import database as database_lib
from trip_planner.app.core.clients import storage as storage_lib
from trip_planner.app.core.providers import source_data as source_data_lib
from trip_planner.app.core.repositories.postgres import (
    gear_category as gear_category_db_lib,
)
from trip_planner.app.core.repositories.postgres import trail as trail_db_lib
from trip_planner.app.core.schemas import api
from trip_planner.app.core.schemas import indexing
from trip_planner.app.inference.routers import state
from trip_planner.app.inference.services import indexing as indexing_lib
from trip_planner.app.ml.source_data_indexing import core as component_lib
from trip_planner.app.ml.source_data_indexing import row_mapping
from trip_planner.app.pipelines.source_data_indexing import (
    core as pipeline_lib,
)

_TRAIL_COLUMNS = (
    'trail_code,name,section,trail_type,length_km,ascent_m,descent_m,'
    'duration_h,difficulty,length_text,elevation_text,duration_text,'
    'difficulty_text,description,how_to,points_of_interest,precautions_es,'
    'precautions_en,map_pdf_url,profile_pdf_url,source_url'
)
_TRAILS_CSV = '\n'.join([
    _TRAIL_COLUMNS,
    'PR-PNPE 1,Ruta De Frassinelli,Senderos (PR),short_distance,15.1,971,971,'
    '3.75,easy,"15,1 Km.",971 m.,3 h. 45 min.,Baja,Desc,,,,,'
    'https://x/map.pdf,https://x/profile.pdf,https://x/1',
    'PR-PNPE 26,Sin Desnivel,Senderos (PR),short_distance,4,,,1.5,moderate,'
    '4 Km.,,1 h. 30 min.,Media,Desc,,,,,,,https://x/26',
])
_GEAR_CSV = '\n'.join([
    'category,item_type,product,is_swap_out,reasons,product_url,source_url',
    'Pack System,Pack,Osprey Exos 55,False,Light | Strong,https://g/1,'
    'https://g',
    'Pack System,Pack liner,Sea to Summit,False,Dry,https://g/2,https://g',
    'Swap Outs,Shell,Rain Jacket,True,,https://g/3,https://g',
])


class _FakeStorageClient:
    """Serves objects from a dict instead of MinIO."""

    bucket = 'test-bucket'

    def __init__(self, objects):
        self._objects = objects

    async def read_bytes(self, object_name):
        if object_name not in self._objects:
            raise storage_lib.ObjectNotFoundError(f'No object {object_name!r}')
        return self._objects[object_name].encode('utf-8')


class _FakeRepository:
    """Records the rows of every `upsert` call."""

    def __init__(self):
        self.rows = []

    async def upsert(self, rows):
        self.rows.extend(rows)
        return len(rows)


class _FakeCategoryRepository(_FakeRepository):

    async def upsert(self, rows):
        self.rows.extend(rows)
        return {row.name: i for i, row in enumerate(rows, start=1)}


@pytest.fixture
def repositories():
    return {
        'trail_repository': _FakeRepository(),
        'gear_category_repository': _FakeCategoryRepository(),
        'gear_product_repository': _FakeRepository(),
    }


def _pipeline(repositories, objects):
    return pipeline_lib.SourceDataIndexingPipeline(
        source_data_lib.SourceDataProvider(_FakeStorageClient(objects)),
        component_lib.SourceDataIndexing(**repositories),
    )


async def test_run_indexes_trails_and_gear(repositories):
    pipeline = _pipeline(
        repositories, {'trails.csv': _TRAILS_CSV, 'gear.csv': _GEAR_CSV}
    )

    report = await pipeline.run('trails.csv', 'gear.csv')

    assert report == indexing.IndexingReport(
        trails=2, gear_categories=2, gear_products=3
    )
    no_elevation = repositories['trail_repository'].rows[1]
    assert no_elevation.code == 'PR-PNPE 26'
    assert no_elevation.ascent_m is None
    assert no_elevation.map_pdf_url is None
    products = repositories['gear_product_repository'].rows
    assert products[0].reasons == ['Light', 'Strong']
    assert products[2].reasons == []
    assert products[2].is_swap_out
    assert products[2].category_id == 2


async def test_run_only_gear_skips_trails(repositories):
    report = await _pipeline(repositories, {'gear.csv': _GEAR_CSV}).run(
        gear_items_file='gear.csv'
    )
    assert report.trails == 0
    assert not repositories['trail_repository'].rows


@pytest.mark.parametrize(
    ('objects', 'name', 'message'),
    [
        ({}, 'missing.csv', 'missing.csv'),
        ({'trails.json': '[]'}, 'trails.json', 'Not a CSV file'),
        ({'trails.csv': _GEAR_CSV}, 'trails.csv', 'lacks the columns'),
        (
            {'trails.csv': _TRAILS_CSV.replace('easy', 'trivial')},
            'trails.csv',
            'line 2: difficulty',
        ),
    ],
)
async def test_run_bad_trails_file_writes_nothing(
    repositories, objects, name, message
):
    with pytest.raises(errors.InvalidRequestError, match=message):
        await _pipeline(repositories, objects).run(trails_file=name)
    assert not any(repo.rows for repo in repositories.values())


async def test_index_trail_without_length_writes_nothing(repositories):
    csv_text = _TRAILS_CSV.replace(',15.1,', ',,')
    with pytest.raises(errors.InvalidRequestError, match='PR-PNPE 1'):
        await _pipeline(repositories, {'t.csv': csv_text}).run('t.csv')
    assert not repositories['trail_repository'].rows


async def test_index_repeated_gear_row_written_once(repositories):
    repeated = _GEAR_CSV + '\nSwap Outs,Shell,Rain Jacket,True,New,u,s'
    await _pipeline(repositories, {'g.csv': repeated}).run(
        gear_items_file='g.csv'
    )
    products = repositories['gear_product_repository'].rows
    assert len(products) == 3
    assert products[2].reasons == ['New']


class _RecordingDatabase:
    """Captures the statement instead of running it."""

    def __init__(self, result_rows):
        self.statements = []
        self._result_rows = result_rows

    def transaction(self):
        database = self

        class _Session:

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                del args  # Unused.

            async def execute(self, statement):
                database.statements.append(statement)

                class _Result:

                    def all(self):
                        return database._result_rows

                return _Result()

        return _Session()


def _sql(statement):
    return str(statement.compile(dialect=postgresql.dialect()))


async def test_trail_upsert_keeps_curated_columns():
    database = _RecordingDatabase([(1,)])
    records = await source_data_lib.SourceDataProvider(
        _FakeStorageClient({'t.csv': _TRAILS_CSV})
    ).read_trails('t.csv')

    written = await trail_db_lib.TrailRepository(database).upsert(
        [row_mapping.to_trail_row(records[0])]
    )

    assert written == 1
    update = _sql(database.statements[0]).split('DO UPDATE SET')[1]
    assert 'ON CONFLICT (code)' in _sql(database.statements[0])
    assert 'description = excluded.description' in update
    assert 'massif' not in update
    assert 'highlights' not in update
    assert 'created_at' not in update


async def test_gear_category_upsert_returns_existing_rows():
    database = _RecordingDatabase([('Pack System', 7)])

    ids = await gear_category_db_lib.GearCategoryRepository(database).upsert(
        [row_mapping.to_gear_category_row('Pack System')]
    )

    assert ids == {'Pack System': 7}
    assert 'DO UPDATE SET name = excluded.name' in _sql(
        database.statements[0]
    )


def test_clients_build_without_a_server():
    database_lib.DatabaseClient(
        database_config_lib.DatabaseConfiguration(host='nowhere.invalid')
    )
    storage = storage_lib.StorageClient(
        storage_config_lib.StorageConfiguration(bucket='b')
    )
    assert storage.bucket == 'b'


async def test_index_source_data_service(repositories):
    service = indexing_lib.IndexingService(
        _pipeline(repositories, {'g.csv': _GEAR_CSV})
    )
    response = await service.index_source_data(
        api.IndexingRequest(gear_items_file='g.csv')
    )
    assert response.report.gear_products == 3


class _FakeIndexingService:

    def __init__(self):
        self.requests = []

    async def index_source_data(self, request):
        self.requests.append(request)
        return api.IndexingResponse(
            report=indexing.IndexingReport(trails=31), duration_s=0.1
        )


@pytest.fixture
def client_and_service():
    service = _FakeIndexingService()
    app = service_launcher.app
    app.dependency_overrides[state.indexing_service] = lambda: service
    with testclient.TestClient(app) as client:
        yield client, service
    app.dependency_overrides.clear()


def test_index_source_data_route(client_and_service):
    client, service = client_and_service
    response = client.post(
        '/indexing',
        json={'trails_file': 'trails.csv', 'gear_items_file': 'gear.csv'},
    )
    assert response.status_code == 200
    assert response.json()['report']['trails'] == 31
    assert service.requests[0].gear_items_file == 'gear.csv'


def test_index_source_data_route_needs_a_file(client_and_service):
    client, _ = client_and_service
    assert client.post('/indexing', json={}).status_code == 422
