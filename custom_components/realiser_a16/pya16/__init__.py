"""pya16 - asyncio client for the Smyth Realiser A16 IP command server.

Unofficial. Has no dependency on Home Assistant (stdlib only) and uses only
relative imports, so it can be extracted into its own package later.
"""

from .client import (
    A16Client,
    A16ConnectionError,
    A16Error,
    A16Stats,
    A16TimeoutError,
)
from .parser import Field, Packet, StreamParser
from .protocol import DEFAULT_PORT, IR_KEYS, SOURCES
from .speakers import SPEAKERS, Layer, Speaker
from .state import A16State, FirmwareInfo, UserState

__all__ = [
    "DEFAULT_PORT",
    "IR_KEYS",
    "SPEAKERS",
    "SOURCES",
    "A16Client",
    "A16ConnectionError",
    "A16Error",
    "A16State",
    "A16Stats",
    "A16TimeoutError",
    "Field",
    "FirmwareInfo",
    "Layer",
    "Packet",
    "Speaker",
    "StreamParser",
    "UserState",
]
