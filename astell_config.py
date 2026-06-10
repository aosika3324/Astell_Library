"""Runtime configuration for Astell Library.

Defaults are derived from this repository location, while production deployments
can override paths and network settings with environment variables.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def _bool_env(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _csv_env(name: str, default: list[str]) -> list[str]:
    value = os.environ.get(name)
    if value is None:
        return default
    return [item.strip() for item in value.split(",") if item.strip()]


ASTELL_LIBRARY_ROOT = Path(
    os.environ.get("ASTELL_LIBRARY_ROOT", Path(__file__).resolve().parent)
).resolve()

MEMPALACE_SRC = Path(
    os.environ.get("MEMPALACE_SRC", ASTELL_LIBRARY_ROOT / "mempalace-develop")
).resolve()

MEMPALACE_DB = Path(
    os.environ.get("MEMPALACE_DB", ASTELL_LIBRARY_ROOT / "mempalace_db")
).resolve()

LIBRARY_PATH = Path(
    os.environ.get("ASTELL_KNOWLEDGE_LIBRARY", ASTELL_LIBRARY_ROOT / "Library")
).resolve()

COMM_BUFFER = Path(
    os.environ.get("ASTELL_COMM_BUFFER", ASTELL_LIBRARY_ROOT / "COMM_BUFFER")
).resolve()

ASTELL_CONTROL_DB = Path(
    os.environ.get("ASTELL_CONTROL_DB", MEMPALACE_DB / "astell_control.db")
).resolve()

ASTELL_UI_HOST = os.environ.get("ASTELL_UI_HOST", "127.0.0.1")
ASTELL_UI_PORT = int(os.environ.get("ASTELL_UI_PORT", "8080"))
ASTELL_OPEN_BROWSER = _bool_env("ASTELL_OPEN_BROWSER", True)
ASTELL_CORS_ORIGINS = _csv_env("ASTELL_CORS_ORIGINS", ["*"])


def add_runtime_paths() -> None:
    """Ensure local packages resolve before site packages."""

    for path in (ASTELL_LIBRARY_ROOT, MEMPALACE_SRC):
        path_str = str(path)
        if path_str not in sys.path:
            sys.path.insert(0, path_str)
