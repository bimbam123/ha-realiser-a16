"""Loudspeaker IDs of the Realiser A16.

Transcribed from the manufacturer document (May 2020), which contains both
tables only as images:

- Table 3 "Loudspeaker designators against ID numbers": ID -> designator
- Table 4 "A16 LCD Loudspeaker map against ID numbers": 7 x 9 grid with the
  layer colour (floor / height / overhead / under / LFE)

The ``description`` texts are our interpretation of the position in the
Table 3 diagram, not the manufacturer's wording.

Speaker IDs are used by the bare response tokens ``Vnn`` (visible), ``Ann``
(active) and ``Mnn`` (muted) and by the select commands ``b1``-``e2``
(IDs 1-50 only). The ACHn/BCHn fields of command ``37`` use the designators.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Final


class Layer(StrEnum):
    FLOOR = "floor"
    HEIGHT = "height"
    OVERHEAD = "overhead"
    UNDER = "under"
    LFE = "lfe"


@dataclass(frozen=True, slots=True)
class Speaker:
    id: int
    designator: str
    layer: Layer
    description: str
    row: int  # Table 4 grid, 0 = top (screen side)
    col: int  # Table 4 grid, 0 = left

    @property
    def selectable(self) -> bool:
        """True if a select command (b1-e2) exists for this ID."""
        return 1 <= self.id <= 50


F, H, OV, U, S = Layer.FLOOR, Layer.HEIGHT, Layer.OVERHEAD, Layer.UNDER, Layer.LFE

# id: (designator, layer, description, row, col)
_TABLE: Final[dict[int, tuple[str, Layer, str, int, int]]] = {
    1: ("L", F, "front left", 0, 1),
    2: ("R", F, "front right", 0, 7),
    3: ("C", F, "centre", 0, 4),
    4: ("SW", S, "subwoofer, front left corner", 0, 0),
    5: ("Ls", F, "left surround", 4, 0),
    6: ("Rs", F, "right surround", 4, 8),
    7: ("Lb", F, "left back", 6, 1),
    8: ("Rb", F, "right back", 6, 7),
    9: ("Lss", F, "left side surround", 3, 0),
    10: ("Rss", F, "right side surround", 3, 8),
    11: ("Cr", F, "centre rear", 6, 4),
    12: ("SW2", S, "subwoofer 2, front right corner", 0, 8),
    13: ("Lw", F, "left wide", 1, 0),
    14: ("Rw", F, "right wide", 1, 8),
    15: ("Lbs", F, "left back surround", 6, 3),
    16: ("Rbs", F, "right back surround", 6, 5),
    17: ("Lc", F, "left centre", 0, 2),
    18: ("Rc", F, "right centre", 0, 6),
    19: ("Lu", U, "left under, front", 2, 3),
    20: ("Ru", U, "right under, front", 2, 5),
    21: ("Cu", U, "centre under", 2, 4),
    22: ("Ch", H, "centre height, front", 1, 4),
    23: ("Chr", H, "centre height, rear", 5, 4),
    24: ("T", OV, "top, above the listener", 3, 4),
    25: ("Lh", H, "left height, front", 1, 2),
    26: ("Rh", H, "right height, front", 1, 6),
    27: ("Lhs", H, "left height side", 3, 1),
    28: ("Rhs", H, "right height side", 3, 7),
    29: ("Lhr", H, "left height rear", 5, 2),
    30: ("Rhr", H, "right height rear", 5, 6),
    31: ("Ltf", OV, "left top front", 2, 2),
    32: ("Rtf", OV, "right top front", 2, 6),
    33: ("Ltm", OV, "left top middle", 3, 2),
    34: ("Rtm", OV, "right top middle", 3, 6),
    35: ("Ltr", OV, "left top rear", 4, 2),
    36: ("Rtr", OV, "right top rear", 4, 6),
    37: ("Lsc", F, "left screen centre", 0, 3),
    38: ("Rsc", F, "right screen centre", 0, 5),
    39: ("Ls1", F, "left surround 1 (front of Lss)", 2, 0),
    40: ("Rs1", F, "right surround 1 (front of Rss)", 2, 8),
    41: ("Lrs1", F, "left rear surround 1", 5, 0),
    42: ("Rrs1", F, "right rear surround 1", 5, 8),
    43: ("Lrs2", F, "left rear surround 2", 6, 2),
    44: ("Rrs2", F, "right rear surround 2", 6, 6),
    45: ("Lhw", H, "left height wide", 1, 1),
    46: ("Rhw", H, "right height wide", 1, 7),
    47: ("Lhs1", H, "left height side 1", 4, 1),
    48: ("Rhs1", H, "right height side 1", 4, 7),
    49: ("Lbu", U, "left back under", 5, 3),
    50: ("Rbu", U, "right back under", 5, 5),
    51: ("SW", S, "subwoofer, rear left corner", 6, 0),
    52: ("SW", S, "subwoofer, rear right corner", 6, 8),
}

SPEAKERS: Final[dict[int, Speaker]] = {
    sid: Speaker(sid, d, layer, desc, row, col)
    for sid, (d, layer, desc, row, col) in _TABLE.items()
}

GRID_ROWS: Final = 7
GRID_COLS: Final = 9

# Designator -> ID. "SW" is ambiguous (4, 51, 52); it maps to 4, the main one.
BY_DESIGNATOR: Final[dict[str, int]] = {}
for _s in sorted(SPEAKERS.values(), key=lambda s: s.id):
    BY_DESIGNATOR.setdefault(_s.designator, _s.id)


def grid() -> list[list[Speaker | None]]:
    """Table 4 as rows of columns (None = empty cell)."""
    cells: list[list[Speaker | None]] = [[None] * GRID_COLS for _ in range(GRID_ROWS)]
    for s in SPEAKERS.values():
        cells[s.row][s.col] = s
    return cells
