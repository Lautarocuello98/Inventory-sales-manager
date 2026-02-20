from __future__ import annotations
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Product:
    id: int
    sku: str
    name: str
    cost_usd: float
    price_usd: float
    stock: int
    min_stock: int
    active: int = 1


@dataclass(frozen=True)
class SaleHeader:
    id: int
    datetime: str
    total_usd: float
    fx_usd_ars: float
    total_ars: float
    notes: Optional[str]


@dataclass(frozen=True)
class SaleLine:
    sku: str
    name: str
    qty: int
    unit_price_usd: float
    line_total_usd: float
    cost_usd: float
    line_margin_usd: float


@dataclass(frozen=True)
class PurchaseHeader:
    id: int
    datetime: str
    vendor: Optional[str]
    total_usd: float
    notes: Optional[str]


@dataclass(frozen=True)
class PurchaseLine:
    sku: str
    name: str
    qty: int
    unit_cost_usd: float
    line_total_usd: float


@dataclass(frozen=True)
class User:
    id: int
    username: str
    role: str
    active: int = 1
    must_change_pin: int = 0

@dataclass(frozen=True)
class LedgerEntry:
    id: int
    datetime: str
    product_id: int
    movement_type: str
    qty_delta: int
    stock_after: int
    unit_value_usd: float
    reference_type: str
    reference_id: int
    actor_user_id: Optional[int]
    notes: Optional[str]