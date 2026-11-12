"""Preset select for user A of the Realiser A16."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import A16ConfigEntry
from .const import DOMAIN, USERS
from .entity import A16Entity
from .pya16.protocol import PRESET_MAX, PRESET_MIN

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: A16ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities(A16PresetSelect(entry.runtime_data, user) for user in USERS)


class A16PresetSelect(A16Entity, SelectEntity):
    """Preset 1-16. Names are learned when a preset is active.

    The A16 only reports room/subject of the active preset, so a preset shows
    its name only after it was active once (stored across restarts).
    """

    def __init__(self, coordinator, user: str) -> None:
        super().__init__(coordinator, f"preset_{user}")
        self._user = user
        self._attr_translation_key = f"preset_{user}"

    def _label(self, preset: int) -> str:
        name = self.coordinator.preset_names[self._user].get(preset)
        return f"{preset} – {name}" if name else str(preset)

    @property
    def options(self) -> list[str]:
        return [self._label(n) for n in range(PRESET_MIN, PRESET_MAX + 1)]

    @property
    def current_option(self) -> str | None:
        preset = self.state_data.user(self._user).preset
        return self._label(preset) if preset is not None else None

    async def async_select_option(self, option: str) -> None:
        try:
            preset = int(option.split(" ", 1)[0])
        except ValueError:
            preset = 0
        if not PRESET_MIN <= preset <= PRESET_MAX:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="invalid_preset",
                translation_placeholders={"option": option},
            )
        await self.coordinator.async_command(
            self.coordinator.client.select_preset(self._user, preset)
        )
