from __future__ import annotations

from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version
import os
from pathlib import Path
import sys

from ism.repositories.sqlite_repo import SqliteRepository
from ism.services.auth_service import AuthService
from ism.services.backup_service import BackupService
from ism.services.operations_service import OperationsService
from ism.services.update_service import UpdateService
from ism.services.excel_service import ExcelService
from ism.services.fx_service import FxService
from ism.services.inventory_service import InventoryService
from ism.services.purchase_service import PurchaseService
from ism.services.reporting_service import ReportingService
from ism.services.sales_service import SalesService


@dataclass(frozen=True)
class AppContainer:
    repo: SqliteRepository
    fx: FxService
    inventory: InventoryService
    purchases: PurchaseService
    sales: SalesService
    excel: ExcelService
    reporting: ReportingService
    auth: AuthService
    backup: BackupService
    operations: OperationsService
    updates: UpdateService

def _get_current_version() -> str:
    try:
        return version("inventory-sales-manager")
    except PackageNotFoundError:
        pyproject = Path(__file__).resolve().parents[3] / "pyproject.toml"
        if pyproject.exists():
            for line in pyproject.read_text(encoding="utf-8").splitlines():
                if line.strip().startswith("version") and "=" in line:
                    return line.split("=", 1)[1].strip().strip('"')
        return "0.0.0"

def _resolve_update_source() -> str | Path | None:
    env_source = os.environ.get("ISM_UPDATE_SOURCE", "").strip()
    if env_source:
        return env_source

    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", "")
        if meipass:
            frozen_manifest = Path(meipass) / "release" / "latest.json"
            if frozen_manifest.exists():
                return frozen_manifest

    local_manifest = Path(__file__).resolve().parents[3] / "release" / "latest.json"
    if local_manifest.exists():
        return local_manifest
    return None


def build_container(db_path: Path | str) -> AppContainer:
    repo = SqliteRepository(db_path)
    repo.init_db()

    fx = FxService(repo)
    inventory = InventoryService(repo)
    purchases = PurchaseService(repo)
    sales = SalesService(repo, fx)
    excel = ExcelService(repo, purchases, inventory)
    reporting = ReportingService(repo)
    auth = AuthService(repo)
    backup_dir = Path(db_path).parent / "backups"
    backup = BackupService(db_path, backup_dir)
    operations = OperationsService(repo, db_path=db_path, logs_dir=Path(db_path).parent / "logs", backup_dir=backup_dir)
    update_source = _resolve_update_source()
    updates = UpdateService(current_version=_get_current_version(), source=update_source)

    return AppContainer(
        repo=repo,
        fx=fx,
        inventory=inventory,
        purchases=purchases,
        sales=sales,
        excel=excel,
        reporting=reporting,
        auth=auth,
        backup=backup,
        operations=operations,
        updates=updates,
    )
