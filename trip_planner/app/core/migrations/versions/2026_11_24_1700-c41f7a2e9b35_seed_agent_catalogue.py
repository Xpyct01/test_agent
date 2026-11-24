"""Seed the catalogue the agents read: trails, gear checklist, guides, stock.

These rows used to live in `trip_planner/data/{trails,equipment,guides,
rental_stock}.json`. The trails are the company's curated routes; their codes
are the ids the agents and scenarios use (e.g. `ruta_del_cares`), so they
never collide with the park codes `/indexing` writes (e.g. `PR-PNPE 3`).

Revision ID: c41f7a2e9b35
Revises: 8db0bcc31dad
Create Date: 2026-11-24 17:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'c41f7a2e9b35'
down_revision: Union[str, Sequence[str], None] = '8db0bcc31dad'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SOURCE_URL = 'https://parquenacionalpicoseuropa.es/'

# Frozen copies of the tables, so later model changes never alter this seed.
_TRAILS = sa.table(
    'trails',
    sa.column('code', sa.String),
    sa.column('name', sa.String),
    sa.column(
        'trail_type', postgresql.ENUM(name='trail_type', create_type=False)
    ),
    sa.column('length_km', sa.Float),
    sa.column('ascent_m', sa.Integer),
    sa.column('duration_h', sa.Float),
    sa.column(
        'difficulty',
        postgresql.ENUM(name='trail_difficulty', create_type=False),
    ),
    sa.column('source_url', sa.String),
    sa.column('massif', sa.String),
    sa.column('start_point', sa.String),
    sa.column(
        'route_type', postgresql.ENUM(name='route_type', create_type=False)
    ),
    sa.column('rockfall_risk', sa.Boolean),
    sa.column('highlights', postgresql.ARRAY(sa.Text)),
    *(sa.column(name, sa.Text) for name in (
        'length_text', 'elevation_text', 'duration_text', 'difficulty_text',
        'description', 'how_to', 'points_of_interest', 'precautions_es',
        'precautions_en',
    )),
)
# Published-text columns of the park's pages; NOT NULL without a server
# default, and empty for routes the company curated itself.
_EMPTY_TEXT = {
    name: '' for name in (
        'length_text', 'elevation_text', 'duration_text', 'difficulty_text',
        'description', 'how_to', 'points_of_interest', 'precautions_es',
        'precautions_en',
    )
}
_EQUIPMENT_ITEMS = sa.table(
    'equipment_items',
    sa.column('id', sa.Integer),
    sa.column('slug', sa.String),
    sa.column('name', sa.String),
    sa.column(
        'required_when',
        postgresql.ENUM(name='equipment_required_when', create_type=False),
    ),
    sa.column('aliases', postgresql.ARRAY(sa.Text)),
    sa.column('rentable', sa.Boolean),
    sa.column('rental_price_eur', sa.Numeric(8, 2)),
)
_GUIDES = sa.table(
    'guides',
    sa.column('full_name', sa.String),
    sa.column('max_party_size', sa.Integer),
    sa.column('unavailable_weekdays', postgresql.ARRAY(sa.SmallInteger)),
)
_RENTAL_STOCK = sa.table(
    'rental_stock',
    sa.column('equipment_item_id', sa.Integer),
    sa.column('units_total', sa.Integer),
)

# (code, name, massif, start point, length km, ascent m, duration h,
#  difficulty, route type, highlights, rockfall risk). Hard routes are
# listed as high mountain routes, the others as short-distance trails.
_TRAIL_ROWS = (
    ('lagos_covadonga', 'Lagos de Covadonga circuit (Enol and Ercina)',
     'Western (Cornion)', 'Lago Enol car park', 5.6, 180, 2.5, 'easy',
     'circular', ['lakes', 'views', 'wildlife'], False),
    ('ruta_del_cares', 'Ruta del Cares (Poncebos - Cain)',
     'Central (Urrieles)', 'Poncebos', 12.0, 350, 4.5, 'moderate', 'linear',
     ['gorge', 'river', 'views'], True),
    ('bulnes_poncebos', 'Bulnes village from Poncebos (Canal del Texu)',
     'Central (Urrieles)', 'Poncebos', 8.0, 420, 3.5, 'moderate',
     'out_and_back', ['gorge', 'villages', 'views'], True),
    ('mirador_ordiales', 'Mirador de Ordiales from Lago Enol',
     'Western (Cornion)', 'Lago Enol car park', 11.0, 550, 4.5, 'moderate',
     'out_and_back', ['views', 'cliffs', 'wildlife'], False),
    ('vega_de_ario', 'Vega de Ario from Lago de la Ercina',
     'Western (Cornion)', 'Lago de la Ercina', 15.0, 850, 6.0, 'hard',
     'out_and_back', ['lakes', 'views', 'mountains'], False),
    ('fuente_de_aliva', 'Fuente De - Aliva - Espinama',
     'Central (Urrieles)', 'Fuente De upper cable car station', 13.0, 250,
     4.0, 'moderate', 'linear', ['meadows', 'views', 'wildlife'], False),
    ('horcados_rojos', 'Horcados Rojos from Fuente De cable car',
     'Central (Urrieles)', 'Fuente De upper cable car station', 12.0, 800,
     6.0, 'hard', 'out_and_back', ['mountains', 'views'], True),
    # `urriellu_pandebano` in the JSON file; codes are at most 16 characters.
    ('picu_urriellu', 'Picu Urriellu refuge from Pandebano',
     'Central (Urrieles)', 'Collado de Pandebano', 11.0, 900, 6.0, 'hard',
     'out_and_back', ['mountains', 'views'], True),
)

# (slug, name, required when, aliases, rental price; None = not rentable).
_EQUIPMENT_ROWS = (
    ('hiking_boots', 'Hiking boots', 'always',
     ['boots', 'hiking boots', 'trekking boots', 'hiking shoes'], 8.0),
    ('backpack', 'Day backpack', 'always',
     ['backpack', 'rucksack', 'daypack', 'day pack', 'bag'], 5.0),
    ('water_2l', '2 litres of water', 'always',
     ['water', 'water bottle', 'hydration', 'bottle'], None),
    ('sun_protection', 'Sunscreen and sunglasses', 'always',
     ['sunscreen', 'sunglasses', 'sun cream', 'sun protection'], None),
    ('first_aid_kit', 'Personal first aid kit', 'always',
     ['first aid', 'first aid kit', 'medkit'], None),
    ('map_or_gps', 'Map or GPS device', 'always',
     ['map', 'gps', 'compass'], 6.0),
    ('rain_jacket', 'Waterproof jacket', 'rain',
     ['rain jacket', 'raincoat', 'waterproof', 'waterproof jacket', 'shell'],
     6.0),
    ('warm_layer', 'Warm fleece or down layer', 'cold',
     ['fleece', 'warm layer', 'down jacket', 'sweater', 'jumper'], 5.0),
    ('sun_hat', 'Sun hat', 'hot', ['hat', 'cap', 'sun hat'], None),
    ('trekking_poles', 'Trekking poles', 'joint_issues',
     ['poles', 'trekking poles', 'hiking poles', 'sticks'], 4.0),
    ('helmet', 'Climbing helmet', 'rockfall',
     ['helmet', 'climbing helmet'], 5.0),
    ('headlamp', 'Headlamp', 'long_day',
     ['headlamp', 'head torch', 'torch', 'flashlight'], 3.0),
)

# (name, max party size, ISO weekdays off).
_GUIDE_ROWS = (('Lucia Prieto', 6, [1, 2]),)

# Units owned per rentable item slug.
_STOCK_ROWS = {
    'hiking_boots': 5,
    'backpack': 3,
    'map_or_gps': 3,
    'rain_jacket': 4,
    'warm_layer': 4,
    'trekking_poles': 4,
    'helmet': 2,
    'headlamp': 6,
}


def upgrade() -> None:
    """Upgrade schema."""
    op.bulk_insert(
        _TRAILS,
        [
            {
                'code': code,
                'name': name,
                'trail_type': (
                    'high_mountain' if difficulty == 'hard'
                    else 'short_distance'
                ),
                'length_km': length_km,
                'ascent_m': ascent_m,
                'duration_h': duration_h,
                'difficulty': difficulty,
                'source_url': _SOURCE_URL,
                'massif': massif,
                'start_point': start_point,
                'route_type': route_type,
                'rockfall_risk': rockfall_risk,
                'highlights': highlights,
                **_EMPTY_TEXT,
            }
            for (
                code, name, massif, start_point, length_km, ascent_m,
                duration_h, difficulty, route_type, highlights, rockfall_risk,
            ) in _TRAIL_ROWS
        ],
    )
    op.bulk_insert(
        _EQUIPMENT_ITEMS,
        [
            {
                'slug': slug,
                'name': name,
                'required_when': required_when,
                'aliases': aliases,
                'rentable': price is not None,
                'rental_price_eur': price,
            }
            for slug, name, required_when, aliases, price in _EQUIPMENT_ROWS
        ],
    )
    op.bulk_insert(
        _GUIDES,
        [
            {
                'full_name': name,
                'max_party_size': max_party_size,
                'unavailable_weekdays': weekdays,
            }
            for name, max_party_size, weekdays in _GUIDE_ROWS
        ],
    )
    for slug, units in _STOCK_ROWS.items():
        op.execute(
            _RENTAL_STOCK.insert().from_select(
                ['equipment_item_id', 'units_total'],
                sa.select(
                    _EQUIPMENT_ITEMS.c.id, sa.literal(units, sa.Integer)
                ).where(_EQUIPMENT_ITEMS.c.slug == slug),
            )
        )


def downgrade() -> None:
    """Downgrade schema."""
    # Deleting the items also deletes their stock (ON DELETE CASCADE).
    op.execute(
        _EQUIPMENT_ITEMS.delete().where(
            _EQUIPMENT_ITEMS.c.slug.in_([row[0] for row in _EQUIPMENT_ROWS])
        )
    )
    op.execute(
        _GUIDES.delete().where(
            _GUIDES.c.full_name.in_([row[0] for row in _GUIDE_ROWS])
        )
    )
    op.execute(
        _TRAILS.delete().where(
            _TRAILS.c.code.in_([row[0] for row in _TRAIL_ROWS])
        )
    )
