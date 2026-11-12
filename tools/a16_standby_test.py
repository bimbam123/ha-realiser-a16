"""Standby test for the Realiser A16 (changes the power state!).

1. connect, wait for the first push, check power with 2e
2. send 2d (standby), then observe for ``--standby`` seconds with a 2e
   keepalive every 20 s: are keepalives answered, are there pushes?
3. send 2c (power on), measure the time until PWR=ON and until the first
   normal user A push (AUR block); keep observing for ``--after`` seconds.

A dropped connection is logged and re-established. Raw data goes to
docs/captures/ (local only).

Usage:
    python tools/a16_standby_test.py 192.168.1.5 [--port 4101]
"""

from __future__ import annotations

import argparse
import asyncio
import time
from datetime import datetime

from a16_capture import CAPTURE_DIR, Capture, split_fields

KEEPALIVE = 20.0


class Session:
    def __init__(self, host: str, port: int, cap: Capture) -> None:
        self.host, self.port, self.cap = host, port, cap
        self.reader: asyncio.StreamReader | None = None
        self.writer: asyncio.StreamWriter | None = None
        self.events: list[tuple[float, list[str]]] = []  # (t, fields) per packet
        self._task: asyncio.Task | None = None
        self.t0 = time.monotonic()

    def now(self) -> float:
        return time.monotonic() - self.t0

    async def connect(self) -> None:
        while True:
            try:
                self.reader, self.writer = await asyncio.wait_for(
                    asyncio.open_connection(self.host, self.port), 5
                )
                self.cap.log("c", "connected", t=round(self.now(), 3))
                self._task = asyncio.create_task(self._read())
                return
            except (OSError, TimeoutError) as err:
                self.cap.log("c", "connect_fail", error=repr(err))
                await asyncio.sleep(2)

    async def _read(self) -> None:
        buf = b""
        while True:
            try:
                chunk = await self.reader.read(4096)
            except OSError as err:
                self.cap.log("c", "read_error", error=repr(err))
                return
            if not chunk:
                self.cap.log("c", "eof")
                return
            buf += chunk
            *packets, buf = buf.split(b"\x00\r")
            for pkt in packets:
                fields = split_fields(pkt.replace(b"\r", b""))
                t = self.now()
                self.events.append((t, fields))
                self.cap.log("c", "rx", t=round(t, 3), hex=pkt.hex(" "), fields=fields)

    @property
    def alive(self) -> bool:
        return self._task is not None and not self._task.done()

    async def send(self, code: str) -> float:
        if not self.alive:
            self.cap.log("c", "reconnect_needed")
            await self.connect()
        t = self.now()
        try:
            self.writer.write(code.encode() + b"\r\n")
            await self.writer.drain()
            self.cap.log("c", "tx", cmd=code, t=round(t, 3))
        except OSError as err:
            self.cap.log("c", "tx_error", cmd=code, error=repr(err))
        return t

    def first_after(self, t: float, pred) -> float | None:
        for te, fields in self.events:
            if te >= t and pred(fields):
                return te
        return None


def has(prefix: str):
    return lambda fields: any(f.strip().startswith(prefix) for f in fields)


async def observe(s: Session, seconds: float, label: str) -> list[dict]:
    """Send 2e every KEEPALIVE s for ``seconds``; return keepalive results."""
    results = []
    end = s.now() + seconds
    while s.now() < end:
        t = await s.send("2e")
        await asyncio.sleep(3)
        ans = s.first_after(t, has("PWR="))
        pwr = next(
            (f for te, fs in s.events if te >= t for f in fs if f.startswith("PWR=")),
            None,
        )
        results.append(
            {"t": round(t, 1), "answered_s": ans and round(ans - t, 2), "pwr": pwr}
        )
        s.cap.log("c", f"{label}_keepalive", **results[-1])
        await asyncio.sleep(max(0, min(KEEPALIVE - 3, end - s.now())))
    return results


def push_stats(s: Session, t_from: float, t_to: float) -> dict:
    pk = [(t, f) for t, f in s.events if t_from <= t < t_to]
    aur = [t for t, f in pk if has("AUR=")(f)]
    gaps = [b - a for a, b in zip(aur, aur[1:], strict=False)]
    return {
        "packets": len(pk),
        "aur_blocks": len(aur),
        "max_aur_gap_s": round(max(gaps), 2) if gaps else None,
        "keys": sorted({f.split("=")[0] for _, fs in pk for f in fs})[:40],
    }


async def main(host: str, port: int, standby_s: float, after_s: float) -> None:
    CAPTURE_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    cap = Capture(CAPTURE_DIR / f"{stamp}-standby.jsonl")
    s = Session(host, port, cap)
    await s.connect()
    await asyncio.sleep(3)  # first push
    t = await s.send("2e")
    await asyncio.sleep(3)
    cap.log(
        "-",
        "baseline",
        pwr_answer_s=(a := s.first_after(t, has("PWR="))) and round(a - t, 2),
    )

    t_off = await s.send("2d")
    await asyncio.sleep(5)
    a = s.first_after(t_off, has("PWR="))
    cap.log("-", "standby_answer", after_s=a and round(a - t_off, 2))
    ka_standby = await observe(s, standby_s, "standby")
    stats_standby = push_stats(s, t_off + 5, s.now())
    cap.log("-", "standby_pushes", **stats_standby)

    t_on = await s.send("2c")
    deadline = s.now() + after_s
    while s.now() < deadline and not s.first_after(t_on, has("AUR=")):
        await asyncio.sleep(0.5)
        if s.now() - t_on > 15 and int(s.now() - t_on) % 20 == 0:
            await s.send("2e")
    t_pwr_on = s.first_after(t_on, lambda f: "PWR=ON" in [x.strip() for x in f])
    t_boot = s.first_after(t_on, lambda f: "PWR=BOOT" in [x.strip() for x in f])
    t_aur = s.first_after(t_on, has("AUR="))
    cap.log(
        "-",
        "power_on",
        pwr_on_s=t_pwr_on and round(t_pwr_on - t_on, 2),
        pwr_boot_s=t_boot and round(t_boot - t_on, 2),
        first_aur_s=t_aur and round(t_aur - t_on, 2),
    )
    t_obs = s.now()
    ka_after = await observe(s, 60, "after_on")
    stats_after = push_stats(s, t_obs, s.now())
    cap.log("-", "after_on_pushes", **stats_after)

    print("\n=== Summary ===")
    print("standby keepalives:", ka_standby)
    print("standby pushes:", stats_standby)
    print(
        "power on: PWR=ON after",
        t_pwr_on and round(t_pwr_on - t_on, 2),
        "s,",
        "PWR=BOOT after",
        t_boot and round(t_boot - t_on, 2),
        "s,",
        "first AUR push after",
        t_aur and round(t_aur - t_on, 2),
        "s",
    )
    print("after-on keepalives:", ka_after)
    print("after-on pushes:", stats_after)
    print("capture:", cap.path)
    cap.close()
    if s.writer:
        s.writer.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("host")
    ap.add_argument("--port", type=int, default=4101)
    ap.add_argument("--standby", type=float, default=120, help="seconds in standby")
    ap.add_argument(
        "--after", type=float, default=180, help="max wait for pushes after 2c"
    )
    a = ap.parse_args()
    asyncio.run(main(a.host, a.port, a.standby, a.after))
