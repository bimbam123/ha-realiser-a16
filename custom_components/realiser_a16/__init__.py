"""The Smyth Realiser A16 integration (unofficial)."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import Event, HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN
from .coordinator import A16Coordinator
from .pya16 import A16Client

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.MEDIA_PLAYER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]

type A16ConfigEntry = ConfigEntry[A16Coordinator]


async def async_setup_entry(hass: HomeAssistant, entry: A16ConfigEntry) -> bool:
    """Set up a Realiser A16 from a config entry (one connection per device)."""
    port = entry.options.get(CONF_PORT, entry.data[CONF_PORT])
    client = A16Client(entry.data[CONF_HOST], port)
    coordinator = A16Coordinator(hass, entry, client)
    _remove_old_volume_numbers(hass, entry)
    await coordinator.async_start()  # raises ConfigEntryNotReady
    entry.runtime_data = coordinator

    async def _on_stop(event: Event) -> None:
        await coordinator.async_stop()

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _on_stop)
    )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


def _remove_old_volume_numbers(hass: HomeAssistant, entry: A16ConfigEntry) -> None:
    """v0.2.1 had number entities "Volume A/B" next to the user players.

    Since v0.2.2 the user players show the A16 value themselves (64 = 64 %),
    so the numbers were duplicates and are removed.
    """
    registry = er.async_get(hass)
    serial = entry.unique_id or entry.entry_id
    for user in ("a", "b"):
        if entity_id := registry.async_get_entity_id(
            "number", DOMAIN, f"{serial}_volume_{user}"
        ):
            registry.async_remove(entity_id)


async def async_unload_entry(hass: HomeAssistant, entry: A16ConfigEntry) -> bool:
    """Unload a config entry and close the connection."""
    if unloaded := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        await entry.runtime_data.async_stop()
    return unloaded
