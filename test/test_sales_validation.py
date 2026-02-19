from pathlib import Path

import pytest

from ism.domain.errors import InsufficientStockError, ValidationError
from ism.repositories.sqlite_repo import SqliteRepository
from ism.services.inventory_service import InventoryService
from ism.services.sales_service import SalesService


class FixedFxService:
    def get_today_rate(self):
        return 1000.0


def _setup(tmp_path: Path):
    db = tmp_path / "sales_validation.db"
    repo = SqliteRepository(db)
    repo.init_db()
    inventory = InventoryService(repo)
    pid = inventory.add_product("SKU-1", "Producto", 5.0, 10.0, 5, 1)
    return repo, pid


def test_create_sale_rejects_negative_unit_price(tmp_path: Path):
    repo, pid = _setup(tmp_path)
    sales = SalesService(repo, FixedFxService())

    with pytest.raises(ValidationError, match="Unit price must be > 0"):
        sales.create_sale(notes=None, items=[{"product_id": pid, "qty": 1, "unit_price_usd": -1.0}])


def test_create_sale_rejects_oversell_when_same_product_is_repeated(tmp_path: Path):
    repo, pid = _setup(tmp_path)
    sales = SalesService(repo, FixedFxService())

    with pytest.raises(InsufficientStockError):
        sales.create_sale(
            notes=None,
            items=[
                {"product_id": pid, "qty": 3, "unit_price_usd": 10.0},
                {"product_id": pid, "qty": 3, "unit_price_usd": 10.0},
            ],
        )