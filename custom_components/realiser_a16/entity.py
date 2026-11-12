"""Base entity for the Realiser A16."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER, MODEL
from .coordinator import A16Coordinator


class A16Entity(CoordinatorEntity[A16Coordinator]):
    """Common device info and availability (= connected to the A16)."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: A16Coordinator, key: str) -> None:
        super().__init__(coordinator)
        serial = coordinator.config_entry.unique_id or coordinator.config_entry.entry_id
        self._attr_unique_id = f"{serial}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, serial)},
            manufacturer=MANUFACTURER,
            model=MODEL,
            serial_number=coordinator.config_entry.unique_id,
            sw_version=coordinator.data.firmware.a16,
            name=MODEL,
        )

    @property
    def available(self) -> bool:
        return super().available and self.coordinator.client.connected

    @property
    def state_data(self):
        return self.coordinator.client.state
