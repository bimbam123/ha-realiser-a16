"""Media players of the Realiser A16.

- "Realiser A16" (device): power and source, which apply to the whole device
- "User A" / "User B": volume and mute per user; on/off follows the device

The volume is mapped 1:1: the A16 value 64 is shown as 64 %, so Home
Assistant shows the same numbers as the A16 display (27-99). Values below 27
are raised to 27.
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
from .const import DOMAIN, SOURCE_NAMES, USERS
from .entity import A16Entity
from .pya16.protocol import VOLUME_MAX, VOLUME_MIN

PARALLEL_UPDATES = 0

_SOURCE_BY_NAME = {name: value for value, name in SOURCE_NAMES.items()}


def volume_to_level(volume: int) -> float:
    """A16 value -> HA volume level (1:1, 64 -> 0.64)."""
    return volume / 100


def level_to_volume(level: float) -> int:
    """HA volume level -> A16 value, limited to 27-99."""
    return max(VOLUME_MIN, min(VOLUME_MAX, round(level * 100)))


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
    coordinator = entry.runtime_data
    async_add_entities(
        [
            A16DevicePlayer(coordinator),
            *(A16UserPlayer(coordinator, user) for user in USERS),
        ]
    )


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


class A16UserPlayer(A16Entity, MediaPlayerEntity):
    """Volume and mute of one user. On/off follows the device."""

    _attr_device_class = MediaPlayerDeviceClass.SPEAKER
    _attr_supported_features = (
        MediaPlayerEntityFeature.VOLUME_SET
        | MediaPlayerEntityFeature.VOLUME_STEP
        | MediaPlayerEntityFeature.VOLUME_MUTE
    )
    _attr_volume_step = 0.01  # one A16 step

    def __init__(self, coordinator, user: str) -> None:
        # Same unique IDs (and entity IDs) as v0.2.0/v0.2.1.
        super().__init__(coordinator, f"user_{user}_player")
        self._user = user
        self._attr_translation_key = f"user_{user}"

    @property
    def _us(self):
        return self.state_data.user(self._user)

    @property
    def state(self) -> MediaPlayerState | None:
        return power_state(self.state_data.power)

    @property
    def volume_level(self) -> float | None:
        volume = self._us.volume
        return None if volume is None else volume_to_level(volume)

    @property
    def is_volume_muted(self) -> bool | None:
        return self._us.muted

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        us = self._us
        return {
            "volume_raw": us.volume,
            "preset": us.preset,
            "room": us.room,
            "subject": us.subject,
            "layout": us.layout,
            "user_name": us.name,
        }

    async def async_set_volume_level(self, volume: float) -> None:
        await self.coordinator.async_set_volume(self._user, level_to_volume(volume))

    async def async_volume_up(self) -> None:
        await self.coordinator.async_volume_step(self._user, up=True)

    async def async_volume_down(self) -> None:
        await self.coordinator.async_volume_step(self._user, up=False)

    async def async_mute_volume(self, mute: bool) -> None:
        await self.coordinator.async_set_mute(self._user, mute)
