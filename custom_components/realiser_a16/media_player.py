"""Media player "Realiser A16": power and source of the whole device.

Volume and mute per user are number and switch entities: a media player can
only show the volume in percent, while everyone knows the A16 values 27-99.
"""

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

PARALLEL_UPDATES = 0

_SOURCE_BY_NAME = {name: value for value, name in SOURCE_NAMES.items()}


def power_state(power: str | None) -> MediaPlayerState | None:
    if power in ("ON", "BOOT"):
        # BOOT (~65 s after power on) is shown as on; see power_state attribute.
        return MediaPlayerState.ON
    if power == "STANDBY":
        return MediaPlayerState.OFF
    return None


async def async_setup_entry(
    hass: HomeAssistant,
    entry: A16ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities([A16DevicePlayer(entry.runtime_data)])


class A16DevicePlayer(A16Entity, MediaPlayerEntity):
    """Power and source of the whole device."""

    _attr_name = None  # the device name ("Realiser A16")
    _attr_device_class = MediaPlayerDeviceClass.RECEIVER
    _attr_supported_features = (
        MediaPlayerEntityFeature.TURN_ON
        | MediaPlayerEntityFeature.TURN_OFF
        | MediaPlayerEntityFeature.SELECT_SOURCE
    )
    _attr_source_list = list(SOURCE_NAMES.values())

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "device_player")

    @property
    def state(self) -> MediaPlayerState | None:
        return power_state(self.state_data.power)

    @property
    def source(self) -> str | None:
        value = self.state_data.source
        return SOURCE_NAMES.get(value, value) if value else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        s = self.state_data
        return {
            "power_state": s.power.lower() if s.power else None,
            "user_mode": s.user_mode,
            "decoder": s.decoder,
            "upmixer": s.upmixer,
        }

    async def async_turn_on(self) -> None:
        if self.state_data.power in ("ON", "BOOT"):
            return
        await self.coordinator.async_command(self.coordinator.client.power_on())

    async def async_turn_off(self) -> None:
        await self.coordinator.async_command(self.coordinator.client.standby())

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
