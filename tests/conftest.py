"""Shared test helpers: fixture loading and a fake A16 TCP server."""

from __future__ import annotations

import asyncio
import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
# Load pya16 as a top-level package straight from its folder, so the
# HA-dependent integration __init__ is not imported. The integration folder
# itself must not go on sys.path: its select.py shadows the stdlib "select".
_PYA16 = ROOT / "custom_components" / "realiser_a16" / "pya16"
if "pya16" not in sys.modules:
    _spec = importlib.util.spec_from_file_location(
        "pya16", _PYA16 / "__init__.py", submodule_search_locations=[str(_PYA16)]
    )
    _module = importlib.util.module_from_spec(_spec)
    sys.modules["pya16"] = _module
    _spec.loader.exec_module(_module)

FIXTURES = ROOT / "tests" / "fixtures"

# The Home Assistant integration tests need pytest-homeassistant-custom-component,
# which only works on Linux (HA imports fcntl). Skip collecting them elsewhere.
try:
    import pytest_homeassistant_custom_component  # noqa: F401
except ImportError:
    collect_ignore = ["integration"]


def load_chunks(name: str, conn: str | None = None) -> list[bytes]:
    """Raw received chunks (bytes) from an anonymised capture."""
    chunks = []
    for line in (FIXTURES / name).read_text(encoding="utf-8").splitlines():
        rec = json.loads(line)
        if rec["event"] in ("rx", "idle_rx") and (conn is None or rec["conn"] == conn):
            chunks.append(bytes.fromhex(rec["hex"].replace(" ", "")))
    return chunks


def packets_with(chunks: list[bytes], key: bytes) -> bytes:
    """First single packet (incl. terminator) whose fields contain ``key``."""
    for chunk in chunks:
        for raw in chunk.split(b"\x00\r"):
            if raw and any(f.strip(b"\r").startswith(key) for f in raw.split(b"\x00")):
                return raw + b"\x00\r"
    raise LookupError(key)


class FakeA16:
    """Minimal A16 emulation built from the reference capture.

    - answers known commands with packets taken from the fixture
    - pushes the user A block every ``push_interval`` seconds
    - accepts only one client: further connections are closed immediately
      (the real device lets the SYN time out; the effect for the client is the
      same: no second session)
    - ``silent`` = stop answering and pushing (like the real silent drop)
    """

    def __init__(self, push_interval: float = 0.2) -> None:
        chunks = load_chunks("run2_reference.jsonl")
        self.push_interval = push_interval
        self.volume = {"a": 64, "b": 65}
        self.responses: dict[str, bytes] = {
            "2e": b"PWR=ON\x00\r",
            "2c": b"PWR=ON\x00\r",
            "2d": b"PWR=STANDBY\x00\r",
            "64": packets_with(chunks, b"A16SN="),
            "80": packets_with(chunks, b"AUR="),
            "a0": packets_with(chunks, b"BUR="),
            "37": packets_with(chunks, b"ACH1="),
            "21": b"IN=HDMI-1\x00\r",
            "75": b"PA=06\x00\r",
        }
        self.push_packet = packets_with(chunks, b"AUR=")
        speaker_block = packets_with(
            load_chunks("run1_manual_operation.jsonl"), b"MODE="
        )
        self.responses["ae"] = speaker_block
        self.responses["af"] = speaker_block
        self.received: list[str] = []
        self.connections_total = 0
        self.active = 0
        self.max_active = 0
        self.rejected = 0
        self.silent = False
        self.ignore: set[str] = set()
        # code -> number of next occurrences to swallow (real A16 drops ~5 %)
        self.drop_next: dict[str, int] = {}
        # 2c -> PWR=BOOT, then no answers until reset_after_boot s, then the
        # fake closes the connection (like the real reset) and is ON.
        self.reset_after_boot: float | None = None
        self.booting = False
        # Like the real device: commands before the first push are ignored.
        self.ignore_before_first_push = True
        self.ignored_early: list[str] = []
        self._server: asyncio.Server | None = None
        self.port = 0

    async def start(self) -> None:
        self._server = await asyncio.start_server(self._handle, "127.0.0.1", 0)
        self.port = self._server.sockets[0].getsockname()[1]

    async def close(self) -> None:
        if self._server:
            self._server.close()
            await self._server.wait_closed()

    def _answer(self, code: str) -> bytes | None:
        if code in ("30", "31", "83"):
            if code == "30":
                self.volume["a"] = min(99, self.volume["a"] + 1)
            elif code == "31":
                self.volume["a"] = max(27, self.volume["a"] - 1)
            return f"VA={self.volume['a']}\x00\r".encode()
        if code in ("33", "34", "a3"):
            if code == "33":
                self.volume["b"] = min(99, self.volume["b"] + 1)
            elif code == "34":
                self.volume["b"] = max(27, self.volume["b"] - 1)
            return f"VB={self.volume['b']}\x00\r".encode()
        return self.responses.get(code)

    async def _handle(self, reader, writer) -> None:
        self.connections_total += 1
        if self.active:
            self.rejected += 1
            writer.close()
            return
        self.active += 1
        self.max_active = max(self.max_active, self.active)

        pushed = asyncio.Event()

        async def pusher():
            while True:
                await asyncio.sleep(self.push_interval)
                if not self.silent:
                    writer.write(self.push_packet)
                    pushed.set()

        push_task = asyncio.create_task(pusher())
        try:
            while True:
                line = await reader.readline()
                if not line:
                    break
                code = line.strip().decode()
                self.received.append(code)
                if self.ignore_before_first_push and not pushed.is_set():
                    self.ignored_early.append(code)
                    continue
                if self.drop_next.get(code, 0) > 0:
                    self.drop_next[code] -= 1
                    continue
                if self.silent or code in self.ignore or self.booting:
                    continue
                if code == "2c" and self.reset_after_boot is not None:
                    writer.write(b"PWR=BOOT\x00\r")
                    await writer.drain()
                    self.booting = True
                    self.silent = True
                    await asyncio.sleep(self.reset_after_boot)
                    self.booting = False
                    self.silent = False
                    self.responses["2e"] = b"PWR=ON\x00\r"
                    break  # closes the connection like the real reset
                if code == "2d":
                    self.responses["2e"] = b"PWR=STANDBY\x00\r"
                await asyncio.sleep(0.01)
                if (answer := self._answer(code)) is not None:
                    writer.write(answer)
                    await writer.drain()
        except (ConnectionError, OSError):
            pass
        finally:
            push_task.cancel()
            self.active -= 1
            writer.close()


@pytest.fixture
async def fake_a16():
    server = FakeA16()
    await server.start()
    yield server
    await server.close()
