"""Results the agent tools return to the LLM."""

import datetime

import pydantic

from trip_planner.app.core.schemas import trip


class ToolError(pydantic.BaseModel):
    """A failure the LLM can read and react to."""

    error: str
    retryable: bool = False


class TrailSummary(pydantic.BaseModel):
    """A ranked trail as the LLM sees it."""

    rank: int
    trail_id: str
    name: str
    distance_km: float
    elevation_gain_m: int
    duration_h: float
    difficulty: str
    highlights: list[str]
    rockfall_risk: bool
    fit_reasons: list[str]


class TrailSearchResult(pydantic.BaseModel):
    """Trails that fit the limits, best first."""

    trails: list[TrailSummary]
    excluded_count: int


class ForecastResult(pydantic.BaseModel):
    """Daily forecast with the dates ranked for hiking."""

    days: list[trip.DailyForecast]
    best_dates: list[datetime.date]


class EquipmentCheckResult(pydantic.BaseModel):
    """Gear the trip requires, split by what the customer must do."""

    required: list[str]
    already_owned: list[str]
    missing_rentable: list[str]
    missing_to_buy: list[str]
    unrecognized_owned: list[str]
    reasons: dict[str, str]


class TrailStatus(pydantic.BaseModel):
    """Whether a trail is open."""

    trail_id: str
    status: str
    reason: str = ''
    name: str = ''
    difficulty: str = ''
    rockfall_risk: bool | None = None


class TrailStatusResult(pydantic.BaseModel):
    """Status of each asked trail."""

    trails: list[TrailStatus]


class DateAvailability(pydantic.BaseModel):
    """Guides free on one date."""

    date: datetime.date
    weekday: str
    available_guides: list[str]


class GuideAvailabilityResult(pydantic.BaseModel):
    """Guide availability of each asked date."""

    dates: list[DateAvailability]


class RentalStockResult(pydantic.BaseModel):
    """Units in stock of each asked item."""

    in_stock: dict[str, int]
    unknown_items: list[str]


class BookingResult(pydantic.BaseModel):
    """A confirmed booking."""

    booking: trip.Booking
    already_existed: bool


class RentalReservationResult(pydantic.BaseModel):
    """Gear reserved for a booking and gear that could not be."""

    reservation: trip.RentalReservation
    unavailable_items: list[str]


class MessageResult(pydantic.BaseModel):
    """Delivery receipt of a message."""

    delivered_to: str
    delivery_tick: int


class FinalPlanResult(pydantic.BaseModel):
    """Receipt of the plan handed to the customer."""

    delivered_to: str
    outcome_key: str
