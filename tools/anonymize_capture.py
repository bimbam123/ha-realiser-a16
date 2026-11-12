"""Anonymise a capture from tools/a16_capture.py for use as test fixture.

Replaces serial number, user names, room/subject names and HPEQ file/subject
names with stable placeholders (same original value -> same placeholder).
Firmware, layouts, headphone models, dates and all framing bytes are kept.
``hex``/``ascii``/``fields`` are recomputed from the rewritten bytes.

Usage:
    python tools/anonymize_capture.py docs/captures/<in>.jsonl tests/fixtures/<out>.jsonl
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SERIAL_PLACEHOLDER = "A16HS0000#000000"
HOST_PLACEHOLDER = "192.0.2.16"  # TEST-NET-1, RFC 5737

# key -> placeholder prefix; numbering is per prefix
REPLACE = {
    "AUR": "Listener",
    "BUR": "Listener",
    "AROOM": "Room",
    "BROOM": "Room",
    "ANAME": "Subject",
    "BNAME": "Subject",
    "AQFILE": "HPEQ File",
    "BQFILE": "HPEQ File",
    "AQNAME": "HPEQ Subject",
    "BQNAME": "HPEQ Subject",
}


class Anonymizer:
    def __init__(self) -> None:
        self.mapping: dict[tuple[str, str], str] = {}
        self.counters: dict[str, int] = {}
        self.originals: set[str] = set()

    def placeholder(self, prefix: str, value: str) -> str:
        key = (prefix, value)
        if key not in self.mapping:
            n = self.counters.get(prefix, 0) + 1
            self.counters[prefix] = n
            self.mapping[key] = f"{prefix} {n}"
        return self.mapping[key]

    def field(self, raw: bytes) -> bytes:
        text = raw.decode("ascii", "replace")
        lead = text[: len(text) - len(text.lstrip("\r"))]
        body = text[len(lead) :]
        key, sep, value = body.partition("=")
        if not sep:
            return raw
        core = value.rstrip(" ")
        trail = value[len(core) :]
        if key == "A16SN" and core:
            self.originals.add(core)
            core = SERIAL_PLACEHOLDER
        elif key in REPLACE and core:
            self.originals.add(core)
            core = self.placeholder(REPLACE[key], core)
        else:
            return raw
        return f"{lead}{key}={core}{trail}".encode("ascii")

    def chunk(self, data: bytes) -> bytes:
        if not data.endswith(b"\x00\r"):
            raise ValueError(f"chunk does not end with \\x00\\r: {data[-8:]!r}")
        return b"\x00".join(self.field(p) for p in data.split(b"\x00"))


def main(src: Path, dst: Path) -> int:
    anon = Anonymizer()
    out_lines = []
    for line in src.read_text(encoding="utf-8").splitlines():
        rec = json.loads(line)
        if "host" in rec:
            rec["host"] = HOST_PLACEHOLDER
        if "hex" in rec and rec["event"] in ("rx", "idle_rx"):
            data = anon.chunk(bytes.fromhex(rec["hex"].replace(" ", "")))
            rec["hex"] = data.hex(" ")
            rec["bytes"] = len(data)
            if "ascii" in rec:
                rec["ascii"] = data.decode("ascii", "replace").replace("\x00", "\\0")
            rec["fields"] = [
                p.decode("ascii", "replace") for p in data.split(b"\x00") if p
            ]
        out_lines.append(json.dumps(rec, ensure_ascii=False))
    text = "\n".join(out_lines) + "\n"

    leaked = sorted(o for o in anon.originals if o in text)
    if leaked:
        print(f"ERROR: original values still present: {len(leaked)}", file=sys.stderr)
        return 1
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(text, encoding="utf-8")
    print(f"{src.name} -> {dst} ({len(out_lines)} records, "
          f"{len(anon.mapping)} values replaced, no originals left)")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("src", type=Path)
    ap.add_argument("dst", type=Path)
    a = ap.parse_args()
    raise SystemExit(main(a.src, a.dst))
