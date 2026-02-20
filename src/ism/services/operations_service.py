from __future__ import annotations

import json
import logging
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


log = logging.getLogger(__name__)


@dataclass(frozen=True)
class HealthReport:
    sqlite_integrity: str
    db_size_bytes: int
    logs_count: int
    generated_at: str


class OperationsService:
    def __init__(self, repo, db_path: Path | str, logs_dir: Path | str, backup_dir: Path | str):
        self.repo = repo
        self.db_path = Path(db_path)
        self.logs_dir = Path(logs_dir)
        self.backup_dir = Path(backup_dir)

    def run_health_check(self) -> HealthReport:
        integrity = self.repo.integrity_check()
        logs_count = len(list(self.logs_dir.glob("*.log"))) if self.logs_dir.exists() else 0
        size = self.db_path.stat().st_size if self.db_path.exists() else 0
        return HealthReport(
            sqlite_integrity=integrity,
            db_size_bytes=size,
            logs_count=logs_count,
            generated_at=datetime.now().isoformat(timespec="seconds"),
        )

    def export_diagnostics(self, target_dir: Path | str | None = None) -> Path:
        out_dir = Path(target_dir) if target_dir else self.db_path.parent
        out_dir.mkdir(parents=True, exist_ok=True)

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        zip_path = out_dir / f"diagnostics_{ts}.zip"
        report = self.run_health_check()

        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            if self.db_path.exists():
                zf.write(self.db_path, arcname=self.db_path.name)

            if self.logs_dir.exists():
                for f in sorted(self.logs_dir.glob("*.log")):
                    zf.write(f, arcname=f"logs/{f.name}")

            if self.backup_dir.exists():
                latest = sorted(self.backup_dir.glob("sales_backup_*.db.enc"))
                for f in latest[-3:]:
                    zf.write(f, arcname=f"backups/{f.name}")

            zf.writestr("health_report.json", json.dumps(report.__dict__, ensure_ascii=False, indent=2))

        log.info("diagnostics_exported path=%s", zip_path)
        return zip_path

    def restore_latest_backup(self, backup_service) -> Path:
        if not self.backup_dir.exists():
            raise FileNotFoundError("No backup directory found")
        files = sorted(self.backup_dir.glob("sales_backup_*.db.enc"))
        if not files:
            raise FileNotFoundError("No backups available to restore")
        latest = files[-1]
        restored = backup_service.restore_backup(latest)
        log.warning("backup_restored latest=%s", latest.name)
        return restored