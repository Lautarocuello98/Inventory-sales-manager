from __future__ import annotations

import logging

from ism.config import get_app_paths
from ism.logging_config import setup_logging
from ism.application import build_container
from ism.ui.app import App


def main() -> None:
    paths = get_app_paths()
    setup_logging(paths.logs_dir, level=logging.INFO)

    container = build_container(paths.db_path)

    app = App(
        fx_service=container.fx,
        inventory_service=container.inventory,
        sales_service=container.sales,
        purchase_service=container.purchases,
        excel_service=container.excel,
        reporting_service=container.reporting,
        auth_service=container.auth,     
        db_path=str(paths.db_path),
        logs_dir=str(paths.logs_dir),
    )
    app.mainloop()


if __name__ == "__main__":
    main()
