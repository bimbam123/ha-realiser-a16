"""Constants for the Smyth Realiser A16 integration."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "realiser_a16"
MANUFACTURER: Final = "Smyth Research"
MODEL: Final = "Realiser A16"

DEFAULT_PORT: Final = 4101
MIN_PORT: Final = 512
MAX_PORT: Final = 65535

# Seconds to wait for the connection in the config flow and on setup.
CONNECT_TIMEOUT: Final = 10.0

# Value of the A16 IN= field -> name shown in Home Assistant.
SOURCE_NAMES: Final[dict[str, str]] = {
    "eARC": "eARC",
    "HDMI-1": "HDMI 1",
    "HDMI-2": "HDMI 2",
    "HDMI-3": "HDMI 3",
    "HDMI-4": "HDMI 4",
    "USB": "USB",
    "LINE": "Line",
    "STEREO": "Stereo",
    "COAXIAL": "Coaxial",
    "OPTICAL": "Optical",
}

# State paths (see pya16.state) that entities use. Other changes (level
# meters, unknown fields, speaker sets) do not notify Home Assistant.
RELEVANT_PATHS: Final = frozenset(
    {
        "power",
        "source",
        "mode",
        "ht_mode",
        "firmware.a16",
        "firmware.serial",
        "user_a.name",
        "user_a.preset",
        "user_a.volume",
        "user_a.muted",
        "user_a.room",
        "user_a.subject",
        "user_a.layout",
        "user_b.name",
        "user_b.preset",
        "user_b.volume",
        "user_b.muted",
        "user_b.room",
        "user_b.subject",
        "user_b.layout",
    }
)

USERS: Final = ("a", "b")

# A volume target gives up after this many steps that changed nothing.
VOLUME_MAX_FAILED_STEPS: Final = 5
# User B info (room/subject) is not pushed; query it this long after PB changed.
USER_B_INFO_DELAY: Final = 2.0
