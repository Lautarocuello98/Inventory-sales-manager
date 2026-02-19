from __future__ import annotations

import logging

from ism.config import get_app_paths
from ism.logging_config import setup_logging
from ism.repositories.sqlite_repo import SqliteRepository
from ism.services.fx_service import FxService
from ism.services.inventory_service import InventoryService
from ism.services.sales_service import SalesService
from ism.services.purchase_service import PurchaseService
from ism.services.excel_service import ExcelService
from ism.services.reporting_service import ReportingService
from ism.services.auth_service import AuthService
from ism.ui.app import App


def main() -> None:
    paths = get_app_paths()
    setup_logging(paths.logs_dir, level=logging.INFO)

    repo = SqliteRepository(paths.db_path)
    repo.init_db()

    fx = FxService(repo)
    inventory = InventoryService(repo)
    purchases = PurchaseService(repo)
    sales = SalesService(repo, fx)
    excel = ExcelService(repo, purchases, inventory)
    reporting = ReportingService(repo)
    auth = AuthService(repo)

    app = App(
        fx_service=fx,
        inventory_service=inventory,
        sales_service=sales,
        purchase_service=purchases,
        excel_service=excel,
        reporting_service=reporting,
        auth_service=auth,        
        db_path=str(paths.db_path),
        logs_dir=str(paths.logs_dir),
    )
    app.mainloop()


if __name__ == "__main__":
    main()
