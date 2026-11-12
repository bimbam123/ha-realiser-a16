"""State model of a Realiser A16, updated from response packets."""

from __future__ import annotations

import logging
import re
from collections.abc import Callable
from dataclasses import dataclass, field, fields

from .parser import Packet

_LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class UserState:
    """Per-user (A or B) settings."""

    name: str | None = None
    preset: int | None = None
    volume: int | None = None
    tri_level: int | None = None
    muted: bool | None = None
    room: str | None = None
    subject: str | None = None
    layout: str | None = None
    hpeq_file: str | None = None
    hpeq_subject: str | None = None
    hpeq_date: str | None = None
    hpeq_type: str | None = None
    headphone: str | None = None
    tactile: bool | None = None
    ht_angle: str | None = None


@dataclass(slots=True)
class FirmwareInfo:
    a16: str | None = None
    apm: str | None = None
    hsr: str | None = None
    head_tracker: str | None = None
    serial: str | None = None


@dataclass(slots=True)
class A16State:
    """Everything known about the device. ``None`` = not reported yet."""

    power: str | None = None  # ON / STANDBY / BOOT
    source: str | None = None  # IN=
    decoder: str | None = None
    listening_mode: str | None = None
    upmixer: str | None = None
    ht_mode: str | None = None
    legacy: str | None = None
    user_mode: str | None = None  # SINGLE / DUAL
    mode: str | None = None  # SVS / AV / MIX
    solo_mute: str | None = None  # ALL=SOLO / MUTE
    test: str | None = None  # LOOP / OFF
    head_tracking: str | None = None  # HT=ACTIVE / OFF
    page: int | None = None
    last_key: str | None = None
    firmware: FirmwareInfo = field(default_factory=FirmwareInfo)
    user_a: UserState = field(default_factory=UserState)
    user_b: UserState = field(default_factory=UserState)
    assignments_a: dict[int, str] = field(default_factory=dict)
    assignments_b: dict[int, str] = field(default_factory=dict)
    levels: dict[str, int] = field(default_factory=dict)
    speakers_visible: frozenset[int] = frozenset()
    speakers_active: frozenset[int] = frozenset()
    speakers_muted: frozenset[int] = frozenset()
    extra: dict[str, str | None] = field(default_factory=dict)

    @property
    def is_on(self) -> bool | None:
        return None if self.power is None else self.power == "ON"

    def user(self, user: str) -> UserState:
        return self.user_a if user == "a" else self.user_b

    def apply_packet(self, packet: Packet) -> set[str]:
        """Apply one packet and return the dotted paths of changed values."""
        changed: set[str] = set()
        visible: set[int] | None = None
        active: set[int] | None = None
        muted: set[int] | None = None

        for f in packet:
            if f.value is None:
                m = _BARE.match(f.key)
                if not m:
                    self._set_extra(f.key, None, changed)
                    continue
                kind, num = m.group(1), int(m.group(2))
                if kind == "V":
                    visible = (visible or set()) | {num}
                elif kind == "A":
                    active = (active or set()) | {num}
                else:
                    muted = (muted or set()) | {num}
                continue
            self._apply_field(f.key, f.value, changed)

        # Bare token lists describe the complete set within one packet.
        if visible is not None:
            self._set(self, "speakers_visible", frozenset(visible), changed, "")
        if active is not None or muted is not None:
            self._set(self, "speakers_active", frozenset(active or ()), changed, "")
            self._set(self, "speakers_muted", frozenset(muted or ()), changed, "")
        return changed

    # --- internals ----------------------------------------------------------

    def _apply_field(self, key: str, value: str, changed: set[str]) -> None:
        if key in _GLOBAL:
            attr, conv = _GLOBAL[key]
            self._set(self, attr, conv(value), changed, "")
            return
        if key in _FIRMWARE:
            self._set(self.firmware, _FIRMWARE[key], _text(value), changed, "firmware.")
            return
        if key in _USER_KEYS:
            user, attr, conv = _USER_KEYS[key]
            target = self.user_a if user == "a" else self.user_b
            self._set(target, attr, conv(value), changed, f"user_{user}.")
            return
        if m := _ASSIGN.match(key):
            target = self.assignments_a if m.group(1) == "A" else self.assignments_b
            path = "assignments_a" if m.group(1) == "A" else "assignments_b"
            ch, val = int(m.group(2)), _text(value)
            if target.get(ch) != val:
                if val is None:
                    target.pop(ch, None)
                else:
                    target[ch] = val
                changed.add(path)
            return
        if _LEVEL.match(key):
            num = _int(value)
            if num is not None and self.levels.get(key) != num:
                self.levels[key] = num
                changed.add("levels")
            return
        self._set_extra(key, value, changed)

    def _set_extra(self, key: str, value: str | None, changed: set[str]) -> None:
        if key not in self.extra:
            _LOGGER.debug("Unknown A16 field %r=%r", key, value)
        if key not in self.extra or self.extra[key] != value:
            self.extra[key] = value
            changed.add(f"extra.{key}")

    @staticmethod
    def _set(obj: object, attr: str, value: object, changed: set[str], prefix: str):
        if getattr(obj, attr) != value:
            setattr(obj, attr, value)
            changed.add(prefix + attr)

    def as_dict(self) -> dict:
        """Plain dict for display/debugging."""

        def conv(v):
            if isinstance(v, (UserState, FirmwareInfo)):
                return {f.name: getattr(v, f.name) for f in fields(v)}
            if isinstance(v, frozenset):
                return sorted(v)
            return v

        return {f.name: conv(getattr(self, f.name)) for f in fields(self)}


def _text(value: str) -> str | None:
    value = value.strip()
    return value or None


def _int(value: str) -> int | None:
    try:
        return int(value.strip())
    except ValueError:
        _LOGGER.debug("Expected integer, got %r", value)
        return None


def _on_off(value: str) -> bool | None:
    v = value.strip().upper()
    if v in ("ON", "MUTE"):
        return True
    if v == "OFF":
        return False
    return None


_GLOBAL: dict[str, tuple[str, Callable[[str], object]]] = {
    "PWR": ("power", _text),
    "IN": ("source", _text),
    "DEC": ("decoder", _text),
    "LM": ("listening_mode", _text),
    "UMIX": ("upmixer", _text),
    "HTMODE": ("ht_mode", _text),
    "LEG": ("legacy", _text),
    "USER": ("user_mode", _text),
    "MODE": ("mode", _text),
    "ALL": ("solo_mute", _text),
    "TEST": ("test", _text),
    "HT": ("head_tracking", _text),
    "PAGE": ("page", _int),
    "KEY": ("last_key", _text),
}

_FIRMWARE = {
    "A16FW": "a16",
    "APMFW": "apm",
    "HSRFW": "hsr",
    "HTFW": "head_tracker",
    "A16SN": "serial",
}

_USER_FIELDS: dict[str, tuple[str, Callable[[str], object]]] = {
    "UR": ("name", _text),
    "ROOM": ("room", _text),
    "NAME": ("subject", _text),
    "SPKR": ("layout", _text),
    "QFILE": ("hpeq_file", _text),
    "QNAME": ("hpeq_subject", _text),
    "QDATE": ("hpeq_date", _text),
    "QTYPE": ("hpeq_type", _text),
    "QMOD": ("headphone", _text),
    "TACT": ("tactile", _on_off),
    "HT": ("ht_angle", _text),
}

_USER_KEYS: dict[str, tuple[str, str, Callable[[str], object]]] = {}
for _suffix, (_attr, _conv) in _USER_FIELDS.items():
    _USER_KEYS["A" + _suffix] = ("a", _attr, _conv)
    _USER_KEYS["B" + _suffix] = ("b", _attr, _conv)
_USER_KEYS.update(
    {
        "PA": ("a", "preset", _int),
        "PB": ("b", "preset", _int),
        "VA": ("a", "volume", _int),
        "VB": ("b", "volume", _int),
        "TRI": ("a", "tri_level", _int),
        "MUTEA": ("a", "muted", _on_off),
        "MUTEB": ("b", "muted", _on_off),
    }
)

_BARE = re.compile(r"^([VAM])(\d{2})$")
_ASSIGN = re.compile(r"^([AB])CH(\d+)$")
_LEVEL = re.compile(r"^(L\d+|[AB][HT][LR])$")
