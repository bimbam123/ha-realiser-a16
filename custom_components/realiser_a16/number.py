"""Volume of user A/B as the value shown on the A16 (27-99)."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import A16ConfigEntry
from .const import USERS
from .entity import A16Entity
from .pya16.protocol import VOLUME_MAX, VOLUME_MIN

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: A16ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities(A16VolumeNumber(entry.runtime_data, user) for user in USERS)


class A16VolumeNumber(A16Entity, NumberEntity):
    """The media player shows volume in %; this shows the A16 value.

    Setting a value starts the background stepping (latest target wins), so
    the state follows the device step by step.
    """

    _attr_native_min_value = VOLUME_MIN
    _attr_native_max_value = VOLUME_MAX
    _attr_native_step = 1
    _attr_mode = NumberMode.SLIDER

    def __init__(self, coordinator, user: str) -> None:
        super().__init__(coordinator, f"volume_{user}")
        self._user = user
        self._attr_translation_key = f"volume_{user}"

    @property
    def native_value(self) -> int | None:
        return self.state_data.user(self._user).volume

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.async_set_volume(self._user, round(value))
