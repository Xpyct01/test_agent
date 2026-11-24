"""Converts source data CSV rows into rows of the database tables."""

from trip_planner.app.core.schemas import source_data
from trip_planner.app.core.sql_models import equipment
from trip_planner.app.core.sql_models import trail

_REASON_SEPARATOR = ' | '


def missing_trail_fields(record: source_data.TrailRecord) -> list[str]:
    """Returns the fields the `trails` table requires that the row lacks."""
    required = {
        'length_km': record.length_km,
        'duration_h': record.duration_h,
        'difficulty': record.difficulty,
    }
    return [name for name, value in required.items() if value is None]


def to_trail_row(record: source_data.TrailRecord) -> trail.Trail:
    """Returns the `trails` row of a park itinerary.

    The curated columns (massif, route type, highlights, ...) are not in the
    file and stay at their defaults.

    Args:
        record: A row without missing required fields (see
            `missing_trail_fields`).
    """
    return trail.Trail(
        code=record.trail_code,
        name=record.name,
        trail_type=trail.TrailType(record.trail_type),
        length_km=record.length_km,
        ascent_m=record.ascent_m,
        descent_m=record.descent_m,
        duration_h=record.duration_h,
        difficulty=trail.TrailDifficulty(record.difficulty),
        length_text=record.length_text,
        elevation_text=record.elevation_text,
        duration_text=record.duration_text,
        difficulty_text=record.difficulty_text,
        description=record.description,
        how_to=record.how_to,
        points_of_interest=record.points_of_interest,
        precautions_es=record.precautions_es,
        precautions_en=record.precautions_en,
        map_pdf_url=record.map_pdf_url,
        profile_pdf_url=record.profile_pdf_url,
        source_url=record.source_url,
    )


def to_gear_category_row(name: str) -> equipment.GearCategory:
    """Returns the `gear_categories` row of a category name."""
    return equipment.GearCategory(name=name)


def to_gear_product_row(
    record: source_data.GearItemRecord, category_id: int
) -> equipment.GearProduct:
    """Returns the `gear_products` row of a gear list item.

    Args:
        record: A row of the gear file.
        category_id: Database id of the row's category.
    """
    reasons = [
        reason.strip()
        for reason in record.reasons.split(_REASON_SEPARATOR)
        if reason.strip()
    ]
    return equipment.GearProduct(
        category_id=category_id,
        item_type=record.item_type,
        product=record.product,
        is_swap_out=record.is_swap_out,
        reasons=reasons,
        product_url=record.product_url,
        source_url=record.source_url,
    )
