"""Customers, their health and fitness, and the gear they own."""

import enum

import sqlalchemy as sa
import sqlmodel

from trip_planner.app.core.sql_models import base


class FitnessLevel(enum.StrEnum):
    """Self-reported fitness of a customer."""

    LOW = 'low'
    MODERATE = 'moderate'
    HIGH = 'high'


class Customer(base.TimestampMixin, table=True):
    """A customer of the company, served by their own assistant.

    Attributes:
        id: Surrogate key.
        full_name: Customer's name.
        email: Contact email; None when not given.
        age: Age in years; None when not given.
        fitness_level: Self-reported fitness; None until asked.
        health_notes: Health conditions that limit trails (injuries, ...).
    """

    __tablename__ = 'customers'
    __table_args__ = (
        sa.CheckConstraint('age > 0 AND age < 120', name='age_range'),
    )

    id: int | None = sqlmodel.Field(default=None, primary_key=True)
    full_name: str = sqlmodel.Field(max_length=128)
    email: str | None = sqlmodel.Field(
        default=None, max_length=320, unique=True
    )
    age: int | None = None
    fitness_level: FitnessLevel | None = sqlmodel.Field(
        default=None, sa_type=base.pg_enum(FitnessLevel, 'fitness_level')
    )
    health_notes: str | None = sqlmodel.Field(default=None, sa_type=sa.Text)


class CustomerGear(base.CreatedAtMixin, table=True):
    """An equipment item a customer already owns.

    Attributes:
        customer_id: The owner.
        equipment_item_id: The owned item.
    """

    __tablename__ = 'customer_gear'

    customer_id: int = sqlmodel.Field(
        primary_key=True, foreign_key='customers.id', ondelete='CASCADE'
    )
    equipment_item_id: int = sqlmodel.Field(
        primary_key=True, foreign_key='equipment_items.id', ondelete='CASCADE'
    )
