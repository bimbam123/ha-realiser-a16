"""The Smyth Realiser A16 integration (unofficial)."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import Event, HomeAssistant

from .coordinator import A16Coordinator
from .pya16 import A16Client

PLATFORMS: list[Platform] = [
    Platform.MEDIA_PLAYER,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
]

type A16ConfigEntry = ConfigEntry[A16Coordinator]


async def async_setup_entry(hass: HomeAssistant, entry: A16ConfigEntry) -> bool:
    """Set up a Realiser A16 from a config entry (one connection per device)."""
    port = entry.options.get(CONF_PORT, entry.data[CONF_PORT])
    client = A16Client(entry.data[CONF_HOST], port)
    coordinator = A16Coordinator(hass, entry, client)
    await coordinator.async_start()  # raises ConfigEntryNotReady
    entry.runtime_data = coordinator

    async def _on_stop(event: Event) -> None:
        await coordinator.async_stop()

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _on_stop)
    )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: A16ConfigEntry) -> bool:
    """Unload a config entry and close the connection."""
    if unloaded := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        await entry.runtime_data.async_stop()
    return unloaded
