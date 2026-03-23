"""Deployment entrypoint compatibility for Streamlit platforms.

Some hosting providers expect `streamlit_app.py` at the project root.
This file delegates to the existing UI entrypoint at `streamlit_app/Home.py`
without changing app logic or layout.
"""

from __future__ import annotations

import runpy
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

PACKAGE_DIR = ROOT / "streamlit_app"
if PACKAGE_DIR.is_dir() and "streamlit_app" not in sys.modules:
    package = types.ModuleType("streamlit_app")
    package.__path__ = [str(PACKAGE_DIR)]  # type: ignore[attr-defined]
    package.__file__ = str(PACKAGE_DIR / "__init__.py")
    sys.modules["streamlit_app"] = package

runpy.run_path(str(ROOT / "streamlit_app" / "Home.py"), run_name="__main__")

