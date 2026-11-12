"""Command line tool for trying pya16 against a real A16.

Run via ``python tools/a16_cli.py <host> [--port N] <command> ...``.

Commands:
  state                    refresh once and print the full state
  monitor [--seconds N]    print every state change (Ctrl+C to stop)
  send <code>              send a raw two-digit command code
  power on|off             power on / standby
  source <name>            select input (eARC, HDMI-1 ... OPTICAL)
  preset a|b <1-16>        select preset for user A or B
  volume a|b <27-99>       step volume of user A or B to the target
  key <name>               send an IR remote key (see protocol.IR_KEYS)
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import time

from .client import A16Client, A16Error
from .protocol import DEFAULT_PORT, IR_KEYS, SOURCES


def _print_change(state, changed: set[str]) -> None:
    data = state.as_dict()
    parts = []
    for path in sorted(changed):
        value = data
        for part in path.split("."):
            value = value.get(part) if isinstance(value, dict) else None
        parts.append(f"{path}={value!r}")
    print(f"{time.strftime('%H:%M:%S')} " + ", ".join(parts))


async def _run(args: argparse.Namespace) -> int:
    client = A16Client(
        args.host, args.port, refresh_on_connect=args.command in ("state", "monitor")
    )
    await client.start()
    try:
        await client.wait_connected(timeout=10)
        cmd = args.command
        if cmd == "state":
            await client.refresh()
            print(json.dumps(client.state.as_dict(), indent=2, ensure_ascii=False))
        elif cmd == "monitor":
            client.add_listener(_print_change)
            client.add_connection_listener(
                lambda up: print(f"{time.strftime('%H:%M:%S')} connected={up}")
            )
            await asyncio.sleep(args.seconds if args.seconds else 10**9)
        elif cmd == "send":
            print(await client.send_command(args.code))
        elif cmd == "power":
            await (client.power_on() if args.value == "on" else client.standby())
            print("power:", client.state.power)
        elif cmd == "source":
            await client.select_source(args.name)
            print("source:", client.state.source)
        elif cmd == "preset":
            await client.select_preset(args.user, args.number)
            print("preset:", client.state.user(args.user).preset)
        elif cmd == "volume":
            await client.set_volume(args.user, args.number)
            print("volume:", client.state.user(args.user).volume)
        elif cmd == "key":
            await client.press_key(args.name)
            print("ok")
        return 0
    except A16Error as err:
        print(f"Error: {err}")
        return 1
    finally:
        await client.stop()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="a16_cli", description="Realiser A16 test CLI")
    ap.add_argument("host")
    ap.add_argument("--port", type=int, default=DEFAULT_PORT)
    ap.add_argument("-v", "--verbose", action="store_true", help="debug logging")
    sub = ap.add_subparsers(dest="command", required=True)
    sub.add_parser("state")
    p = sub.add_parser("monitor")
    p.add_argument("--seconds", type=float, default=0)
    p = sub.add_parser("send")
    p.add_argument("code")
    p = sub.add_parser("power")
    p.add_argument("value", choices=["on", "off"])
    p = sub.add_parser("source")
    p.add_argument("name", choices=list(SOURCES), type=str)
    p = sub.add_parser("preset")
    p.add_argument("user", choices=["a", "b"])
    p.add_argument("number", type=int)
    p = sub.add_parser("volume")
    p.add_argument("user", choices=["a", "b"])
    p.add_argument("number", type=int)
    p = sub.add_parser("key")
    p.add_argument("name", choices=list(IR_KEYS))
    args = ap.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    try:
        return asyncio.run(_run(args))
    except KeyboardInterrupt:
        return 130
