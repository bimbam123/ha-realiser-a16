"""Config flow for the Smyth Realiser A16 integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT

from .api import A16ConnectionError, A16DeviceInfo, async_get_device_info
from .const import CONNECT_TIMEOUT, DEFAULT_PORT, DOMAIN, MAX_PORT, MIN_PORT

_LOGGER = logging.getLogger(__name__)

PORT_VALIDATOR = vol.All(vol.Coerce(int), vol.Range(min=MIN_PORT, max=MAX_PORT))

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): PORT_VALIDATOR,
    }
)


class RealiserA16ConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for the Realiser A16."""

    VERSION = 1

    async def _async_test(
        self, user_input: dict[str, Any], errors: dict[str, str]
    ) -> A16DeviceInfo | None:
        try:
            return await async_get_device_info(
                user_input[CONF_HOST], user_input[CONF_PORT], CONNECT_TIMEOUT
            )
        except A16ConnectionError:
            errors["base"] = "cannot_connect"
        except Exception:
            _LOGGER.exception("Unexpected error while connecting to the A16")
            errors["base"] = "unknown"
        return None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for host and port and verify the connection."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Abort before connecting: the A16 accepts only one client, so a
            # test connection to an already configured device would fail.
            self._async_abort_entries_match({CONF_HOST: user_input[CONF_HOST]})
            if info := await self._async_test(user_input, errors):
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

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Change host and/or port of an existing entry.

        A new host is tested and must answer with the same serial number. A
        port-only change is not tested: the running integration holds the only
        connection the A16 accepts. A wrong port makes the entry retry setup.
        """
        entry = self._get_reconfigure_entry()
        current = {
            CONF_HOST: entry.data[CONF_HOST],
            # v0.2.0 stored a changed port in the options
            CONF_PORT: entry.options.get(CONF_PORT, entry.data[CONF_PORT]),
        }
        errors: dict[str, str] = {}

        if user_input is not None:
            if user_input[CONF_HOST] != current[CONF_HOST]:
                if info := await self._async_test(user_input, errors):
                    await self.async_set_unique_id(info.serial)
                    self._abort_if_unique_id_mismatch(reason="wrong_device")
            if not errors:
                return self.async_update_reload_and_abort(
                    entry, data_updates=user_input, options={}
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, user_input or current
            ),
            errors=errors,
        )
