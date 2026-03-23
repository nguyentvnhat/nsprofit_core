"""
Smoke-test that the `app` package imports. Run from `nosaprofit/`:

  python3 test_imports.py

Requires venv + deps: pip install -r requirements.txt
"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

_MODULES = (
    "app.services.file_parser",
    "app.services.shopify_normalizer",
    "app.services.metrics_engine",
    "app.services.signal_engine",
    "app.services.rules_engine",
    "app.services.narrative_engine",
)


def main() -> None:
    for name in _MODULES:
        __import__(name)
    print("Imports OK")


if __name__ == "__main__":
    try:
        main()
    except ModuleNotFoundError as exc:
        print(
            f"Import failed: {exc}\n\n"
            "Install project dependencies (use a venv):\n"
            "  python3 -m venv .venv && source .venv/bin/activate\n"
            "  pip install -r requirements.txt\n",
            file=sys.stderr,
        )
        sys.exit(1)
