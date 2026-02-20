from __future__ import annotations

from ism.domain.errors import ValidationError, NotFoundError
from ism.domain.models import Product


class InventoryService:
    def __init__(self, repo):
        self.repo = repo

    def list_products(self) -> list[Product]:
        return self.repo.list_products()

    def top_critical_stock(self, limit: int = 10) -> list[tuple[str, int, int]]:
        return self.repo.list_top_critical_stock(limit)
    
    def get_product_by_sku(self, sku: str) -> Product:
        p = self.repo.get_product_by_sku(sku)
        if not p:
            raise NotFoundError("Product not found.")
        return p

    def add_product(self, sku: str, name: str, cost: float, price: float, stock: int, min_stock: int) -> int:
        sku = (sku or "").strip()
        name = (name or "").strip()
        if not sku or not name:
            raise ValidationError("SKU and Name are required.")
        if stock < 0 or min_stock < 0:
            raise ValidationError("Stock values must be >= 0.")
        if cost < 0:
            raise ValidationError("Cost must be >= 0.")
        if price <= 0:
            raise ValidationError("Price must be > 0.")
        return self.repo.add_product(sku, name, float(cost), float(price), int(stock), int(min_stock))
    
    def delete_product(self, product_id: int) -> None:
        product = self.repo.get_product_by_id(int(product_id))
        if not product:
            raise NotFoundError("Product not found.")
        removed = self.repo.deactivate_product(int(product_id))
        if not removed:
            raise NotFoundError("Product not found.")
        
    def remove_product_stock(self, product_id: int, qty: int, actor_user_id: int | None = None, notes: str | None = None) -> None:
        if qty <= 0:
            raise ValidationError("Quantity to remove must be > 0.")
        product = self.repo.get_product_by_id(int(product_id))
        if not product:
            raise NotFoundError("Product not found.")
        if qty > int(product.stock):
            raise ValidationError(f"Not enough stock. Available: {product.stock}")
        updated = self.repo.adjust_product_stock(int(product_id), -int(qty), actor_user_id=actor_user_id, notes=notes)
        if not updated:
            raise NotFoundError("Product not found.")

    def clear_product_stock(self, product_id: int, actor_user_id: int | None = None, notes: str | None = None) -> None:
        product = self.repo.get_product_by_id(int(product_id))
        if not product:
            raise NotFoundError("Product not found.")
        if int(product.stock) == 0:
            return
        updated = self.repo.adjust_product_stock(int(product_id), -int(product.stock), actor_user_id=actor_user_id, notes=notes)
        if not updated:
            raise NotFoundError("Product not found.")

    def update_product(self, product_id: int, price: float, min_stock: int) -> None:
        if price <= 0:
            raise ValidationError("Price must be > 0.")
        if min_stock < 0:
            raise ValidationError("Min stock must be >= 0.")

        updated = self.repo.update_product_pricing_and_min_stock(int(product_id), float(price), int(min_stock))
        if not updated:
            raise NotFoundError("Product not found.")
    
    def upsert_product_keep_stock(self, sku: str, name: str, cost: float, price: float, min_stock: int) -> int:
        p = self.repo.get_product_by_sku(sku)
        if p:
            return self.repo.upsert_product(sku, name, cost, price, p.stock, min_stock)
        return self.repo.upsert_product(sku, name, cost, price, 0, min_stock)
