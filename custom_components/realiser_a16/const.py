"""Constants for the Smyth Realiser A16 integration."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "realiser_a16"

DEFAULT_PORT: Final = 4101
MIN_PORT: Final = 512
MAX_PORT: Final = 65535

# Seconds to wait for the A16 to answer during the config flow connection test.
CONNECT_TIMEOUT: Final = 5.0
