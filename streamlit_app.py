"""Deployment entrypoint compatibility for Streamlit platforms.

Some hosting providers expect `streamlit_app.py` at the project root.
This file delegates to the existing UI entrypoint at `streamlit_app/Home.py`
without changing app logic or layout.
"""

from __future__ import annotations

import runpy
from pathlib import Path


runpy.run_path(str(Path(__file__).resolve().parent / "streamlit_app" / "Home.py"), run_name="__main__")

