"""Stream parser for A16 responses.

Wire format (FW 2.17): fields ``KEY=VALUE`` or bare tokens (``V01``), each
terminated by ``\\x00``; every packet ends with ``\\x00\\r``. Packets can be
split or concatenated arbitrarily by TCP, so the parser buffers.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from .protocol import FIELD_SEPARATOR, PACKET_TERMINATOR

_LOGGER = logging.getLogger(__name__)

# Guard against a device that never sends the packet terminator.
MAX_BUFFER = 64 * 1024


@dataclass(frozen=True, slots=True)
class Field:
    """One response field. ``value`` is None for bare tokens like ``V01``."""

    key: str
    value: str | None

    def __str__(self) -> str:
        return self.key if self.value is None else f"{self.key}={self.value}"


Packet = list[Field]


def parse_field(raw: bytes) -> Field | None:
    """Parse one field; returns None for empty fields."""
    text = raw.decode("ascii", "replace").strip("\r\n")
    if not text.strip():
        return None
    key, sep, value = text.partition("=")
    key = key.strip()
    if not key:
        return None
    return Field(key, value.strip() if sep else None)


def parse_packet(raw: bytes) -> Packet:
    """Parse the fields of one packet (without terminator)."""
    fields = (parse_field(part) for part in raw.split(FIELD_SEPARATOR))
    return [f for f in fields if f is not None]


class StreamParser:
    """Turns a TCP byte stream into packets."""

    def __init__(self) -> None:
        self._buffer = bytearray()

    def feed(self, data: bytes) -> list[Packet]:
        """Add received bytes and return all packets completed by them."""
        self._buffer.extend(data)
        packets: list[Packet] = []
        while (idx := self._buffer.find(PACKET_TERMINATOR)) != -1:
            raw = bytes(self._buffer[:idx])
            del self._buffer[: idx + len(PACKET_TERMINATOR)]
            if packet := parse_packet(raw):
                packets.append(packet)
        if len(self._buffer) > MAX_BUFFER:
            _LOGGER.warning(
                "No packet terminator in %d bytes, flushing buffer", len(self._buffer)
            )
            packets.extend(self.flush())
        return packets

    def flush(self) -> list[Packet]:
        """Return whatever is buffered as one packet (e.g. on disconnect)."""
        raw = bytes(self._buffer)
        self._buffer.clear()
        packet = parse_packet(raw)
        return [packet] if packet else []

    def reset(self) -> None:
        self._buffer.clear()
