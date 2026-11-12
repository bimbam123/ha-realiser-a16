"""Tests for the state model using real (anonymised) captures."""

from conftest import load_chunks
from pya16.parser import StreamParser, parse_packet
from pya16.state import A16State


def _replay(name: str) -> tuple[A16State, list[set[str]]]:
    state = A16State()
    parser = StreamParser()
    changes = []
    for chunk in load_chunks(name):
        for packet in parser.feed(chunk):
            changes.append(state.apply_packet(packet))
    return state, changes


def test_reference_capture_state():
    s, _ = _replay("run2_reference.jsonl")
    assert s.power == "ON"
    assert s.is_on is True
    assert s.source == "HDMI-1"
    assert s.user_mode == "DUAL"
    assert s.ht_mode == "Gyro"
    assert s.firmware.a16 == "2.17 Jan 26 2024"
    assert s.firmware.serial == "A16HS0000#000000"
    assert s.firmware.head_tracker == "1.40 May 21 2021"

    a, b = s.user_a, s.user_b
    assert (a.name, a.preset, a.volume, a.layout) == ("Listener 1", 6, 64, "12.1.10")
    assert a.tactile is True
    assert a.headphone == "HD800S"  # trailing blanks stripped
    assert a.hpeq_file == "HPEQ File 1"
    assert (b.name, b.preset, b.volume, b.layout) == ("Listener 2", 7, 65, "9.1.6")
    assert b.tactile is None  # BTACT= (empty)

    assert s.assignments_a[1] == "L"
    assert s.assignments_a[16] == "Rtm"
    assert 17 not in s.assignments_a  # ACH17= empty
    assert s.assignments_b[1] == "L"


def test_manual_operation_capture_tracks_changes():
    s, changes = _replay("run1_manual_operation.jsonl")
    assert any("user_a.volume" in c for c in changes)
    assert any("user_a.preset" in c for c in changes)
    assert s.user_a.preset == 6  # final preset after manual switching
    assert s.solo_mute == "SOLO"
    assert s.test == "OFF"
    assert s.mode == "SVS"
    assert {0, 1, 2, 22, 28} <= s.speakers_visible
    assert 22 in s.speakers_active


def test_repeated_push_reports_no_change():
    s, changes = _replay("run2_reference.jsonl")
    # The periodic user A block is identical most of the time.
    assert sum(1 for c in changes if not c) > 50


def test_volume_only_packet():
    s = A16State()
    assert s.apply_packet(parse_packet(b"VA=54")) == {"user_a.volume"}
    assert s.apply_packet(parse_packet(b"VA=54")) == set()
    assert s.apply_packet(parse_packet(b"VB=40\x00TRI=2")) == {
        "user_b.volume",
        "user_a.tri_level",
    }


def test_mute_and_unknown_fields():
    s = A16State()
    assert s.apply_packet(parse_packet(b"MUTEA=MUTE")) == {"user_a.muted"}
    assert s.user_a.muted is True
    assert s.apply_packet(parse_packet(b"MUTEA=OFF")) == {"user_a.muted"}
    assert s.user_a.muted is False
    assert s.apply_packet(parse_packet(b"FOO=1")) == {"extra.FOO"}
    assert s.extra["FOO"] == "1"


def test_invalid_number_is_ignored():
    s = A16State()
    s.apply_packet(parse_packet(b"VA=abc"))
    assert s.user_a.volume is None


def test_speaker_sets_are_replaced_per_packet():
    s = A16State()
    s.apply_packet(parse_packet(b"A00\x00A01\x00M02"))
    assert s.speakers_active == {0, 1}
    assert s.speakers_muted == {2}
    s.apply_packet(parse_packet(b"A00\x00A03"))
    assert s.speakers_active == {0, 3}
    assert s.speakers_muted == frozenset()


def test_levels():
    s = A16State()
    changed = s.apply_packet(parse_packet(b"L1=12\x00L24=00\x00AHL=40\x00BTR=05"))
    assert changed == {"levels"}
    assert s.levels == {"L1": 12, "L24": 0, "AHL": 40, "BTR": 5}
    # LM / AHT are not levels
    s.apply_packet(parse_packet(b"LM=0.0.0\x00AHT=12"))
    assert s.listening_mode == "0.0.0"
    assert s.user_a.ht_angle == "12"
