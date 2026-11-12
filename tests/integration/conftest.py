"""Fixtures for the Home Assistant integration tests.

These tests need pytest-homeassistant-custom-component, which only runs on
Linux (Home Assistant imports fcntl). On Windows they are not collected, see
tests/conftest.py.
"""

from __future__ import annotations

import asyncio
from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.realiser_a16.api import A16DeviceInfo
from custom_components.realiser_a16.const import DOMAIN
from custom_components.realiser_a16.pya16 import (
    A16ConnectionError,
    A16State,
    A16TimeoutError,
)
from custom_components.realiser_a16.pya16.parser import parse_packet
from custom_components.realiser_a16.pya16.protocol import SOURCES, preset_command

SERIAL = "A16HS0000#000000"
HOST = "192.0.2.16"

INITIAL_PACKETS = [
    b"PWR=ON",
    b"A16FW=2.17 Jan 26 2024\x00A16SN=" + SERIAL.encode(),
    b"AUR=Listener 1\x00PA=06\x00VA=64\x00AROOM=Room 1\x00ANAME=Subject 1"
    b"\x00ASPKR=12.1.10\x00IN=HDMI-1\x00HTMODE=Gyro\x00USER=DUAL",
    b"A00\x00A01\x00ALL=SOLO\x00TEST=OFF\x00MODE=SVS",
]


class MockA16Client:
    """Stand-in for pya16.A16Client that emulates the device."""

    instances: list[MockA16Client] = []

    def __init__(self, host: str, port: int = 4101, **kwargs) -> None:
        self.host = host
        self.port = port
        self.state = A16State()
        self.connected = False
        self.sent: list[str] = []
        self.stopped = False
        self.fail_connect = MockA16Client.next_fail_connect
        self.timeout_codes: set[str] = set()
        self.device_muted = False  # actual mute state of the "device"
        self._listeners: list = []
        self._conn_listeners: list = []
        MockA16Client.instances.append(self)

    next_fail_connect = False

    # --- connection ---
    async def start(self) -> None:
        if self.fail_connect:
            return
        self.set_connected(True)
        for raw in INITIAL_PACKETS:
            self.push(raw)

    async def wait_connected(self, timeout: float | None = None) -> None:
        if not self.connected:
            raise A16ConnectionError("not connected")

    async def stop(self) -> None:
        self.stopped = True
        self.set_connected(False)

    def set_connected(self, connected: bool) -> None:
        if connected != self.connected:
            self.connected = connected
            for cb in list(self._conn_listeners):
                cb(connected)

    def add_listener(self, cb):
        self._listeners.append(cb)
        return lambda: self._listeners.remove(cb)

    def add_connection_listener(self, cb):
        self._conn_listeners.append(cb)
        return lambda: self._conn_listeners.remove(cb)

    def push(self, raw: bytes) -> None:
        changed = self.state.apply_packet(parse_packet(raw))
        if changed:
            for cb in list(self._listeners):
                cb(self.state, changed)

    # --- commands ---
    async def send_command(self, code: str, **kwargs) -> dict:
        await asyncio.sleep(0)
        self.sent.append(code)
        if code in self.timeout_codes:
            raise A16TimeoutError(f"No answer to command {code}")
        a = self.state.user_a
        if code == "2c":
            self.push(b"PWR=BOOT")
        elif code == "2d":
            self.push(b"PWR=STANDBY")
        elif code in ("30", "31"):
            vol = (a.volume or 64) + (1 if code == "30" else -1)
            self.push(f"VA={max(27, min(99, vol))}".encode())
        elif code == "83":
            self.push(f"VA={a.volume or 64}".encode())
        elif code == "32":
            self.device_muted = not self.device_muted
            self.push(b"MUTEA=" + (b"MUTE" if self.device_muted else b"OFF"))
        elif code in SOURCES.values():
            name = next(k for k, v in SOURCES.items() if v == code)
            self.push(b"IN=" + name.encode())
        elif 0x70 <= int(code, 16) <= 0x7F:
            n = int(code, 16) - 0x6F
            fields = ["AUR=Listener 1", f"PA={n:02d}", f"AROOM=Room {n}"]
            fields.append(f"ANAME=Subject {n}")
            self.push("\x00".join(fields).encode())
        return {}

    async def power_on(self) -> None:
        await self.send_command("2c")

    async def standby(self) -> None:
        await self.send_command("2d")

    async def select_source(self, source: str) -> None:
        await self.send_command(SOURCES[source])

    async def select_preset(self, user: str, preset: int) -> None:
        await self.send_command(preset_command(user, preset))

    async def volume_up(self, user: str) -> None:
        await self.send_command("30" if user == "a" else "33")

    async def volume_down(self, user: str) -> None:
        await self.send_command("31" if user == "a" else "34")

    async def step_volume(self, user: str, up: bool) -> int | None:
        before = self.state.user(user).volume
        await (self.volume_up if up else self.volume_down)(user)
        after = self.state.user(user).volume
        return after if after != before else None


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


@pytest.fixture
def mock_client() -> Generator[type[MockA16Client]]:
    MockA16Client.instances = []
    MockA16Client.next_fail_connect = False
    with patch("custom_components.realiser_a16.A16Client", MockA16Client):
        yield MockA16Client


@pytest.fixture
def mock_device_info() -> Generator[AsyncMock]:
    with patch(
        "custom_components.realiser_a16.config_flow.async_get_device_info",
        return_value=A16DeviceInfo(SERIAL, "2.17 Jan 26 2024", None, None, None),
    ) as mock:
        yield mock


@pytest.fixture
def config_entry() -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=SERIAL,
        title=f"Realiser A16 ({SERIAL})",
        data={"host": HOST, "port": 4101},
    )


@pytest.fixture
async def setup_integration(hass, mock_client, config_entry):
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    return mock_client.instances[-1]
