from __future__ import annotations

from datetime import datetime
from typing import Iterable, Optional

from ism.domain.errors import ValidationError, NotFoundError
from ism.domain.models import PurchaseHeader, PurchaseLine


class PurchaseService:
    def __init__(self, repo):
        self.repo = repo

    def create_purchase(self, vendor: Optional[str], notes: Optional[str], items: Iterable[dict]) -> int:
        """
        items: [{product_id, qty, unit_cost_usd}]

        Updates stock and cost using weighted average:
          new_cost = (old_stock*old_cost + qty*unit_cost) / (old_stock+qty)
        """
        items = list(items)
        if not items:
            raise ValidationError("Restock cart is empty.")

        # Validate items and compute header total
        total_usd = 0.0
        for it in items:
            qty = int(it["qty"])
            unit_cost = float(it["unit_cost_usd"])
            if qty <= 0:
                raise ValidationError("Qty must be >= 1.")
            if unit_cost < 0:
                raise ValidationError("Unit cost must be >= 0.")
            prod = self.repo.get_product_by_id(int(it["product_id"]))
            if not prod:
                raise NotFoundError("Product not found/active.")
            total_usd += unit_cost * qty

        dt_iso = datetime.now().replace(microsecond=0).isoformat(sep=" ")
        purchase_id = self.repo.create_purchase_header(dt_iso, vendor, total_usd, notes)

        # Insert lines + update inventory
        for it in items:
            pid = int(it["product_id"])
            qty = int(it["qty"])
            unit_cost = float(it["unit_cost_usd"])

            self.repo.add_purchase_item(purchase_id, pid, qty, unit_cost)

            prod = self.repo.get_product_by_id(pid)
            if not prod:
                raise NotFoundError("Product not found/active.")

            old_stock = int(prod.stock)
            old_cost = float(prod.cost_usd)
            new_stock = old_stock + qty
            new_cost = ((old_stock * old_cost) + (qty * unit_cost)) / new_stock if new_stock > 0 else unit_cost

            self.repo.update_product_stock_and_cost(pid, new_stock, new_cost)

        return int(purchase_id)

    def list_purchases_between(self, start_iso: str, end_iso: str) -> list[PurchaseHeader]:
        return self.repo.list_purchases_between(start_iso, end_iso)

    def purchase_items_for_purchase(self, purchase_id: int) -> list[PurchaseLine]:
        return self.repo.purchase_items_for_purchase(purchase_id)
