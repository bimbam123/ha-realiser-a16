"""Shared test helpers: fixture loading and a fake A16 TCP server."""

from __future__ import annotations

import asyncio
import importlib.util
import json
import re
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


TERM = bytes([0, 13])  # packet terminator (NUL, CR)


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
        self.muted = {"a": False, "b": False}
        # TEST/HT toggles and output mode (4d/5e set the mode, FW 2.17)
        self.test = "OFF"
        self.ht = "OFF"
        self.mode = "SVS"
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
        # Volume steps: answer delay, and an optional stale duplicate of the
        # answer sent later (seen on the real A16 after vol+/vol-).
        self.volume_answer_delay = 0.01
        self.duplicate_volume_after: float | None = None
        # Like the real A16: a command arriving less than min_interval after
        # the previous one is ignored. An ignored volume step is still
        # answered with the unchanged VA=, other commands get no answer.
        self.min_interval: float | None = None
        self.ignore_next_steps = 0
        self.ignored: list[str] = []
        self.reset_first_connections = 0
        self.lose_answer_next: dict[str, int] = {}
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
        if code in ("32", "35"):
            user = "a" if code == "32" else "b"
            self.muted[user] = not self.muted[user]
            state = "MUTE" if self.muted[user] else "OFF"
            return f"MUTE{user.upper()}={state}".encode() + TERM
        if code == "08":
            self.test = "OFF" if self.test == "LOOP" else "LOOP"
            return f"TEST={self.test}".encode() + TERM
        if code == "42":
            self.ht = "OFF" if self.ht == "ACTIVE" else "ACTIVE"
            return f"HT={self.ht}".encode() + TERM
        if code in ("4d", "5e"):
            self.mode = "SVS" if code == "4d" else "MIX"
            return f"MODE={self.mode}".encode() + TERM
        if code == "af":
            block = re.sub(
                rb"TEST=[A-Z]*", f"TEST={self.test}".encode(), self.responses["af"]
            )
            return re.sub(rb"MODE=[A-Z]*", f"MODE={self.mode}".encode(), block)
        return self.responses.get(code)

    async def _handle(self, reader, writer) -> None:
        self.connections_total += 1
        if self.reset_first_connections > 0:
            # Real A16 shortly after another client left: accept, then reset.
            self.reset_first_connections -= 1
            await asyncio.sleep(0.05)
            writer.transport.abort()
            return
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
                    # like the real device: the push carries the current volume
                    writer.write(
                        self.push_packet.replace(
                            b"VA=64", f"VA={self.volume['a']}".encode()
                        )
                    )
                    pushed.set()

        push_task = asyncio.create_task(pusher())
        timers: list[asyncio.TimerHandle] = []
        last_cmd: float | None = None
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
                now = asyncio.get_running_loop().time()
                too_soon = (
                    self.min_interval is not None
                    and last_cmd is not None
                    and now - last_cmd < self.min_interval
                )
                last_cmd = now
                is_step = code in ("30", "31", "33", "34")
                if too_soon or (is_step and self.ignore_next_steps > 0):
                    if not too_soon:
                        self.ignore_next_steps -= 1
                    self.ignored.append(code)
                    if is_step:
                        user = "a" if code in ("30", "31") else "b"
                        key = "VA" if user == "a" else "VB"
                        writer.write(f"{key}={self.volume[user]}\x00\r".encode())
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
                is_step = code in ("30", "31", "33", "34")
                await asyncio.sleep(self.volume_answer_delay if is_step else 0.01)
                answer = self._answer(code)  # applies the command
                if self.lose_answer_next.get(code, 0) > 0:
                    # executed, but the answer gets lost on the way back
                    self.lose_answer_next[code] -= 1
                    continue
                if answer is not None:
                    writer.write(answer)
                    if is_step and self.duplicate_volume_after is not None:
                        loop = asyncio.get_running_loop()
                        timers.append(
                            loop.call_later(
                                self.duplicate_volume_after, writer.write, answer
                            )
                        )
                    await writer.drain()
        except (ConnectionError, OSError):
            pass
        finally:
            push_task.cancel()
            for timer in timers:
                timer.cancel()
            self.active -= 1
            writer.close()


@pytest.fixture
async def fake_a16():
    server = FakeA16()
    await server.start()
    yield server
    await server.close()
