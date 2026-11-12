"""Sensors of the Realiser A16: mode, firmware, head tracking mode."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import A16ConfigEntry
from .entity import A16Entity
from .pya16 import A16State

PARALLEL_UPDATES = 0

MODES = ["svs", "av", "mix"]


@dataclass(frozen=True, kw_only=True)
class A16SensorDescription(SensorEntityDescription):
    value_fn: Callable[[A16State], str | None]


def _mode(state: A16State) -> str | None:
    mode = (state.mode or "").lower()
    return mode if mode in MODES else None


SENSORS: tuple[A16SensorDescription, ...] = (
    A16SensorDescription(
        key="mode",
        translation_key="mode",
        device_class=SensorDeviceClass.ENUM,
        options=MODES,
        value_fn=_mode,
    ),
    A16SensorDescription(
        key="ht_mode",
        translation_key="ht_mode",
        value_fn=lambda s: s.ht_mode,
    ),
    A16SensorDescription(
        key="firmware",
        translation_key="firmware",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda s: s.firmware.a16,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: A16ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities(A16Sensor(entry.runtime_data, d) for d in SENSORS)


class A16Sensor(A16Entity, SensorEntity):
    entity_description: A16SensorDescription

    def __init__(self, coordinator, description: A16SensorDescription) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> str | None:
        return self.entity_description.value_fn(self.state_data)
