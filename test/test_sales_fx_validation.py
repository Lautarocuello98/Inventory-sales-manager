from pathlib import Path

import pytest

from ism.domain.errors import FxUnavailableError
from ism.repositories.sqlite_repo import SqliteRepository
from ism.services.inventory_service import InventoryService
from ism.services.sales_service import SalesService


class InvalidFxService:
    def get_today_rate(self):
        return "invalid-number"


class UnavailableFxService:
    def get_today_rate(self):
        raise FxUnavailableError("upstream unavailable")


def _setup_repo_with_product(tmp_path: Path) -> tuple[SqliteRepository, int]:
    db = tmp_path / "sales.db"
    repo = SqliteRepository(db)
    repo.init_db()
    inventory = InventoryService(repo)
    pid = inventory.add_product("SKU-1", "Producto", 5.0, 10.0, 10, 1)
    return repo, pid


def test_create_sale_raises_fx_unavailable_for_non_numeric_rate(tmp_path: Path):
    repo, pid = _setup_repo_with_product(tmp_path)
    sales = SalesService(repo, InvalidFxService())

    with pytest.raises(FxUnavailableError):
        sales.create_sale(notes=None, items=[{"product_id": pid, "qty": 1, "unit_price_usd": 10.0}])


def test_create_sale_propagates_fx_unavailable_error(tmp_path: Path):
    repo, pid = _setup_repo_with_product(tmp_path)
    sales = SalesService(repo, UnavailableFxService())

    with pytest.raises(FxUnavailableError, match="upstream unavailable") as exc_info:
        sales.create_sale(notes=None, items=[{"product_id": pid, "qty": 1, "unit_price_usd": 10.0}])

    assert exc_info.value.__cause__ is None