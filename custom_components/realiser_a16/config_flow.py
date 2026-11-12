"""Config flow for the Smyth Realiser A16 integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT

from .api import A16ConnectionError, async_get_device_info
from .const import CONNECT_TIMEOUT, DEFAULT_PORT, DOMAIN, MAX_PORT, MIN_PORT

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): vol.All(
            vol.Coerce(int), vol.Range(min=MIN_PORT, max=MAX_PORT)
        ),
    }
)


class RealiserA16ConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for the Realiser A16."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for host and port and verify the connection."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                info = await async_get_device_info(
                    user_input[CONF_HOST], user_input[CONF_PORT], CONNECT_TIMEOUT
                )
            except A16ConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected error while connecting to the A16")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(info.serial)
                self._abort_if_unique_id_configured(updates=user_input)
                return self.async_create_entry(
                    title=f"Realiser A16 ({info.serial})", data=user_input
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, user_input
            ),
            errors=errors,
        )
