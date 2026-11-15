"""Binary sensors of the Realiser A16: tactile output per user."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import A16ConfigEntry
from .const import USERS
from .entity import A16Entity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: A16ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities(A16TactileSensor(entry.runtime_data, user) for user in USERS)


class A16TactileSensor(A16Entity, BinarySensorEntity):
    """Tactile output (ATACT/BTACT) of the active preset."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator, user: str) -> None:
        super().__init__(coordinator, f"tactile_{user}")
        self._user = user
        self._attr_translation_key = f"tactile_{user}"

    @property
    def is_on(self) -> bool | None:
        return self.state_data.user(self._user).tactile
