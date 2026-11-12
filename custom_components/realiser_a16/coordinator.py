"""Push coordinator: one A16Client (one TCP connection) per config entry."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady, HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import CONNECT_TIMEOUT, DOMAIN, RELEVANT_PATHS
from .pya16 import A16Client, A16Error, A16State, A16TimeoutError
from .pya16.protocol import MUTE_TOGGLE, VOLUME_MAX, VOLUME_MIN, User

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry

_LOGGER = logging.getLogger(__name__)

STORAGE_VERSION = 1
SAVE_DELAY = 10


class A16Coordinator(DataUpdateCoordinator[A16State]):
    """Feeds the pushed A16 state into Home Assistant (no polling)."""

    config_entry: ConfigEntry

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, client: A16Client
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN} {client.host}",
            update_interval=None,
        )
        self.client = client
        self.data = client.state
        # Learned preset names per user: {"a": {6: "Room / Subject"}}
        self.preset_names: dict[str, dict[int, str]] = {"a": {}, "b": {}}
        self._store: Store[dict[str, dict[str, str]]] = Store(
            hass, STORAGE_VERSION, f"{DOMAIN}.{entry.entry_id}.preset_names"
        )
        self._volume_target: dict[str, int] = {}
        self._volume_tasks: dict[str, asyncio.Task] = {}
        self._unsubs: list = []

    # --- lifecycle --------------------------------------------------------------

    async def async_start(self) -> None:
        """Load stored data, connect and wait for the first connection."""
        if stored := await self._store.async_load():
            for user, names in stored.items():
                self.preset_names[user] = {int(k): v for k, v in names.items()}
        self._unsubs.append(self.client.add_listener(self._on_state))
        self._unsubs.append(self.client.add_connection_listener(self._on_connection))
        await self.client.start()
        try:
            await self.client.wait_connected(CONNECT_TIMEOUT)
        except A16Error as err:
            await self.async_stop()
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN,
                translation_key="not_reachable",
                translation_placeholders={"host": self.client.host},
            ) from err

    async def async_stop(self) -> None:
        for task in self._volume_tasks.values():
            task.cancel()
        self._volume_tasks.clear()
        while self._unsubs:
            self._unsubs.pop()()
        await self.client.stop()

    async def async_shutdown(self) -> None:
        await super().async_shutdown()
        await self.async_stop()

    # --- client callbacks ---------------------------------------------------------

    @callback
    def _on_state(self, state: A16State, changed: set[str]) -> None:
        if {"user_a.preset", "user_a.room", "user_a.subject"} & changed:
            self._learn_preset_name("a", state)
        if "firmware.a16" in changed:
            self._update_device_firmware(state.firmware.a16)
        if changed & RELEVANT_PATHS:
            self.async_set_updated_data(state)

    @callback
    def _on_connection(self, connected: bool) -> None:
        # Entities read availability from client.connected.
        self.async_update_listeners()

    @callback
    def _learn_preset_name(self, user: str, state: A16State) -> None:
        us = state.user(user)
        if us.preset is None or not (us.room or us.subject):
            return
        name = " / ".join(p for p in (us.room, us.subject) if p)
        if self.preset_names[user].get(us.preset) != name:
            self.preset_names[user][us.preset] = name
            self._store.async_delay_save(self._store_data, SAVE_DELAY)

    def _store_data(self) -> dict[str, dict[str, str]]:
        return {
            user: {str(k): v for k, v in names.items()}
            for user, names in self.preset_names.items()
        }

    @callback
    def _update_device_firmware(self, firmware: str | None) -> None:
        registry = dr.async_get(self.hass)
        if device := registry.async_get_device_by_identifier(
            (DOMAIN, self.config_entry.unique_id or ""), self.config_entry.entry_id
        ):
            registry.async_update_device(device.id, sw_version=firmware)

    # --- actions ----------------------------------------------------------------

    async def async_command(self, coro) -> None:
        """Run a client call and turn library errors into HA errors."""
        try:
            await coro
        except A16Error as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="command_failed",
                translation_placeholders={"error": str(err)},
            ) from err

    async def async_set_volume(self, user: User, target: int) -> None:
        """Set the volume target; stepping runs in the background.

        The A16 has no absolute volume command and each step takes ~0.5-1.5 s,
        so the call returns immediately. A newer target replaces an older one
        (the latest target wins).
        """
        self._volume_target[user] = max(VOLUME_MIN, min(VOLUME_MAX, target))
        task = self._volume_tasks.get(user)
        if task is None or task.done():
            self._volume_tasks[user] = self.config_entry.async_create_background_task(
                self.hass, self._volume_worker(user), f"{DOMAIN} volume {user}"
            )

    async def async_volume_step(self, user: User, up: bool) -> None:
        """One volume step; cancels a running volume target."""
        self._cancel_volume_target(user)
        await self.async_command(
            self.client.volume_up(user) if up else self.client.volume_down(user)
        )

    def _cancel_volume_target(self, user: User) -> None:
        self._volume_target.pop(user, None)
        if (task := self._volume_tasks.pop(user, None)) is not None:
            task.cancel()

    async def _volume_worker(self, user: User) -> None:
        us = self.client.state.user(user)
        try:
            while (target := self._volume_target.get(user)) is not None:
                current = us.volume
                if current is None:
                    await self.client.send_command("83" if user == "a" else "a3")
                    current = us.volume
                    if current is None:
                        break
                if current == target:
                    break
                if await self.client.step_volume(user, up=target > current) is None:
                    _LOGGER.warning(
                        "Volume of user %s did not change (stays %s)", user, current
                    )
                    break
        except A16Error as err:
            _LOGGER.warning("Setting volume of user %s failed: %s", user, err)
        finally:
            self._volume_target.pop(user, None)

    async def _toggle_mute(self, user: User) -> None:
        """Toggle mute. Without an answer the state becomes unknown.

        There is no query command for the mute state, so after a lost answer
        it is unknown whether the toggle was applied.
        """
        try:
            await self.client.send_command(MUTE_TOGGLE[user])
        except A16TimeoutError as err:
            self.client.state.user(user).muted = None
            self.async_update_listeners()
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="command_failed",
                translation_placeholders={"error": str(err)},
            ) from err
        except A16Error as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="command_failed",
                translation_placeholders={"error": str(err)},
            ) from err

    async def async_set_mute(self, user: User, mute: bool) -> None:
        """Mute/unmute with state check.

        The A16 only reports the mute state in the answer to the toggle command
        (not in pushes). If the state is unknown, toggle once, check the
        answer and toggle again if it went the wrong way.
        """
        us = self.client.state.user(user)
        if us.muted is mute:
            return
        await self._toggle_mute(user)
        if us.muted is not mute:
            await self._toggle_mute(user)
        if us.muted is not mute:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="mute_failed"
            )
