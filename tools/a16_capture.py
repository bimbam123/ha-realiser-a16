"""Capture raw responses from a Realiser A16 TCP command server.

Read-only test tool (sends only status/info requests). It

1. opens one persistent connection and sends 2e, 64, 80, 83, a0, 37 in turn,
2. opens a second simultaneous connection and checks whether it is served,
   and whether the first connection still works afterwards,
3. stays idle on the first connection until the A16 closes it (inactivity
   timeout) and measures how long that took, then tries to reconnect.

Every received chunk is written with a timestamp to docs/captures/.

Usage:
    python tools/a16_capture.py 192.168.1.5 4101 [--max-idle 300]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from datetime import datetime, timezone
from pathlib import Path

COMMANDS = ["2e", "64", "80", "83", "a0", "37"]
QUIET_AFTER = 1.5  # seconds without new data = response finished
FIRST_BYTE_TIMEOUT = 3.0
# The A16 pushes status about once per second, so "quiet" may never happen.
# Each read window is therefore also capped.
MAX_WINDOW = 6.0

CAPTURE_DIR = Path(__file__).resolve().parent.parent / "docs" / "captures"


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="milliseconds")


def split_fields(data: bytes) -> list[str]:
    return [p.decode("ascii", "replace") for p in data.split(b"\x00") if p]


class Capture:
    """Writes one JSON object per event to a .jsonl file and echoes a summary."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.fh = path.open("w", encoding="utf-8")
        self.t0 = time.monotonic()

    def log(self, conn: str, event: str, **extra) -> None:
        rec = {
            "ts": now_iso(),
            "t_rel_s": round(time.monotonic() - self.t0, 3),
            "conn": conn,
            "event": event,
            **extra,
        }
        self.fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
        self.fh.flush()
        short = {k: v for k, v in extra.items() if k != "hex"}
        print(f"[{rec['t_rel_s']:8.3f}] {conn:<5} {event:<10} {short}")

    def close(self) -> None:
        self.fh.close()


async def read_until_quiet(
    reader: asyncio.StreamReader, cap: Capture, conn: str
) -> bytes:
    """Read until quiet for QUIET_AFTER s or MAX_WINDOW s passed. Logs chunks."""
    buf = b""
    timeout = FIRST_BYTE_TIMEOUT
    deadline = time.monotonic() + MAX_WINDOW
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        try:
            chunk = await asyncio.wait_for(reader.read(4096), min(timeout, remaining))
        except TimeoutError:
            break
        except (ConnectionResetError, OSError) as err:
            cap.log(conn, "read_error", error=repr(err))
            break
        if not chunk:
            cap.log(conn, "eof")
            break
        buf += chunk
        cap.log(
            conn,
            "rx",
            bytes=len(chunk),
            hex=chunk.hex(" "),
            ascii=chunk.decode("ascii", "replace").replace("\x00", "\\0"),
            fields=split_fields(chunk),
        )
        timeout = QUIET_AFTER
    return buf


async def send(
    writer: asyncio.StreamWriter, cap: Capture, conn: str, code: str
) -> None:
    data = code.encode("ascii") + b"\r\n"
    try:
        writer.write(data)
        await writer.drain()
    except (ConnectionResetError, BrokenPipeError, OSError) as err:
        cap.log(conn, "tx_error", cmd=code, error=repr(err))
        return
    cap.log(conn, "tx", cmd=code, hex=data.hex(" "))


async def open_conn(host: str, port: int, cap: Capture, conn: str):
    t = time.monotonic()
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port), 5
        )
    except (OSError, TimeoutError) as err:
        cap.log(conn, "connect_fail", error=repr(err))
        return None, None
    cap.log(conn, "connected", ms=round((time.monotonic() - t) * 1000, 1))
    return reader, writer


async def close_conn(writer, cap: Capture, conn: str) -> None:
    if writer is None:
        return
    writer.close()
    try:
        await writer.wait_closed()
    except OSError:
        pass
    cap.log(conn, "closed_by_client")


async def main(host: str, port: int, max_idle: float) -> None:
    CAPTURE_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    cap = Capture(CAPTURE_DIR / f"{stamp}-capture.jsonl")
    cap.log("-", "start", host=host, port=port, commands=COMMANDS)

    # --- 1. command sequence on a persistent connection ---------------------
    r1, w1 = await open_conn(host, port, cap, "c1")
    if r1 is None:
        cap.close()
        return
    unsolicited = await read_until_quiet(r1, cap, "c1")  # banner / push?
    cap.log("c1", "pre_cmd", got_bytes=len(unsolicited))
    for code in COMMANDS:
        await send(w1, cap, "c1", code)
        resp = await read_until_quiet(r1, cap, "c1")
        cap.log("c1", "resp_done", cmd=code, total_bytes=len(resp))
        if r1.at_eof():
            cap.log("c1", "aborted", reason="connection closed during sequence")
            break

    # --- 2. second simultaneous connection ----------------------------------
    r2, w2 = await open_conn(host, port, cap, "c2")
    if r2 is not None:
        await send(w2, cap, "c2", "2e")
        resp2 = await read_until_quiet(r2, cap, "c2")
        cap.log("c2", "result", answered=bool(resp2), eof=r2.at_eof())
    # Does c1 still work while / after c2 exists?
    if not r1.at_eof():
        await send(w1, cap, "c1", "2e")
        resp1 = await read_until_quiet(r1, cap, "c1")
        cap.log("c1", "result_with_c2_open", answered=bool(resp1), eof=r1.at_eof())
    await close_conn(w2, cap, "c2")
    if not r1.at_eof():
        await send(w1, cap, "c1", "2e")
        resp1 = await read_until_quiet(r1, cap, "c1")
        cap.log("c1", "result_after_c2", answered=bool(resp1), eof=r1.at_eof())

    # --- 3. idle until the A16 closes the connection ------------------------
    if not r1.at_eof():
        cap.log("c1", "idle_start", max_idle_s=max_idle)
        t_idle = time.monotonic()
        try:
            while True:
                remaining = max_idle - (time.monotonic() - t_idle)
                if remaining <= 0:
                    raise TimeoutError
                chunk = await asyncio.wait_for(r1.read(4096), remaining)
                if not chunk:
                    cap.log(
                        "c1",
                        "idle_eof",
                        idle_s=round(time.monotonic() - t_idle, 1),
                    )
                    break
                cap.log(
                    "c1",
                    "idle_rx",
                    after_s=round(time.monotonic() - t_idle, 1),
                    hex=chunk.hex(" "),
                    fields=split_fields(chunk),
                )
        except TimeoutError:
            cap.log("c1", "idle_no_close", idle_s=max_idle)
        except (ConnectionResetError, OSError) as err:
            cap.log(
                "c1",
                "idle_reset",
                idle_s=round(time.monotonic() - t_idle, 1),
                error=repr(err),
            )
        # Writing to the (possibly) closed socket shows how a client notices.
        await send(w1, cap, "c1", "2e")
        resp = await read_until_quiet(r1, cap, "c1")
        cap.log("c1", "post_idle_write", answered=bool(resp))
    await close_conn(w1, cap, "c1")

    # --- 4. reconnect after timeout ------------------------------------------
    r3, w3 = await open_conn(host, port, cap, "c3")
    if r3 is not None:
        await send(w3, cap, "c3", "2e")
        resp3 = await read_until_quiet(r3, cap, "c3")
        cap.log("c3", "result", answered=bool(resp3))
        await close_conn(w3, cap, "c3")

    cap.log("-", "done")
    cap.close()
    print(f"\nCapture written to {cap.path}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("host")
    ap.add_argument("port", type=int, nargs="?", default=4101)
    ap.add_argument(
        "--max-idle",
        type=float,
        default=300,
        help="seconds to wait for the A16 inactivity timeout (default 300)",
    )
    ap.add_argument(
        "--skip",
        nargs="*",
        default=[],
        help="command codes to leave out of the sequence, e.g. --skip 80 a0",
    )
    args = ap.parse_args()
    COMMANDS = [c for c in COMMANDS if c not in args.skip]
    asyncio.run(main(args.host, args.port, args.max_idle))
