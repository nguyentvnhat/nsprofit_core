"""Fix import collision: root file `streamlit_app.py` vs package dir `streamlit_app/`.

Streamlit (and Python) may bind the name ``streamlit_app`` to the entrypoint
``.py`` file. That shadows the real package directory and breaks
``from streamlit_app.ui_components import ...``.

Call ``ensure_streamlit_app_package(project_root)`` after putting ``project_root``
on ``sys.path`` and *before* any ``streamlit_app.*`` imports.
"""

from __future__ import annotations

import sys
import types
from pathlib import Path


def ensure_streamlit_app_package(project_root: Path) -> None:
    """Register ``streamlit_app`` as a package pointing at ``project_root/streamlit_app``."""
    pkg_dir = (project_root / "streamlit_app").resolve()
    if not pkg_dir.is_dir():
        return

    mod = sys.modules.get("streamlit_app")
    if mod is not None and getattr(mod, "__path__", None):
        return

    package = types.ModuleType("streamlit_app")
    package.__path__ = [str(pkg_dir)]  # type: ignore[attr-defined]
    init_py = pkg_dir / "__init__.py"
    package.__file__ = str(init_py) if init_py.is_file() else None
    sys.modules["streamlit_app"] = package
