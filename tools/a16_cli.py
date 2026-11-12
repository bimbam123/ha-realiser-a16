"""Wrapper to run the pya16 CLI without installing anything.

python tools/a16_cli.py 192.168.1.5 state
python tools/a16_cli.py 192.168.1.5 monitor --seconds 30

pya16 is loaded as a top-level package straight from its folder. The
integration folder itself must NOT be put on sys.path: its select.py would
shadow the standard library module "select" that asyncio needs.
"""

import importlib.util
import sys
from pathlib import Path

PYA16 = (
    Path(__file__).resolve().parent.parent
    / "custom_components"
    / "realiser_a16"
    / "pya16"
)


def load_pya16():
    spec = importlib.util.spec_from_file_location(
        "pya16", PYA16 / "__init__.py", submodule_search_locations=[str(PYA16)]
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["pya16"] = module
    spec.loader.exec_module(module)
    return module


if __name__ == "__main__":
    load_pya16()
    from pya16.cli import main

    raise SystemExit(main())
