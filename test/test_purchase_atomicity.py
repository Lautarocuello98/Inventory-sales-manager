from pathlib import Path

from ism.repositories.sqlite_repo import SqliteRepository
from ism.services.inventory_service import InventoryService
from ism.services.purchase_service import PurchaseService


class FailingRepo(SqliteRepository):
    def create_purchase_with_items(self, datetime_iso, vendor, total_usd, notes, items):
        conn = self._conn()
        cur = conn.cursor()
        try:
            cur.execute(
                """
                INSERT INTO purchases (datetime, vendor, total_usd, notes)
                VALUES (?, ?, ?, ?)
                """,
                (datetime_iso, vendor, float(total_usd), notes),
            )
            purchase_id = int(cur.lastrowid)

            for idx, it in enumerate(items):
                pid = int(it["product_id"])
                qty = int(it["qty"])
                unit_cost = float(it["unit_cost_usd"])
                cur.execute(
                    """
                    INSERT INTO purchase_items (purchase_id, product_id, qty, unit_cost_usd)
                    VALUES (?, ?, ?, ?)
                    """,
                    (purchase_id, pid, qty, unit_cost),
                )
                if idx == 0:
                    raise RuntimeError("boom")

            conn.commit()
            return purchase_id
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()


def test_purchase_rolls_back_when_repository_fails(tmp_path: Path):
    db = tmp_path / "t.db"
    repo = FailingRepo(db)
    repo.init_db()

    inventory = InventoryService(repo)
    purchases = PurchaseService(repo)

    pid = inventory.add_product("SKU-1", "Producto", 2.0, 4.0, 0, 0)

    try:
        purchases.create_purchase(
            vendor="TEST",
            notes="rollback expected",
            items=[{"product_id": pid, "qty": 5, "unit_cost_usd": 3.0}],
        )
    except RuntimeError:
        pass

    product = repo.get_product_by_id(pid)
    assert product is not None
    assert product.stock == 0

    purchases_rows = repo.list_purchases_between("2000-01-01 00:00:00", "2100-01-01 00:00:00")
    assert purchases_rows == []