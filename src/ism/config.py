from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import sys


@dataclass(frozen=True)
class AppPaths:
    base_dir: Path
    db_path: Path
    logs_dir: Path


def _windows_appdata() -> Path:
    return Path(os.environ.get("APPDATA", str(Path.home() / "AppData" / "Roaming")))


def _mac_app_support() -> Path:
    return Path.home() / "Library" / "Application Support"


def get_app_paths(app_name: str = "InventorySalesManager") -> AppPaths:
    if sys.platform.startswith("win"):
        base = _windows_appdata() / app_name
    elif sys.platform == "darwin":
        base = _mac_app_support() / app_name
    else:
        base = Path.home() / f".{app_name.lower()}"

    logs = base / "logs"
    db = base / "sales.db"

    base.mkdir(parents=True, exist_ok=True)
    logs.mkdir(parents=True, exist_ok=True)

    return AppPaths(base_dir=base, db_path=db, logs_dir=logs)
