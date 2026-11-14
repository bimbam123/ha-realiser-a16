"""Selects of the Realiser A16: source, rendering (SVS / AV or mixdown), presets."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import A16ConfigEntry
from .const import DOMAIN, SOURCE_NAMES, USERS
from .entity import A16Entity
from .pya16.protocol import PRESET_MAX, PRESET_MIN

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: A16ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        [
            A16SourceSelect(coordinator),
            A16RenderingSelect(coordinator),
            *(A16PresetSelect(coordinator, user) for user in USERS),
        ]
    )


_SOURCE_BY_NAME = {name: value for value, name in SOURCE_NAMES.items()}

RENDERING_SVS = "svs"
RENDERING_AV_MIX = "av_mix"
# MODE= value -> rendering option. The speaker key (5e) gives AV loudspeaker
# mode if AV mode is enabled in the active User A preset, otherwise stereo
# mixdown to the headphones (manual 9.2.6 and chapter 11). The sensor "Rendering
# mode" shows which one.
_RENDERING_BY_MODE = {
    "SVS": RENDERING_SVS,
    "AV": RENDERING_AV_MIX,
    "MIX": RENDERING_AV_MIX,
}


class A16SourceSelect(A16Entity, SelectEntity):
    """Audio source; same state as the source of the device media player."""

    _attr_translation_key = "source"
    _attr_options = list(SOURCE_NAMES.values())

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "source")

    @property
    def current_option(self) -> str | None:
        value = self.state_data.source
        return SOURCE_NAMES.get(value) if value else None

    async def async_select_option(self, option: str) -> None:
        value = _SOURCE_BY_NAME.get(option)
        if value is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="invalid_source",
                translation_placeholders={"source": option},
            )
        await self.coordinator.async_command(
            self.coordinator.client.select_source(value)
        )


class A16RenderingSelect(A16Entity, SelectEntity):
    """SVS headphone mode (4d) or the speaker key (5e): AV or stereo mixdown.

    The key stays "output" so existing entities keep their unique_id.
    """

    _attr_translation_key = "rendering"
    _attr_options = [RENDERING_SVS, RENDERING_AV_MIX]

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "output")

    @property
    def current_option(self) -> str | None:
        return _RENDERING_BY_MODE.get((self.state_data.mode or "").upper())

    async def async_select_option(self, option: str) -> None:
        await self.coordinator.async_command(
            self.coordinator.client.set_output(option == RENDERING_AV_MIX)
        )


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
