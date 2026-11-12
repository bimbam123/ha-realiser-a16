"""Wrapper to run the pya16 CLI without installing anything.

python tools/a16_cli.py 192.168.1.5 state
python tools/a16_cli.py 192.168.1.5 monitor --seconds 30
"""

import sys
from pathlib import Path

sys.path.insert(
    0,
    str(Path(__file__).resolve().parent.parent / "custom_components" / "realiser_a16"),
)

from pya16.cli import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
