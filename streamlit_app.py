"""Deployment entrypoint compatibility for Streamlit platforms.

Some hosting providers expect `streamlit_app.py` at the project root.
This file delegates to the existing UI entrypoint at `streamlit_app/Home.py`
without changing app logic or layout.
"""

from __future__ import annotations

import runpy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from streamlit_pkg_bootstrap import ensure_streamlit_app_package

ensure_streamlit_app_package(ROOT)

runpy.run_path(str(ROOT / "streamlit_app" / "Home.py"), run_name="__main__")

