from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path


class BackupService:
    def __init__(self, db_path: Path | str, backup_dir: Path | str):
        self.db_path = Path(db_path)
        self.backup_dir = Path(backup_dir)

    def create_backup(self) -> Path:
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        target = self.backup_dir / f"sales_backup_{ts}.db"

        src = sqlite3.connect(str(self.db_path))
        dst = sqlite3.connect(str(target))
        try:
            src.backup(dst)
            dst.commit()
        finally:
            dst.close()
            src.close()
        return target
