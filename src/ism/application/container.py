from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ism.repositories.sqlite_repo import SqliteRepository
from ism.services.auth_service import AuthService
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

    return AppContainer(
        repo=repo,
        fx=fx,
        inventory=inventory,
        purchases=purchases,
        sales=sales,
        excel=excel,
        reporting=reporting,
        auth=auth,
    )