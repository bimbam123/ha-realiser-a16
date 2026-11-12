"""Minimal TCP client for the Realiser A16 IP command server.

This module must not import anything from Home Assistant so it can be tested
standalone. The full persistent client (queue, reconnect, push handling) will
be built here; for now it only offers a one-shot firmware/serial query used by
the config flow.

Protocol summary (see docs/protocol.md):
- command: two ASCII hex characters followed by ``\\r\\n``
- response: one or more ``KEY=VALUE`` fields, each terminated by ``\\x00``
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

CMD_FIRMWARE_INFO = "64"

TERMINATOR = b"\r\n"
FIELD_SEPARATOR = b"\x00"


class A16Error(Exception):
    """Base error for the A16 client."""


class A16ConnectionError(A16Error):
    """The A16 could not be reached or did not answer in time."""


@dataclass(frozen=True, slots=True)
class A16DeviceInfo:
    """Identity data returned by command 64."""

    serial: str
    firmware: str | None
    apm_firmware: str | None
    hsr_firmware: str | None
    ht_firmware: str | None


def encode_command(code: str) -> bytes:
    """Encode a two-digit hex command code for transmission."""
    if len(code) != 2 or any(c not in "0123456789abcdefABCDEF" for c in code):
        raise ValueError(f"Invalid A16 command code: {code!r}")
    return code.encode("ascii") + TERMINATOR


def parse_fields(buffer: bytearray) -> list[tuple[str, str]]:
    """Consume complete ``KEY=VALUE\\x00`` fields from ``buffer``.

    Incomplete trailing data stays in the buffer for the next read.
    """
    fields: list[tuple[str, str]] = []
    while (idx := buffer.find(FIELD_SEPARATOR)) != -1:
        raw = bytes(buffer[:idx]).decode("ascii", errors="replace").strip()
        del buffer[: idx + 1]
        if not raw:
            continue
        key, sep, value = raw.partition("=")
        if sep:
            fields.append((key.strip(), value.strip()))
    return fields


async def async_get_device_info(
    host: str, port: int, timeout: float = 5.0
) -> A16DeviceInfo:
    """Connect once, request firmware info and return the device identity."""
    try:
        async with asyncio.timeout(timeout):
            reader, writer = await asyncio.open_connection(host, port)
    except (OSError, TimeoutError) as err:
        raise A16ConnectionError(f"Cannot connect to {host}:{port}") from err

    data: dict[str, str] = {}
    buffer = bytearray()
    try:
        writer.write(encode_command(CMD_FIRMWARE_INFO))
        await writer.drain()
        async with asyncio.timeout(timeout):
            while "A16SN" not in data:
                chunk = await reader.read(1024)
                if not chunk:
                    break
                buffer.extend(chunk)
                data.update(parse_fields(buffer))
    except (OSError, TimeoutError) as err:
        raise A16ConnectionError(f"No valid answer from {host}:{port}") from err
    finally:
        writer.close()
        try:
            await writer.wait_closed()
        except OSError:
            pass

    if not data.get("A16SN"):
        raise A16ConnectionError(f"No serial number received from {host}:{port}")

    return A16DeviceInfo(
        serial=data["A16SN"],
        firmware=data.get("A16FW"),
        apm_firmware=data.get("APMFW"),
        hsr_firmware=data.get("HSRFW"),
        ht_firmware=data.get("HTFW"),
    )
