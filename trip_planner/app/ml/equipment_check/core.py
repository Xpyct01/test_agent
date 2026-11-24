"""Works out the gear a trip requires and what the hiker still lacks."""

from collections.abc import Sequence

from trip_planner.app.core.repositories.postgres import (
    equipment_item as equipment_item_lib,
)
from trip_planner.app.core.schemas import tools
from trip_planner.app.core.schemas import trip

_RAIN_PROBABILITY = 40
_RAIN_MM = 1.0
_COLD_MIN_C = 8.0
_HOT_MAX_C = 24.0
_LONG_DAY_H = 6.0


class EquipmentCheck:
    """Rule-based gear requirements from the trail, weather and health."""

    def __init__(
        self, equipment_repository: equipment_item_lib.EquipmentItemRepository
    ):
        """Initializes the checker.

        Args:
            equipment_repository: The gear catalogue.
        """
        self._equipment_repository = equipment_repository

    async def check(
        self,
        trail: trip.Trail,
        day: trip.DailyForecast | None,
        owned_items: Sequence[str],
        has_joint_issues: bool,
    ) -> tools.EquipmentCheckResult:
        """Returns the required gear split into owned, to rent and to buy.

        Args:
            trail: The trail of the trip.
            day: Forecast of the trip date; None skips weather rules.
            owned_items: Gear the hiker owns, in free text.
            has_joint_issues: Whether the hiker has a joint condition.

        Returns:
            The gear lists and why each item is required.
        """
        catalogue = await self._equipment_repository.list_all()
        active = self._active_conditions(trail, day, has_joint_issues)
        owned_ids, unrecognized = self._match_owned(catalogue, owned_items)
        required, owned, rentable, to_buy = [], [], [], []
        reasons = {}
        for item in catalogue:
            if item.required_when not in active:
                continue
            required.append(item.item_id)
            reasons[item.item_id] = active[item.required_when]
            if item.item_id in owned_ids:
                owned.append(item.item_id)
            elif item.rentable:
                rentable.append(item.item_id)
            else:
                to_buy.append(item.item_id)
        return tools.EquipmentCheckResult(
            required=required,
            already_owned=owned,
            missing_rentable=rentable,
            missing_to_buy=to_buy,
            unrecognized_owned=unrecognized,
            reasons=reasons,
        )

    def _active_conditions(
        self,
        trail: trip.Trail,
        day: trip.DailyForecast | None,
        has_joint_issues: bool,
    ) -> dict[str, str]:
        active = {'always': 'Required on every hike.'}
        if trail.difficulty != 'easy':
            active['moderate_or_harder'] = f'{trail.difficulty} trail.'
        if has_joint_issues:
            active['joint_issues'] = 'Joint condition: poles ease descents.'
        if trail.rockfall_risk:
            active['rockfall'] = 'Trail has rockfall risk.'
        if trail.duration_h >= _LONG_DAY_H:
            active['long_day'] = f'{trail.duration_h} h hike may end late.'
        if day is not None:
            if (
                day.precipitation_probability >= _RAIN_PROBABILITY
                or day.precipitation_mm >= _RAIN_MM
            ):
                active['rain'] = (
                    f'{day.precipitation_probability}% chance of rain.'
                )
            if day.temperature_min_c < _COLD_MIN_C:
                active['cold'] = f'Minimum {day.temperature_min_c} C.'
            if day.temperature_max_c >= _HOT_MAX_C:
                active['hot'] = f'Maximum {day.temperature_max_c} C.'
        return active

    def _match_owned(
        self,
        catalogue: Sequence[trip.EquipmentItem],
        owned_items: Sequence[str],
    ) -> tuple[set[str], list[str]]:
        matched, unrecognized = set(), []
        for owned in owned_items:
            text = owned.strip().lower().replace('_', ' ')
            item = next(
                (
                    i for i in catalogue
                    if text == i.item_id.replace('_', ' ')
                    or any(alias in text for alias in i.aliases)
                ),
                None,
            )
            if item is None:
                unrecognized.append(owned)
            else:
                matched.add(item.item_id)
        return matched, unrecognized
