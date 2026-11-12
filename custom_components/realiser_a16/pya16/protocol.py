"""Command codes and protocol constants of the Realiser A16 IP command server.

Source: "Realiser A16 IP (TCP) Command Summary" (May 2020) plus observations on
FW 2.17, see docs/protocol.md.
"""

from __future__ import annotations

from typing import Final, Literal

User = Literal["a", "b"]

DEFAULT_PORT: Final = 4101
COMMAND_TERMINATOR: Final = b"\r\n"
FIELD_SEPARATOR: Final = b"\x00"
# FW 2.17 terminates every packet with "\x00\r" (the PDF only mentions "\x00").
PACKET_TERMINATOR: Final = b"\x00\r"

VOLUME_MIN: Final = 27
VOLUME_MAX: Final = 99
PRESET_MIN: Final = 1
PRESET_MAX: Final = 16
SPEAKER_ID_MIN: Final = 1
SPEAKER_ID_MAX: Final = 50

# --- Non-IR commands (table 2) ----------------------------------------------
CMD_POWER_ON: Final = "2c"
CMD_STANDBY: Final = "2d"
CMD_POWER_STATUS: Final = "2e"
CMD_ASSIGNMENTS: Final = "37"
CMD_RESET_METERS: Final = "38"
CMD_FIRMWARE: Final = "64"
CMD_LEVELS: Final = "6a"
CMD_USER_A_INFO: Final = "80"
CMD_USER_A_VOLUME: Final = "83"
CMD_USER_A_HT_ANGLE: Final = "85"
CMD_USER_B_INFO: Final = "a0"
CMD_USER_B_VOLUME: Final = "a3"
CMD_USER_B_HT_ANGLE: Final = "a5"
CMD_SPEAKER_VISIBILITY: Final = "ae"
CMD_SPEAKER_STATUS: Final = "af"

# Value of the IN= field -> command code.
SOURCES: Final[dict[str, str]] = {
    "eARC": "20",
    "HDMI-1": "21",
    "HDMI-2": "22",
    "HDMI-3": "23",
    "HDMI-4": "24",
    "USB": "25",
    "LINE": "26",
    "STEREO": "27",
    "COAXIAL": "28",
    "OPTICAL": "29",
}

# --- IR remote keys (table 1) -----------------------------------------------
IR_KEYS: Final[dict[str, str]] = {
    "power": "11",
    "menu": "43",
    "back": "59",
    "enter": "04",
    "cancel": "50",
    "adj_up": "56",
    "adj_down": "5a",
    "up": "47",
    "down": "4b",
    "left": "57",
    "right": "53",
    "1": "5d",
    "2": "5f",
    "3": "49",
    "4": "16",
    "5": "17",
    "6": "44",
    "7": "55",
    "8": "0f",
    "9": "0e",
    "0": "5b",
    "star": "12",
    "hash": "36",
    "cal": "03",
    "spk": "0b",
    "hp": "0a",
    "c": "1c",
    "l": "1d",
    "r": "46",
    "lw": "0d",
    "rw": "0c",
    "ls": "15",
    "rs": "45",
    "lb": "00",
    "rb": "1b",
    "lfe": "4c",
    "oh": "14",
    "all": "1a",
    "headphone": "4d",
    "speaker": "5e",
    "volume_a_up": "30",
    "volume_a_down": "31",
    "volume_b_up": "33",
    "volume_b_down": "34",
    "mute_a": "32",
    "mute_b": "35",
    "test": "08",
    "ht": "42",
    "pa": "58",
    "pb": "54",
}

VOLUME_UP: Final[dict[User, str]] = {"a": "30", "b": "33"}
VOLUME_DOWN: Final[dict[User, str]] = {"a": "31", "b": "34"}
MUTE_TOGGLE: Final[dict[User, str]] = {"a": "32", "b": "35"}
VOLUME_QUERY: Final[dict[User, str]] = {"a": CMD_USER_A_VOLUME, "b": CMD_USER_B_VOLUME}
INFO_QUERY: Final[dict[User, str]] = {"a": CMD_USER_A_INFO, "b": CMD_USER_B_INFO}

# Commands sent by A16Client.refresh().
REFRESH_COMMANDS: Final = (
    CMD_POWER_STATUS,
    CMD_FIRMWARE,
    CMD_USER_A_INFO,
    CMD_USER_A_VOLUME,
    CMD_USER_B_INFO,
    CMD_USER_B_VOLUME,
    CMD_ASSIGNMENTS,
)

_SPECIAL_IR_RESPONSES: Final[dict[str, tuple[str, ...]]] = {
    "59": ("PAGE",),
    "1a": ("ALL",),
    "4d": ("MODE",),
    "5e": ("MODE",),
    "30": ("VA",),
    "31": ("VA",),
    "33": ("VB",),
    "34": ("VB",),
    "32": ("MUTEA",),
    "35": ("MUTEB",),
    "08": ("TEST",),
    "42": ("HT",),
}

_FIXED_RESPONSES: Final[dict[str, tuple[str, ...]]] = {
    CMD_POWER_ON: ("PWR",),
    CMD_STANDBY: ("PWR",),
    CMD_POWER_STATUS: ("PWR",),
    CMD_ASSIGNMENTS: ("ACH1",),
    CMD_RESET_METERS: ("L1",),
    CMD_FIRMWARE: ("A16SN", "A16FW"),
    CMD_LEVELS: ("L1",),
    CMD_USER_A_INFO: ("AUR",),
    CMD_USER_A_VOLUME: ("VA",),
    CMD_USER_A_HT_ANGLE: ("AHT",),
    CMD_USER_B_INFO: ("BUR",),
    CMD_USER_B_VOLUME: ("VB",),
    CMD_USER_B_HT_ANGLE: ("BHT",),
}


def normalize_code(code: str) -> str:
    """Validate a two-digit hex command code and return it in lower case."""
    if (
        not isinstance(code, str)
        or len(code) != 2
        or any(c not in "0123456789abcdefABCDEF" for c in code)
    ):
        raise ValueError(f"Invalid A16 command code: {code!r}")
    return code.lower()


def encode_command(code: str) -> bytes:
    """Encode a command code for transmission (``"2e"`` -> ``b"2e\\r\\n"``)."""
    return normalize_code(code).encode("ascii") + COMMAND_TERMINATOR


def preset_command(user: User, preset: int) -> str:
    """Command code selecting preset 1-16 for user A or B."""
    if not PRESET_MIN <= preset <= PRESET_MAX:
        raise ValueError(f"Preset must be {PRESET_MIN}-{PRESET_MAX}, got {preset}")
    base = 0x70 if user == "a" else 0x90
    return f"{base + preset - 1:02x}"


def speaker_command(speaker_id: int) -> str:
    """Command code selecting speaker ID 1-50 (solo/mute)."""
    if not SPEAKER_ID_MIN <= speaker_id <= SPEAKER_ID_MAX:
        raise ValueError(f"Speaker ID must be 1-50, got {speaker_id}")
    return f"{0xB0 + speaker_id:02x}"


def is_idempotent(code: str) -> bool:
    """True if sending ``code`` twice has the same effect as sending it once.

    Queries, power on/standby, source and preset selection are; IR keys
    (toggles, volume steps, menu navigation) and speaker selection are not.
    """
    code = normalize_code(code)
    value = int(code, 16)
    return (
        code in _FIXED_RESPONSES
        or code in SOURCES.values()
        or 0x70 <= value <= 0x7F
        or 0x90 <= value <= 0x9F
        or code in (CMD_SPEAKER_VISIBILITY, CMD_SPEAKER_STATUS)
    ) and code != CMD_RESET_METERS


def expected_keys(code: str) -> tuple[str, ...]:
    """Response keys that confirm ``code`` was processed (empty if unknown)."""
    code = normalize_code(code)
    if code in _FIXED_RESPONSES:
        return _FIXED_RESPONSES[code]
    if code in _SPECIAL_IR_RESPONSES:
        return _SPECIAL_IR_RESPONSES[code]
    value = int(code, 16)
    if code in SOURCES.values():
        return ("IN",)
    if 0x70 <= value <= 0x7F:
        return ("PA",)
    if 0x90 <= value <= 0x9F:
        return ("PB",)
    if code in IR_KEYS.values():
        return ("KEY",)
    return ()
