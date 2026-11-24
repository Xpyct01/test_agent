"""Hiking gear: categories, required items, products and rental stock."""

import decimal
import enum

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import sqlmodel

from trip_planner.app.core.sql_models import base


class RequiredWhen(enum.StrEnum):
    """Condition of a trip that makes an equipment item required."""

    ALWAYS = 'always'
    RAIN = 'rain'
    COLD = 'cold'
    HOT = 'hot'
    MODERATE_OR_HARDER = 'moderate_or_harder'
    JOINT_ISSUES = 'joint_issues'
    ROCKFALL = 'rockfall'
    LONG_DAY = 'long_day'


class GearCategory(sqlmodel.SQLModel, table=True):
    """A group of gear, e.g. `Layering System` or `First Aid Equipment`.

    Attributes:
        id: Surrogate key.
        name: Category name, as on the gear list.
    """

    __tablename__ = 'gear_categories'

    id: int | None = sqlmodel.Field(default=None, primary_key=True)
    name: str = sqlmodel.Field(max_length=64, unique=True)


class EquipmentItem(base.TimestampMixin, table=True):
    """A kind of gear the equipment check asks a customer about.

    Attributes:
        id: Surrogate key.
        slug: Stable id the agents use, e.g. `hiking_boots`.
        name: Display name.
        category_id: Category of the item; None when uncategorized.
        required_when: Trip condition that makes the item required.
        aliases: Words a customer may use for the item.
        rentable: Whether the company rents the item out.
        rental_price_eur: Price of renting one unit for one day.
    """

    __tablename__ = 'equipment_items'
    __table_args__ = (
        sa.CheckConstraint(
            'NOT rentable OR rental_price_eur IS NOT NULL',
            name='rentable_has_price',
        ),
        sa.CheckConstraint(
            'rental_price_eur >= 0', name='rental_price_non_negative'
        ),
    )

    id: int | None = sqlmodel.Field(default=None, primary_key=True)
    slug: str = sqlmodel.Field(max_length=64, unique=True)
    name: str = sqlmodel.Field(max_length=128)
    category_id: int | None = sqlmodel.Field(
        default=None, foreign_key='gear_categories.id', ondelete='SET NULL'
    )
    required_when: RequiredWhen = sqlmodel.Field(
        sa_type=base.pg_enum(RequiredWhen, 'equipment_required_when')
    )
    aliases: list[str] = sqlmodel.Field(
        default_factory=list,
        sa_type=postgresql.ARRAY(sa.Text),
        sa_column_kwargs={'server_default': '{}'},
    )
    rentable: bool = sqlmodel.Field(
        default=False, sa_column_kwargs={'server_default': sa.false()}
    )
    rental_price_eur: decimal.Decimal | None = sqlmodel.Field(
        default=None, max_digits=8, decimal_places=2
    )


class GearProduct(base.CreatedAtMixin, table=True):
    """A recommended product from the example hiking gear list.

    Attributes:
        id: Surrogate key.
        category_id: Category heading the product is listed under.
        equipment_item_id: Equipment item the product satisfies; None until
            it is mapped.
        item_type: Kind of item, as labelled on the list (e.g. `Pack liner`).
        product: Product name.
        is_swap_out: Whether the product replaces a core item in some
            conditions instead of being part of the core kit.
        reasons: Why the product was chosen, one entry per bullet.
        product_url: Product page.
        source_url: Gear list the product was read from.
    """

    __tablename__ = 'gear_products'
    __table_args__ = (
        sa.UniqueConstraint('category_id', 'item_type', 'product'),
    )

    id: int | None = sqlmodel.Field(default=None, primary_key=True)
    category_id: int = sqlmodel.Field(
        foreign_key='gear_categories.id', ondelete='RESTRICT', index=True
    )
    equipment_item_id: int | None = sqlmodel.Field(
        default=None,
        foreign_key='equipment_items.id',
        ondelete='SET NULL',
        index=True,
    )
    item_type: str = sqlmodel.Field(max_length=64)
    product: str = sqlmodel.Field(max_length=256)
    is_swap_out: bool = sqlmodel.Field(
        default=False, sa_column_kwargs={'server_default': sa.false()}
    )
    reasons: list[str] = sqlmodel.Field(
        default_factory=list,
        sa_type=postgresql.ARRAY(sa.Text),
        sa_column_kwargs={'server_default': '{}'},
    )
    product_url: str = sqlmodel.Field(max_length=512)
    source_url: str = sqlmodel.Field(max_length=512)


class RentalStock(base.TimestampMixin, table=True):
    """Units of a rentable item the company owns.

    Units free on a date are `units_total` minus the units in
    `booking_rentals` of the confirmed bookings on that date.

    Attributes:
        equipment_item_id: The rentable item.
        units_total: Units owned.
    """

    __tablename__ = 'rental_stock'
    __table_args__ = (
        sa.CheckConstraint('units_total >= 0', name='units_non_negative'),
    )

    equipment_item_id: int = sqlmodel.Field(
        primary_key=True, foreign_key='equipment_items.id', ondelete='CASCADE'
    )
    units_total: int
