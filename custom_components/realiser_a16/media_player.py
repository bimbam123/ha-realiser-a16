"""Media player for user A of the Realiser A16."""

from __future__ import annotations

from typing import Any

from homeassistant.components.media_player import (
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import A16ConfigEntry
from .const import DOMAIN, SOURCE_NAMES
from .entity import A16Entity
from .pya16.protocol import VOLUME_MAX, VOLUME_MIN

PARALLEL_UPDATES = 0

_VOLUME_RANGE = VOLUME_MAX - VOLUME_MIN
_SOURCE_BY_NAME = {name: value for value, name in SOURCE_NAMES.items()}


def volume_to_level(volume: int) -> float:
    return (volume - VOLUME_MIN) / _VOLUME_RANGE


def level_to_volume(level: float) -> int:
    return round(VOLUME_MIN + max(0.0, min(1.0, level)) * _VOLUME_RANGE)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: A16ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities([A16UserAPlayer(entry.runtime_data)])


class A16UserAPlayer(A16Entity, MediaPlayerEntity):
    """Power, volume, mute and source for user A."""

    _attr_translation_key = "user_a"
    _attr_device_class = MediaPlayerDeviceClass.RECEIVER
    _attr_supported_features = (
        MediaPlayerEntityFeature.TURN_ON
        | MediaPlayerEntityFeature.TURN_OFF
        | MediaPlayerEntityFeature.VOLUME_SET
        | MediaPlayerEntityFeature.VOLUME_STEP
        | MediaPlayerEntityFeature.VOLUME_MUTE
        | MediaPlayerEntityFeature.SELECT_SOURCE
    )
    _attr_source_list = list(SOURCE_NAMES.values())
    _attr_volume_step = 1 / _VOLUME_RANGE

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "user_a_player")

    @property
    def state(self) -> MediaPlayerState | None:
        power = self.state_data.power
        if power in ("ON", "BOOT"):
            # BOOT (~65 s after power on) is shown as on; see power_state.
            return MediaPlayerState.ON
        if power == "STANDBY":
            return MediaPlayerState.OFF
        return None

    @property
    def volume_level(self) -> float | None:
        volume = self.state_data.user_a.volume
        return None if volume is None else volume_to_level(volume)

    @property
    def is_volume_muted(self) -> bool | None:
        return self.state_data.user_a.muted

    @property
    def source(self) -> str | None:
        value = self.state_data.source
        return SOURCE_NAMES.get(value, value) if value else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        s = self.state_data
        return {
            "power_state": s.power.lower() if s.power else None,
            "volume_raw": s.user_a.volume,
            "preset": s.user_a.preset,
            "room": s.user_a.room,
            "subject": s.user_a.subject,
            "layout": s.user_a.layout,
        }

    async def async_turn_on(self) -> None:
        if self.state_data.power in ("ON", "BOOT"):
            return
        await self.coordinator.async_command(self.coordinator.client.power_on())

    async def async_turn_off(self) -> None:
        await self.coordinator.async_command(self.coordinator.client.standby())

    async def async_set_volume_level(self, volume: float) -> None:
        await self.coordinator.async_set_volume("a", level_to_volume(volume))

    async def async_volume_up(self) -> None:
        await self.coordinator.async_volume_step("a", up=True)

    async def async_volume_down(self) -> None:
        await self.coordinator.async_volume_step("a", up=False)

    async def async_mute_volume(self, mute: bool) -> None:
        await self.coordinator.async_set_mute("a", mute)

    async def async_select_source(self, source: str) -> None:
        value = _SOURCE_BY_NAME.get(source)
        if value is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="invalid_source",
                translation_placeholders={"source": source},
            )
        await self.coordinator.async_command(
            self.coordinator.client.select_source(value)
        )
