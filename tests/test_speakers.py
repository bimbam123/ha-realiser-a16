"""Speaker table checks (Table 3 / Table 4 of the manufacturer document)."""

from pya16.speakers import BY_DESIGNATOR, GRID_COLS, GRID_ROWS, SPEAKERS, Layer, grid

# Table 4, transcribed row by row from the image a second time (0 = empty).
TABLE_4 = [
    [4, 1, 17, 37, 3, 38, 18, 2, 12],
    [13, 45, 25, 0, 22, 0, 26, 46, 14],
    [39, 0, 31, 19, 21, 20, 32, 0, 40],
    [9, 27, 33, 0, 24, 0, 34, 28, 10],
    [5, 47, 35, 0, 0, 0, 36, 48, 6],
    [41, 0, 29, 49, 23, 50, 30, 0, 42],
    [51, 7, 43, 15, 11, 16, 44, 8, 52],
]

# Table 4 legend colours, read from the image.
LAYERS = {
    Layer.LFE: {4, 12, 51, 52},
    Layer.UNDER: {19, 20, 21, 49, 50},
    Layer.OVERHEAD: {24, 31, 32, 33, 34, 35, 36},
    Layer.HEIGHT: {22, 23, 25, 26, 27, 28, 29, 30, 45, 46, 47, 48},
}


def test_all_ids_once():
    assert sorted(SPEAKERS) == list(range(1, 53))
    flat = [i for row in TABLE_4 for i in row if i]
    assert sorted(flat) == list(range(1, 53))


def test_grid_matches_second_transcription():
    cells = grid()
    assert len(cells) == GRID_ROWS
    for r in range(GRID_ROWS):
        assert len(cells[r]) == GRID_COLS
        assert [c.id if c else 0 for c in cells[r]] == TABLE_4[r], f"row {r}"


def test_layers():
    for sid, s in SPEAKERS.items():
        expected = next((ly for ly, ids in LAYERS.items() if sid in ids), Layer.FLOOR)
        assert s.layer == expected, sid


def test_designators_and_selectable():
    assert SPEAKERS[1].designator == "L"
    assert SPEAKERS[24].designator == "T"
    assert SPEAKERS[50].designator == "Rbu"
    assert BY_DESIGNATOR["Rtm"] == 34
    assert BY_DESIGNATOR["SW"] == 4
    assert SPEAKERS[50].selectable and not SPEAKERS[51].selectable
    # designators are unique apart from the three subwoofers named "SW"
    names = [s.designator for s in SPEAKERS.values() if s.designator != "SW"]
    assert len(names) == len(set(names))
