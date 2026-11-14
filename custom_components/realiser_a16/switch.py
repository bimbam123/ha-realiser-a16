"""Switches of the Realiser A16: test signal."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import A16ConfigEntry
from .entity import A16Entity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: A16ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities([A16TestSignalSwitch(coordinator)])


class A16TestSignalSwitch(A16Entity, SwitchEntity):
    """Internal test loop (TEST key). The state is queried with ``af``."""

    _attr_translation_key = "test_signal"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "test_signal")

    @property
    def is_on(self) -> bool | None:
        test = self.state_data.test
        return None if test is None else test == "LOOP"

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.async_command(
            self.coordinator.client.set_test_signal(True)
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.async_command(
            self.coordinator.client.set_test_signal(False)
        )
