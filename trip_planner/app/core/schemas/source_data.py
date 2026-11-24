"""Rows of the source data CSV files (the columns of the DVC datasets).

`TrailRecord` matches `picos_trails/trails.csv` and `GearItemRecord` matches
`hiking_gear/gear_items.csv`, as written by the source data scraping
experiment. Length limits mirror the database columns.
"""

from typing import Annotated, Literal

import pydantic


def _empty_to_none(value: object) -> object:
    """Reads an empty CSV cell as a missing value."""
    if isinstance(value, str) and not value.strip():
        return None
    return value


_Optional = pydantic.BeforeValidator(_empty_to_none)
_Url = Annotated[str, pydantic.Field(max_length=512)]

TrailType = Literal['short_distance', 'long_distance', 'high_mountain']
TrailDifficulty = Literal['easy', 'moderate', 'hard', 'very_hard']


class TrailRecord(pydantic.BaseModel):
    """One itinerary of the park, as parsed from its page.

    The numbers are the first figure of each page field; they are None
    where the page gives none.
    """

    trail_code: str = pydantic.Field(min_length=1, max_length=16)
    name: str = pydantic.Field(min_length=1, max_length=128)
    section: str
    trail_type: TrailType
    length_km: Annotated[float | None, _Optional] = None
    ascent_m: Annotated[int | None, _Optional] = None
    descent_m: Annotated[int | None, _Optional] = None
    duration_h: Annotated[float | None, _Optional] = None
    difficulty: Annotated[TrailDifficulty | None, _Optional] = None
    length_text: str = ''
    elevation_text: str = ''
    duration_text: str = ''
    difficulty_text: str = ''
    description: str = ''
    how_to: str = ''
    points_of_interest: str = ''
    precautions_es: str = ''
    precautions_en: str = ''
    map_pdf_url: Annotated[_Url | None, _Optional] = None
    profile_pdf_url: Annotated[_Url | None, _Optional] = None
    source_url: _Url


class GearItemRecord(pydantic.BaseModel):
    """One product of the example hiking gear list.

    `reasons` holds the "why I chose it" bullets joined by ` | `.
    """

    category: str = pydantic.Field(min_length=1, max_length=64)
    item_type: str = pydantic.Field(min_length=1, max_length=64)
    product: str = pydantic.Field(min_length=1, max_length=256)
    is_swap_out: bool
    reasons: str = ''
    product_url: _Url
    source_url: _Url
