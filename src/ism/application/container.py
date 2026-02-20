from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

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
    updates = UpdateService(current_version="1.1.0", source=Path(__file__).resolve().parents[3] / "release" / "latest.json")

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