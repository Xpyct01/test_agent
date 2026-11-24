"""Trails of the Picos de Europa National Park and their closures."""

import datetime
import enum

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import sqlmodel

from trip_planner.app.core.sql_models import base


class TrailType(enum.StrEnum):
    """Section of the park's itinerary list a trail is published under."""

    SHORT_DISTANCE = 'short_distance'  # Senderos de pequeño recorrido (PR).
    LONG_DISTANCE = 'long_distance'  # Senderos de gran recorrido (GR).
    HIGH_MOUNTAIN = 'high_mountain'  # Rutas de alta montaña.


class TrailDifficulty(enum.StrEnum):
    """Difficulty level, normalized from the park's Spanish wording."""

    EASY = 'easy'
    MODERATE = 'moderate'
    HARD = 'hard'
    VERY_HARD = 'very_hard'


class RouteType(enum.StrEnum):
    """Shape of a route."""

    CIRCULAR = 'circular'
    LINEAR = 'linear'
    OUT_AND_BACK = 'out_and_back'


class Trail(base.TimestampMixin, table=True):
    """A hiking route, as published on the park's itinerary pages.

    The parsed numbers keep the first figure of each page field (the main
    variant); the `*_text` columns keep the published wording for routes with
    several variants. The last group of columns is curated by the company and
    is not on the park's pages.

    Attributes:
        id: Surrogate key.
        code: Park code of the route, e.g. `PR-PNPE 2`.
        name: Route name.
        trail_type: Itinerary section the route is listed under.
        length_km: Length of the main variant.
        ascent_m: Total ascent; None when the page gives none.
        descent_m: Total descent; None when the page gives none.
        duration_h: Walking time of the main variant.
        difficulty: Normalized difficulty.
        length_text: Published length field.
        elevation_text: Published elevation field.
        duration_text: Published duration field.
        difficulty_text: Published difficulty field.
        description: Route description (Spanish).
        how_to: How to walk the route (Spanish).
        points_of_interest: Sights along the route (Spanish).
        precautions_es: Safety notes in Spanish.
        precautions_en: Safety notes in English.
        map_pdf_url: Route map PDF.
        profile_pdf_url: Elevation profile PDF.
        source_url: Page the route was read from.
        massif: Massif the route is in (Western, Central or Eastern).
        start_point: Where the route starts.
        route_type: Shape of the route.
        rockfall_risk: Whether a helmet is required.
        highlights: Tags matched against customer wishes (lakes, gorge, ...).
    """

    __tablename__ = 'trails'
    __table_args__ = (
        sa.CheckConstraint('length_km > 0', name='length_positive'),
        sa.CheckConstraint('duration_h > 0', name='duration_positive'),
        sa.CheckConstraint('ascent_m >= 0', name='ascent_non_negative'),
        sa.CheckConstraint('descent_m >= 0', name='descent_non_negative'),
    )

    id: int | None = sqlmodel.Field(default=None, primary_key=True)
    code: str = sqlmodel.Field(max_length=16, unique=True)
    name: str = sqlmodel.Field(max_length=128)
    trail_type: TrailType = sqlmodel.Field(
        sa_type=base.pg_enum(TrailType, 'trail_type')
    )
    length_km: float
    ascent_m: int | None = None
    descent_m: int | None = None
    duration_h: float
    difficulty: TrailDifficulty = sqlmodel.Field(
        sa_type=base.pg_enum(TrailDifficulty, 'trail_difficulty'), index=True
    )
    length_text: str = sqlmodel.Field(default='', sa_type=sa.Text)
    elevation_text: str = sqlmodel.Field(default='', sa_type=sa.Text)
    duration_text: str = sqlmodel.Field(default='', sa_type=sa.Text)
    difficulty_text: str = sqlmodel.Field(default='', sa_type=sa.Text)
    description: str = sqlmodel.Field(default='', sa_type=sa.Text)
    how_to: str = sqlmodel.Field(default='', sa_type=sa.Text)
    points_of_interest: str = sqlmodel.Field(default='', sa_type=sa.Text)
    precautions_es: str = sqlmodel.Field(default='', sa_type=sa.Text)
    precautions_en: str = sqlmodel.Field(default='', sa_type=sa.Text)
    map_pdf_url: str | None = sqlmodel.Field(default=None, max_length=512)
    profile_pdf_url: str | None = sqlmodel.Field(default=None, max_length=512)
    source_url: str = sqlmodel.Field(max_length=512)
    massif: str | None = sqlmodel.Field(default=None, max_length=64)
    start_point: str | None = sqlmodel.Field(default=None, max_length=128)
    route_type: RouteType | None = sqlmodel.Field(
        default=None, sa_type=base.pg_enum(RouteType, 'route_type')
    )
    rockfall_risk: bool = sqlmodel.Field(
        default=False, sa_column_kwargs={'server_default': sa.false()}
    )
    highlights: list[str] = sqlmodel.Field(
        default_factory=list,
        sa_type=postgresql.ARRAY(sa.Text),
        sa_column_kwargs={'server_default': '{}'},
    )


class TrailClosure(base.CreatedAtMixin, table=True):
    """A period during which the park administration closes a trail.

    Attributes:
        id: Surrogate key.
        trail_id: The closed trail.
        reason: Why the trail is closed.
        starts_on: First closed day.
        ends_on: Last closed day; None while the end is not announced.
    """

    __tablename__ = 'trail_closures'
    __table_args__ = (
        sa.CheckConstraint(
            'ends_on IS NULL OR ends_on >= starts_on', name='period_ordered'
        ),
        sa.Index(
            'ix_trail_closures_trail_id_starts_on', 'trail_id', 'starts_on'
        ),
    )

    id: int | None = sqlmodel.Field(default=None, primary_key=True)
    trail_id: int = sqlmodel.Field(foreign_key='trails.id', ondelete='CASCADE')
    reason: str = sqlmodel.Field(sa_type=sa.Text)
    starts_on: datetime.date
    ends_on: datetime.date | None = None
