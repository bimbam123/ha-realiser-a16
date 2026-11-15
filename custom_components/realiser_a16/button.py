"""Buttons of the Realiser A16: head-tracker angle display (HT key)."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
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
    async_add_entities([A16HtDisplayButton(entry.runtime_data)])


class A16HtDisplayButton(A16Entity, ButtonEntity):
    """HT key: toggles the head-tracker angle display on the Speaker Map page.

    It does not switch head tracking itself. A button instead of a switch:
    the A16 pushes nothing when HT is pressed on the remote, so a state shown
    in Home Assistant would go stale. The toggle is never repeated blindly.
    """

    _attr_translation_key = "ht_display"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "ht_display")

    async def async_press(self) -> None:
        await self.coordinator.async_command(self.coordinator.client.press_key("ht"))
