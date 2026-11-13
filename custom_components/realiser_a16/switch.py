"""Switches of the Realiser A16: test signal and head tracking."""

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
    async_add_entities(
        [A16TestSignalSwitch(coordinator), A16HeadTrackingSwitch(coordinator)]
    )


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


class A16HeadTrackingSwitch(A16Entity, SwitchEntity):
    """Head tracking (HT key).

    The A16 has no query for it: the state is only known from the answer to
    the last toggle (or a key press on the remote) and unknown after start.
    """

    _attr_translation_key = "head_tracking"
    _attr_assumed_state = True

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "head_tracking")

    @property
    def is_on(self) -> bool | None:
        ht = self.state_data.head_tracking
        return None if ht is None else ht == "ACTIVE"

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.async_command(
            self.coordinator.client.set_head_tracking(True)
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.async_command(
            self.coordinator.client.set_head_tracking(False)
        )
