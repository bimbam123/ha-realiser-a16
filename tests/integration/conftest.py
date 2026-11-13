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
    A16Client,
    A16ConnectionError,
    A16State,
    A16Stats,
    A16TimeoutError,
)
from custom_components.realiser_a16.pya16.parser import parse_packet
from custom_components.realiser_a16.pya16.protocol import (
    MUTE_TOGGLE,
    SOURCES,
    VOLUME_DOWN,
    VOLUME_UP,
    preset_command,
)

SERIAL = "A16HS0000#000000"
HOST = "192.0.2.16"

INITIAL_PACKETS = [
    b"PWR=ON",
    b"A16FW=2.17 Jan 26 2024\x00A16SN=" + SERIAL.encode(),
    b"AUR=Listener 1\x00PA=06\x00VA=64\x00AROOM=Room 1\x00ANAME=Subject 1"
    b"\x00ASPKR=12.1.10\x00AQFILE=HD800S Subject 1  \x00AQNAME=Subject 1"
    b"\x00AQDATE=19:09 29/04/2023\x00AQTYPE=flatEQ\x00AQMOD=HD800S  \x00ATACT=ON"
    b"\x00IN=HDMI-1\x00DEC=PCM 2ch\x00LM=2.1.0\x00UMIX=OFF\x00HTMODE=Gyro"
    b"\x00LEG=OFF\x00USER=DUAL",
    b"BUR=Listener 2\x00PB=07\x00VB=65\x00BROOM=Room B7\x00BNAME=Subject B7"
    b"\x00BSPKR=9.1.6",
    b"A00\x00A01\x00ALL=SOLO\x00TEST=OFF\x00MODE=SVS",
]


class MockA16Client:
    """Stand-in for pya16.A16Client that emulates the device."""

    instances: list[MockA16Client] = []
    next_fail_connect = False

    def __init__(self, host: str, port: int = 4101, **kwargs) -> None:
        self.host = host
        self.port = port
        self.state = A16State()
        self.stats = A16Stats()
        self.connected = False
        self.sent: list[str] = []
        self.stopped = False
        self.fail_connect = MockA16Client.next_fail_connect
        self.timeout_codes: set[str] = set()
        self.ignore_steps = 0  # next N volume steps change nothing
        self.device_muted = {"a": False, "b": False}
        self.device_preset_b = 7
        self.device_test = "OFF"
        self.device_ht = "OFF"
        self.drop_codes: dict[str, int] = {}  # code -> ignore the next N
        self.response_timeout = 5.0
        self.min_command_interval = 1.2
        self.min_step_interval = 2.5
        self.keepalive_interval = 20.0
        self._listeners: list = []
        self._conn_listeners: list = []
        MockA16Client.instances.append(self)

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
        self.stats.commands_sent += 1
        if code in self.timeout_codes:
            raise A16TimeoutError(f"No answer to command {code}")
        if self.drop_codes.get(code, 0) > 0:  # ignored by the device
            self.drop_codes[code] -= 1
            raise A16TimeoutError(f"No answer to command {code}")
        value = int(code, 16)
        if code == "2c":
            self.push(b"PWR=BOOT")
        elif code == "2d":
            self.push(b"PWR=STANDBY")
        elif code in (*VOLUME_UP.values(), *VOLUME_DOWN.values()):
            user = "a" if code in (VOLUME_UP["a"], VOLUME_DOWN["a"]) else "b"
            us = self.state.user(user)
            vol = us.volume or 64
            if self.ignore_steps > 0:
                self.ignore_steps -= 1
            else:
                vol += 1 if code in VOLUME_UP.values() else -1
            key = "VA" if user == "a" else "VB"
            self.push(f"{key}={max(27, min(99, vol))}".encode())
        elif code in ("83", "a3"):
            user = "a" if code == "83" else "b"
            key = "VA" if user == "a" else "VB"
            self.push(f"{key}={self.state.user(user).volume or 64}".encode())
        elif code in MUTE_TOGGLE.values():
            user = "a" if code == MUTE_TOGGLE["a"] else "b"
            self.device_muted[user] = not self.device_muted[user]
            state = "MUTE" if self.device_muted[user] else "OFF"
            self.push(f"MUTE{user.upper()}={state}".encode())
        elif code in SOURCES.values():
            name = next(k for k, v in SOURCES.items() if v == code)
            self.push(b"IN=" + name.encode())
        elif 0x70 <= value <= 0x7F:
            n = value - 0x6F
            fields = ["AUR=Listener 1", f"PA={n:02d}", f"AROOM=Room {n}"]
            fields.append(f"ANAME=Subject {n}")
            self.push("\x00".join(fields).encode())
        elif 0x90 <= value <= 0x9F:
            # Like the device: only PB= is answered, no room/subject of B.
            self.device_preset_b = value - 0x8F
            self.push(f"PB={self.device_preset_b:02d}".encode())
        elif code in ("4d", "5e"):
            self.push(b"MODE=SVS" if code == "4d" else b"MODE=MIX")
        elif code == "08":
            self.device_test = "OFF" if self.device_test == "LOOP" else "LOOP"
            self.push(f"TEST={self.device_test}".encode())
        elif code == "42":
            self.device_ht = "OFF" if self.device_ht == "ACTIVE" else "ACTIVE"
            self.push(f"HT={self.device_ht}".encode())
        elif code == "af":
            self.push(f"A00\x00ALL=SOLO\x00TEST={self.device_test}".encode())
        elif code == "a0":
            n = self.device_preset_b
            fields = ["BUR=Listener 2", f"PB={n:02d}", f"BROOM=Room B{n}"]
            fields.append(f"BNAME=Subject B{n}")
            self.push("\x00".join(fields).encode())
        self.stats.answered += 1
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
        await self.send_command(VOLUME_UP[user])

    async def volume_down(self, user: str) -> None:
        await self.send_command(VOLUME_DOWN[user])

    # The real toggle logic only uses send_command and state.
    set_output = A16Client.set_output
    set_test_signal = A16Client.set_test_signal
    set_head_tracking = A16Client.set_head_tracking
    _set_toggle = A16Client._set_toggle

    async def step_volume(self, user: str, up: bool) -> int | None:
        before = self.state.user(user).volume
        await (self.volume_up if up else self.volume_down)(user)
        after = self.state.user(user).volume
        return after if after != before else None


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


@pytest.fixture(autouse=True)
def no_user_b_info_delay():
    with patch("custom_components.realiser_a16.coordinator.USER_B_INFO_DELAY", 0):
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
