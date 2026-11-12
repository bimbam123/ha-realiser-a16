"""Tests for the stream parser using real (anonymised) captures."""

from conftest import load_chunks
from pya16.parser import Field, StreamParser, parse_field

FIXTURES = ["run1_manual_operation.jsonl", "run2_reference.jsonl"]


def _all_packets(chunks, step=None):
    parser = StreamParser()
    packets = []
    for chunk in chunks:
        if step is None:
            packets += parser.feed(chunk)
        else:
            for i in range(0, len(chunk), step):
                packets += parser.feed(chunk[i : i + step])
    return packets


def test_every_chunk_ends_with_terminator():
    for name in FIXTURES:
        for chunk in load_chunks(name):
            assert chunk.endswith(b"\x00\r")


def test_fragmented_stream_gives_same_packets():
    chunks = load_chunks("run2_reference.jsonl")
    whole = _all_packets(chunks)
    assert whole
    for step in (1, 3, 7, 50):
        assert _all_packets(chunks, step) == whole


def test_concatenated_stream_gives_same_packets():
    chunks = load_chunks("run1_manual_operation.jsonl")
    assert _all_packets([b"".join(chunks)]) == _all_packets(chunks)


def test_no_carriage_returns_or_empty_fields_leak():
    for name in FIXTURES:
        for packet in _all_packets(load_chunks(name)):
            for f in packet:
                assert "\r" not in f.key
                assert f.key
                assert f.value is None or "\r" not in f.value


def test_bare_tokens_are_kept():
    # The V../A.. speaker block only appears in the manual-operation capture.
    packets = _all_packets(load_chunks("run1_manual_operation.jsonl"))
    keys = {f.key for p in packets for f in p if f.value is None}
    assert {"V00", "V01", "A00", "A28"} <= keys


def test_firmware_packet():
    packets = _all_packets(load_chunks("run2_reference.jsonl"))
    fw = next(p for p in packets if any(f.key == "A16SN" for f in p))
    values = {f.key: f.value for f in fw}
    assert values["A16FW"] == "2.17 Jan 26 2024"
    assert values["A16SN"] == "A16HS0000#000000"


def test_parse_field_variants():
    assert parse_field(b"\rVA=54") == Field("VA", "54")
    assert parse_field(b"DEC=") == Field("DEC", "")
    assert parse_field(b"AQMOD=HD800S     ") == Field("AQMOD", "HD800S")
    assert parse_field(b"V01") == Field("V01", None)
    assert parse_field(b"") is None
    assert parse_field(b"\r") is None


def test_incomplete_packet_is_buffered():
    parser = StreamParser()
    assert parser.feed(b"PWR=ON\x00") == []
    assert parser.feed(b"\r") == [[Field("PWR", "ON")]]
