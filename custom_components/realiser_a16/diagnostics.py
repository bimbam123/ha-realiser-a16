"""Diagnostics download: connection statistics and the current device state."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from . import A16ConfigEntry

# Personal names and the serial number are not needed to analyse problems.
TO_REDACT = {
    "serial",
    "serial_number",
    "unique_id",
    "name",
    "room",
    "subject",
    "hpeq_file",
    "hpeq_subject",
    "title",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: A16ConfigEntry
) -> dict[str, Any]:
    coordinator = entry.runtime_data
    client = coordinator.client
    return {
        "entry": async_redact_data(
            {
                "title": entry.title,
                "data": dict(entry.data),
                "options": dict(entry.options),
            },
            TO_REDACT,
        ),
        "connection": {
            "connected": client.connected,
            "settings": {
                "response_timeout": client.response_timeout,
                "min_command_interval": client.min_command_interval,
                "min_step_interval": client.min_step_interval,
                "keepalive_interval": client.keepalive_interval,
            },
            "stats": client.stats.as_dict(),
        },
        "state": async_redact_data(client.state.as_dict(), TO_REDACT),
        "learned_preset_names": {
            user: sorted(names) for user, names in coordinator.preset_names.items()
        },
    }
