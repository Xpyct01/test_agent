"""Domain schemas of trip planning: trails, weather, gear, bookings, plans."""

import datetime
from typing import Literal

import pydantic

Difficulty = Literal['easy', 'moderate', 'hard']
FitnessLevel = Literal['low', 'moderate', 'high']

DIFFICULTY_ORDER: dict[str, int] = {'easy': 0, 'moderate': 1, 'hard': 2}


class Trail(pydantic.BaseModel):
    """A hiking route of the Picos de Europa National Park."""

    trail_id: str
    name: str
    massif: str
    start_point: str
    distance_km: float
    elevation_gain_m: int
    duration_h: float
    difficulty: Difficulty
    route_type: Literal['circular', 'linear', 'out_and_back']
    highlights: list[str]
    rockfall_risk: bool
    source_url: str


class FitnessProfile(pydantic.BaseModel):
    """Limits a hiker can safely handle in one day."""

    max_distance_km: float
    max_elevation_gain_m: int
    max_difficulty: Difficulty
    needs_trekking_poles: bool
    has_joint_issues: bool
    notes: list[str]


class TrailOption(pydantic.BaseModel):
    """A trail that fits a fitness profile, with its fit score."""

    trail: Trail
    score: float
    reasons: list[str]


class DailyForecast(pydantic.BaseModel):
    """Weather of one day at the forecast point, with its hiking score."""

    date: datetime.date
    weather: str
    temperature_max_c: float
    temperature_min_c: float
    precipitation_probability: int
    precipitation_mm: float
    wind_speed_max_kmh: float
    hiking_score: float = 0.0


class EquipmentItem(pydantic.BaseModel):
    """A piece of hiking gear and the condition that makes it required."""

    item_id: str
    name: str
    aliases: list[str]
    required_when: Literal[
        'always',
        'rain',
        'cold',
        'hot',
        'moderate_or_harder',
        'joint_issues',
        'rockfall',
        'long_day',
    ]
    rentable: bool
    rental_price_eur: float = 0.0


class Guide(pydantic.BaseModel):
    """A mountain guide of the company and the days they do not work."""

    name: str
    unavailable_weekdays: list[str]
    max_party_size: int


class TrailClosure(pydantic.BaseModel):
    """A trail closed by the park administration."""

    trail_id: str
    reason: str


class Booking(pydantic.BaseModel):
    """A confirmed guided trip."""

    booking_id: str
    trail_id: str
    date: datetime.date
    start_time: str
    customer_name: str
    party_size: int
    guide_name: str


class RentalReservation(pydantic.BaseModel):
    """Gear reserved for a booking."""

    booking_id: str
    items: list[str]
    total_price_eur: float


class TripPlan(pydantic.BaseModel):
    """The final plan of a trip, handed to the customer."""

    booking_id: str = pydantic.Field(
        description='Booking id returned by the operations assistant.'
    )
    trail_id: str = pydantic.Field(description='Id of the booked trail.')
    trail_name: str = pydantic.Field(description='Name of the booked trail.')
    date: datetime.date = pydantic.Field(
        description='Trip date, YYYY-MM-DD.'
    )
    start_time: str = pydantic.Field(description='Meeting time, HH:MM.')
    guide_name: str = pydantic.Field(description='Name of the guide.')
    weather_summary: str = pydantic.Field(
        description='One sentence on the forecast for the trip date.'
    )
    gear_to_bring: list[str] = pydantic.Field(
        description='Required gear the customer already owns.'
    )
    gear_to_rent: list[str] = pydantic.Field(
        description='Gear item ids reserved for the customer to rent.'
    )
    gear_to_buy: list[str] = pydantic.Field(
        description='Required gear that is not rentable and must be bought.'
    )
    notes: list[str] = pydantic.Field(
        description='Safety notes and conditions set by the guide.'
    )

    def outcome_key(self) -> str:
        """Returns the fields that must match for two runs to agree."""
        rented = ','.join(sorted(self.gear_to_rent))
        return f'{self.trail_id}|{self.date.isoformat()}|{rented}'
