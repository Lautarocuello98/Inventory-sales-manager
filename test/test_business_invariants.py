from pathlib import Path

from openpyxl import Workbook

from ism.repositories.sqlite_repo import SqliteRepository
from ism.services.excel_service import ExcelService
from ism.services.inventory_service import InventoryService
from ism.services.purchase_service import PurchaseService
from ism.services.sales_service import SalesService


class FixedFxService:
    def get_today_rate(self):
        return 1000.0


def test_weighted_average_cost_after_multiple_purchases(tmp_path: Path):
    repo = SqliteRepository(tmp_path / "weighted.db")
    repo.init_db()
    inv = InventoryService(repo)
    purchases = PurchaseService(repo)

    pid = inv.add_product("SKU-W", "Weighted", 10.0, 20.0, 10, 1)
    purchases.create_purchase("Vendor A", None, [{"product_id": pid, "qty": 10, "unit_cost_usd": 20.0}])

    updated = repo.get_product_by_id(pid)
    assert updated is not None
    assert updated.stock == 20
    assert round(updated.cost_usd, 2) == 15.0


def test_sale_line_margin_uses_current_weighted_cost(tmp_path: Path):
    repo = SqliteRepository(tmp_path / "margin.db")
    repo.init_db()
    inv = InventoryService(repo)
    purchases = PurchaseService(repo)
    sales = SalesService(repo, FixedFxService())

    pid = inv.add_product("SKU-M", "Margin", 10.0, 20.0, 10, 1)
    purchases.create_purchase("Vendor A", None, [{"product_id": pid, "qty": 10, "unit_cost_usd": 20.0}])

    sale_id = sales.create_sale(None, [{"product_id": pid, "qty": 2, "unit_price_usd": 30.0}])
    lines = sales.sale_items_for_sale(sale_id)

    assert len(lines) == 1
    assert round(lines[0].cost_usd, 2) == 15.0
    assert round(lines[0].line_margin_usd, 2) == 30.0


def test_excel_import_keeps_existing_stock_and_logs_purchase(tmp_path: Path):
    repo = SqliteRepository(tmp_path / "excel.db")
    repo.init_db()
    inv = InventoryService(repo)
    purchases = PurchaseService(repo)
    excel = ExcelService(repo, purchases, inv)

    pid = inv.add_product("SKU-X", "Excel", 5.0, 8.0, 10, 1)

    wb = Workbook()
    ws = wb.active
    ws.append(["sku", "name", "cost_usd", "price_usd", "stock", "min_stock"])
    ws.append(["SKU-X", "Excel Updated", 6.0, 9.0, 5, 2])
    path = tmp_path / "import.xlsx"
    wb.save(path)

    ok, skipped = excel.import_restock_excel(str(path))
    updated = repo.get_product_by_id(pid)

    assert ok == 1
    assert skipped == 0
    assert updated is not None
    assert updated.stock == 15

    purchase_rows = purchases.list_purchases_between("2000-01-01 00:00:00", "2100-01-01 00:00:00")
    assert len(purchase_rows) == 1
    assert purchase_rows[0].vendor == "EXCEL_IMPORT"