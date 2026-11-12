"""Glue between Home Assistant and the pya16 library (no HA imports here)."""

from __future__ import annotations

from dataclasses import dataclass

from .pya16 import A16Client, A16ConnectionError, A16Error, A16TimeoutError
from .pya16.protocol import CMD_FIRMWARE

__all__ = [
    "A16Client",
    "A16ConnectionError",
    "A16DeviceInfo",
    "A16Error",
    "async_get_device_info",
]


@dataclass(frozen=True, slots=True)
class A16DeviceInfo:
    """Identity data returned by command 64."""

    serial: str
    firmware: str | None
    apm_firmware: str | None
    hsr_firmware: str | None
    ht_firmware: str | None


async def async_get_device_info(
    host: str, port: int, timeout: float = 5.0
) -> A16DeviceInfo:
    """Connect once, request firmware info and return the device identity.

    Note: the A16 accepts only one client. If another controller (or this
    integration) holds the connection, this raises A16ConnectionError.
    """
    client = A16Client(host, port, refresh_on_connect=False, connect_timeout=timeout)
    await client.start()
    try:
        await client.wait_connected(timeout)
        try:
            await client.send_command(CMD_FIRMWARE, timeout=timeout)
        except A16TimeoutError as err:
            raise A16ConnectionError(f"No answer from {host}:{port}") from err
    finally:
        await client.stop()

    fw = client.state.firmware
    if not fw.serial:
        raise A16ConnectionError(f"No serial number received from {host}:{port}")
    return A16DeviceInfo(
        serial=fw.serial,
        firmware=fw.a16,
        apm_firmware=fw.apm,
        hsr_firmware=fw.hsr,
        ht_firmware=fw.head_tracker,
    )
