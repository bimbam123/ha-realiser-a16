"""Probe how the A16 answers volume steps and mute toggles (raw packets).

Changes volume/mute of user A temporarily, but only in pairs that cancel
out, and finally restores ``--volume`` and "not muted". Raw data goes to
docs/captures/ (local only).

Usage:
    python tools/a16_volume_probe.py 192.168.1.5 --volume 64
"""

from __future__ import annotations

import argparse
import asyncio
import time
from datetime import datetime

from a16_capture import CAPTURE_DIR, Capture, split_fields


class Probe:
    def __init__(self, host: str, port: int, cap: Capture) -> None:
        self.host, self.port, self.cap = host, port, cap
        self.t0 = time.monotonic()
        self.events: list[tuple[float, list[str]]] = []

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
                await asyncio.sleep(5)
        else:
            raise SystemExit("could not connect")
        self.task = asyncio.create_task(self._read())

    async def _read(self) -> None:
        buf = b""
        while chunk := await self.reader.read(4096):
            buf += chunk
            *packets, buf = buf.split(b"\x00\r")
            for pkt in packets:
                fields = split_fields(pkt.replace(b"\r", b""))
                t = self.now()
                self.events.append((t, fields))
                short = [f for f in fields if f.split("=")[0] in KEYS] or [
                    "<block>" if any(f.startswith("AROOM") for f in fields) else "?"
                ]
                print(f"{t:8.3f}  rx  {' '.join(short)}")
                self.cap.log("c", "rx", t=round(t, 3), hex=pkt.hex(" "), fields=fields)

    async def send(self, code: str, observe: float) -> list[str]:
        t = self.now()
        self.writer.write(code.encode() + b"\r\n")
        await self.writer.drain()
        print(f"{t:8.3f}  tx  {code}")
        self.cap.log("c", "tx", cmd=code, t=round(t, 3))
        await asyncio.sleep(observe)
        return [f for te, fs in self.events if te >= t for f in fs]

    def last(self, key: str) -> str | None:
        for _, fs in reversed(self.events):
            for f in reversed(fs):
                if f.startswith(key + "="):
                    return f.split("=", 1)[1]
        return None


KEYS = {"VA", "MUTEA", "PWR", "PA", "TRI"}


async def main(host: str, port: int, volume: int) -> None:
    CAPTURE_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    cap = Capture(CAPTURE_DIR / f"{stamp}-volume-probe.jsonl")
    p = Probe(host, port, cap)
    await p.connect()
    await asyncio.sleep(3)
    print("--- baseline")
    await p.send("83", 3)
    print("--- single +1")
    await p.send("30", 4)
    print("--- single -1")
    await p.send("31", 4)
    print("--- +1 +1 (0.4 s gap)")
    await p.send("30", 0.4)
    await p.send("30", 4)
    print("--- -1 -1 (0.4 s gap)")
    await p.send("31", 0.4)
    await p.send("31", 4)
    print("--- mute toggle #1")
    await p.send("32", 4)
    print("--- mute toggle #2")
    await p.send("32", 4)
    print("--- query volume")
    await p.send("83", 3)

    # restore: volume and unmuted
    for _ in range(10):
        cur = p.last("VA")
        if cur is None or int(cur) == volume:
            break
        await p.send("30" if int(cur) < volume else "31", 2)
    if p.last("MUTEA") == "MUTE":
        print("--- unmute")
        await p.send("32", 3)
    print(f"=== final VA={p.last('VA')} MUTEA={p.last('MUTEA')}")
    cap.log("-", "final", va=p.last("VA"), mutea=p.last("MUTEA"))
    p.writer.close()
    cap.close()
    print("capture:", cap.path)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("host")
    ap.add_argument("--port", type=int, default=4101)
    ap.add_argument("--volume", type=int, required=True, help="volume to restore")
    a = ap.parse_args()
    asyncio.run(main(a.host, a.port, a.volume))
