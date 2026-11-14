"""Probe the A16 toggles for v0.3.0: mode (4d/5e), test (08), HT (42), TRI.

Each phase reads the state first, toggles, checks again, and finally
restores the start state. Toggles are never repeated blindly: a correction
is only sent when a query (``af``) shows the wrong state. Commands are sent
at least ``--gap`` seconds apart (default 2.5 s, enough for network delays of
up to ~1 s over Powerline/Wi-Fi). Raw data goes to docs/captures/ (local only).

Before running: turn the volume down (TEST plays a test signal), close other
control apps (Centro Control) and stop the Home Assistant test instance - the
A16 accepts only one client.

Usage:
    python tools/a16_toggle_probe.py 192.168.1.5
    python tools/a16_toggle_probe.py 192.168.1.5 --only mode test
    python tools/a16_toggle_probe.py 192.168.1.5 --only tri --watch 45
"""

from __future__ import annotations

import argparse
import asyncio
import time
from datetime import datetime

from a16_capture import CAPTURE_DIR, Capture, split_fields

KEYS = {"MODE", "TEST", "HT", "HTMODE", "ALL", "TRI", "VA", "PWR", "KEY", "IN"}
PHASES = ("mode", "test", "ht", "tri")


class Probe:
    def __init__(self, host: str, port: int, cap: Capture, gap: float) -> None:
        self.host, self.port, self.cap, self.gap = host, port, cap, gap
        self.t0 = time.monotonic()
        self.last_tx = -1e9
        self.events: list[tuple[float, list[str]]] = []
        self.notes: list[str] = []

    def now(self) -> float:
        return time.monotonic() - self.t0

    async def connect(self) -> None:
        for attempt in range(12):
            try:
                self.reader, self.writer = await asyncio.wait_for(
                    asyncio.open_connection(self.host, self.port), 6
                )
                self.cap.log("c", "connected", attempt=attempt)
                break
            except (OSError, TimeoutError) as err:
                self.cap.log("c", "connect_fail", error=repr(err))
                print(f"connect failed ({err!r}), retrying in 5 s")
                await asyncio.sleep(5)
        else:
            raise SystemExit("could not connect")
        self.task = asyncio.create_task(self._read())

    async def _read(self) -> None:
        try:
            await self._read_loop()
        except OSError as err:  # connection aborted (seen over Powerline)
            print(f"connection lost: {err!r}")
            self.cap.log("c", "conn_lost", error=repr(err))

    async def _read_loop(self) -> None:
        buf = b""
        while chunk := await self.reader.read(4096):
            buf += chunk
            *packets, buf = buf.split(b"\x00\r")
            for pkt in packets:
                fields = split_fields(pkt.replace(b"\r", b""))
                t = self.now()
                self.events.append((t, fields))
                short = [f for f in fields if f.split("=")[0] in KEYS]
                if any(f.startswith(("AROOM", "AUR")) for f in fields):
                    short.append("<A block>")
                print(f"{t:8.3f}  rx  {' '.join(short) or '?'}")
                self.cap.log("c", "rx", t=round(t, 3), hex=pkt.hex(" "), fields=fields)

    async def send(self, code: str, observe: float = 4.0) -> list[str]:
        """Send ``code`` (keeping the gap) and return the fields seen afterwards."""
        wait = self.last_tx + self.gap - self.now()
        if wait > 0:
            await asyncio.sleep(wait)
        t = self.now()
        self.writer.write(code.encode() + b"\r\n")
        await self.writer.drain()
        self.last_tx = t
        print(f"{t:8.3f}  tx  {code}")
        self.cap.log("c", "tx", cmd=code, t=round(t, 3))
        await asyncio.sleep(observe)
        return [f for te, fs in self.events if te >= t for f in fs]

    def answer(self, code: str, key: str, fields: list[str]) -> str | None:
        """Last ``key`` value in ``fields``; note and log it (with latency)."""
        value = next(
            (f.split("=", 1)[1] for f in reversed(fields) if f.startswith(key + "=")),
            None,
        )
        latency = self._latency(key)
        text = f"{code} -> {key}={value}" + (
            f" ({latency:.2f} s)" if value is not None and latency is not None else ""
        )
        self.note(text if value is not None else f"{code} -> no {key}= answer")
        return value

    def _latency(self, key: str) -> float | None:
        for te, fs in reversed(self.events):
            if te < self.last_tx:
                return None
            if any(f.startswith(key + "=") for f in fs):
                return te - self.last_tx
        return None

    def note(self, text: str) -> None:
        print(f"          >>> {text}")
        self.notes.append(text)
        self.cap.log("-", "note", text=text)

    async def query_af(self) -> dict[str, str]:
        fields = await self.send("af", 3)
        found = {
            k: v
            for k, v in (f.split("=", 1) for f in fields if "=" in f)
            if k in {"MODE", "TEST", "ALL", "HT"}
        }
        self.note(f"af -> {found or 'no answer'}")
        return found


async def phase_mode(p: Probe, repeat: int) -> None:
    print("=== mode: 5e cycle, 4d, restore")
    start = (await p.query_af()).get("MODE")
    p.note(f"mode start: {start}")
    if start is None:
        p.note("mode: no MODE from af, phase skipped")
        return
    for run in range(repeat):
        seen = [start]
        for _ in range(4):
            p.answer("5e", "MODE", await p.send("5e"))
            mode = (await p.query_af()).get("MODE")
            seen.append(mode or "?")
            if mode == start:
                break
        p.note(f"mode run {run + 1}: 5e sequence {' -> '.join(seen)}")
    p.answer("4d", "MODE", await p.send("4d"))
    p.note(f"mode after 4d: {(await p.query_af()).get('MODE')}")
    # restore
    for _ in range(4):
        mode = (await p.query_af()).get("MODE")
        if mode == start or mode is None:
            break
        await p.send("4d" if start == "SVS" else "5e")
    p.note(f"mode restored: {(await p.query_af()).get('MODE')} (start {start})")


async def phase_test(p: Probe, repeat: int) -> None:
    print("=== test signal: 08 on/off (volume down!)")
    start = (await p.query_af()).get("TEST")
    p.note(f"test start: {start}")
    for run in range(repeat):
        for _ in range(2):
            p.answer("08", "TEST", await p.send("08"))
            p.note(f"test run {run + 1}: af TEST={(await p.query_af()).get('TEST')}")
    # restore, only after a query shows the wrong state
    test = (await p.query_af()).get("TEST")
    if start is not None and test is not None and test != start:
        await p.send("08")
        test = (await p.query_af()).get("TEST")
    p.note(f"test restored: {test} (start {start})")


async def phase_ht(p: Probe, repeat: int) -> None:
    print("=== head tracking: 42 on/off, does 80/af show it?")
    before = await p.send("80", 3)
    p.answer("80", "HTMODE", before)
    await p.query_af()
    first = None
    for run in range(repeat):
        for i in range(2):
            ht = p.answer("42", "HT", await p.send("42"))
            if run == 0 and i == 0:
                first = ht
            p.answer("80", "HTMODE", await p.send("80", 3))
            await p.query_af()
    last = next(
        (
            f.split("=", 1)[1]
            for _, fs in reversed(p.events)
            for f in reversed(fs)
            if f.startswith("HT=")
        ),
        None,
    )
    if first is not None and last == first:
        p.note("ht: odd number of confirmed toggles, sending one more 42")
        p.answer("42", "HT", await p.send("42"))
    start = {"ACTIVE": "OFF", "OFF": "ACTIVE"}.get(first or "", "unknown")
    p.note(f"ht start (derived): {start}; check the A16 display")


async def phase_tri(p: Probe, watch: float) -> None:
    print(f"=== tri-level: queries, then {watch:.0f} s watching")
    print("    -> change tri-level (menu/remote) on the A16 during the watch")
    p.answer("83", "TRI", await p.send("83", 3))
    p.answer("80", "TRI", await p.send("80", 3))
    end = p.now() + watch
    while p.now() < end:
        p.answer("83", "TRI", await p.send("83", 5))
    tris = sorted({f for _, fs in p.events for f in fs if f.startswith("TRI=")})
    p.note(f"tri: values seen {tris or 'none'}")


async def main(args: argparse.Namespace) -> None:
    CAPTURE_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    cap = Capture(CAPTURE_DIR / f"{stamp}-toggle-probe.jsonl")
    p = Probe(args.host, args.port, cap, args.gap)
    await p.connect()
    await asyncio.sleep(3)
    p.answer("2e", "PWR", await p.send("2e", 3))
    try:
        for phase in args.only:
            if phase == "mode":
                await phase_mode(p, args.repeat)
            elif phase == "test":
                await phase_test(p, args.repeat)
            elif phase == "ht":
                await phase_ht(p, args.repeat)
            elif phase == "tri":
                await phase_tri(p, args.watch)
    except OSError as err:
        p.note(f"aborted: {err!r}")
    finally:
        p.writer.close()
        cap.close()
    print("\n=== summary")
    for line in p.notes:
        print("  " + line)
    print("capture:", cap.path)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("host")
    ap.add_argument("--port", type=int, default=4101)
    ap.add_argument("--gap", type=float, default=2.5, help="min. gap (s)")
    ap.add_argument("--repeat", type=int, default=2, help="runs per toggle sequence")
    ap.add_argument("--watch", type=float, default=30, help="tri watch time (s)")
    ap.add_argument("--only", nargs="+", choices=PHASES, default=list(PHASES))
    asyncio.run(main(ap.parse_args()))
