"""Mute of user A/B."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
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
    async_add_entities(A16MuteSwitch(entry.runtime_data, user) for user in USERS)


class A16MuteSwitch(A16Entity, SwitchEntity):
    """On = muted.

    The A16 reports the mute state only in the answer to the toggle command,
    so it is unknown until it was switched once (or toggled on the remote
    while the integration is connected).
    """

    def __init__(self, coordinator, user: str) -> None:
        super().__init__(coordinator, f"mute_{user}")
        self._user = user
        self._attr_translation_key = f"mute_{user}"

    @property
    def is_on(self) -> bool | None:
        return self.state_data.user(self._user).muted

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.async_set_mute(self._user, True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.async_set_mute(self._user, False)
