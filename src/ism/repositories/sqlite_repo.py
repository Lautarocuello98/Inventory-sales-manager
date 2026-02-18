from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Iterable, Optional
import logging

from ism.domain.models import Product, SaleHeader, SaleLine, PurchaseHeader, PurchaseLine

log = logging.getLogger(__name__)


class SqliteRepository:
    def __init__(self, db_path: Path | str):
        self.db_path = str(db_path)

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    def init_db(self) -> None:
        conn = self._conn()
        cur = conn.cursor()

        cur.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sku TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            cost_usd REAL NOT NULL,
            price_usd REAL NOT NULL,
            stock INTEGER NOT NULL DEFAULT 0,
            min_stock INTEGER NOT NULL DEFAULT 0,
            active INTEGER NOT NULL DEFAULT 1
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            datetime TEXT NOT NULL,
            total_usd REAL NOT NULL,
            fx_usd_ars REAL NOT NULL,
            total_ars REAL NOT NULL,
            notes TEXT
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS sale_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sale_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            qty INTEGER NOT NULL,
            unit_price_usd REAL NOT NULL,
            FOREIGN KEY(sale_id) REFERENCES sales(id) ON DELETE CASCADE,
            FOREIGN KEY(product_id) REFERENCES products(id)
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS fx_rates (
            date TEXT PRIMARY KEY,
            usd_ars REAL NOT NULL
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS purchases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            datetime TEXT NOT NULL,
            vendor TEXT,
            total_usd REAL NOT NULL,
            notes TEXT
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS purchase_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            purchase_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            qty INTEGER NOT NULL,
            unit_cost_usd REAL NOT NULL,
            FOREIGN KEY(purchase_id) REFERENCES purchases(id) ON DELETE CASCADE,
            FOREIGN KEY(product_id) REFERENCES products(id)
        )
        """)

        conn.commit()
        conn.close()

    # ---------- Products ----------
    def add_product(self, sku: str, name: str, cost_usd: float, price_usd: float,
                    stock: int, min_stock: int) -> int:
        conn = self._conn()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO products (sku, name, cost_usd, price_usd, stock, min_stock)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (sku, name, cost_usd, price_usd, stock, min_stock))
        pid = cur.lastrowid
        conn.commit()
        conn.close()
        return int(pid)

    def upsert_product(self, sku: str, name: str, cost_usd: float, price_usd: float,
                       stock: int, min_stock: int) -> int:
        conn = self._conn()
        cur = conn.cursor()

        cur.execute("SELECT id FROM products WHERE sku = ?", (sku,))
        row = cur.fetchone()
        if row:
            pid = int(row[0])
            cur.execute("""
                UPDATE products
                SET name=?, cost_usd=?, price_usd=?, stock=?, min_stock=?, active=1
                WHERE sku=?
            """, (name, cost_usd, price_usd, stock, min_stock, sku))
        else:
            cur.execute("""
                INSERT INTO products (sku, name, cost_usd, price_usd, stock, min_stock)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (sku, name, cost_usd, price_usd, stock, min_stock))
            pid = int(cur.lastrowid)

        conn.commit()
        conn.close()
        return int(pid)

    def list_products(self) -> list[Product]:
        conn = self._conn()
        cur = conn.cursor()
        cur.execute("""
            SELECT id, sku, name, cost_usd, price_usd, stock, min_stock, active
            FROM products
            WHERE active = 1
            ORDER BY name
        """)
        rows = cur.fetchall()
        conn.close()
        return [
            Product(
                id=int(r[0]), sku=str(r[1]), name=str(r[2]),
                cost_usd=float(r[3]), price_usd=float(r[4]),
                stock=int(r[5]), min_stock=int(r[6]), active=int(r[7]),
            )
            for r in rows
        ]

    def get_product_by_sku(self, sku: str) -> Optional[Product]:
        conn = self._conn()
        cur = conn.cursor()
        cur.execute("""
            SELECT id, sku, name, cost_usd, price_usd, stock, min_stock, active
            FROM products
            WHERE active=1 AND sku=?
        """, (sku,))
        r = cur.fetchone()
        conn.close()
        if not r:
            return None
        return Product(
            id=int(r[0]), sku=str(r[1]), name=str(r[2]),
            cost_usd=float(r[3]), price_usd=float(r[4]),
            stock=int(r[5]), min_stock=int(r[6]), active=int(r[7]),
        )

    def get_product_by_id(self, product_id: int) -> Optional[Product]:
        conn = self._conn()
        cur = conn.cursor()
        cur.execute("""
            SELECT id, sku, name, cost_usd, price_usd, stock, min_stock, active
            FROM products
            WHERE active=1 AND id=?
        """, (int(product_id),))
        r = cur.fetchone()
        conn.close()
        if not r:
            return None
        return Product(
            id=int(r[0]), sku=str(r[1]), name=str(r[2]),
            cost_usd=float(r[3]), price_usd=float(r[4]),
            stock=int(r[5]), min_stock=int(r[6]), active=int(r[7]),
        )

    def update_product_stock_and_cost(self, product_id: int, new_stock: int, new_cost_usd: float) -> None:
        conn = self._conn()
        cur = conn.cursor()
        cur.execute("""
            UPDATE products
            SET stock = ?, cost_usd = ?
            WHERE id = ? AND active=1
        """, (int(new_stock), float(new_cost_usd), int(product_id)))
        conn.commit()
        conn.close()

    def decrement_stock(self, product_id: int, qty: int) -> None:
        conn = self._conn()
        cur = conn.cursor()
        cur.execute("""
            UPDATE products
            SET stock = stock - ?
            WHERE id = ? AND active=1
        """, (int(qty), int(product_id)))
        conn.commit()
        conn.close()

    # ---------- FX ----------
    def get_fx_rate(self, date_iso: str) -> Optional[float]:
        conn = self._conn()
        cur = conn.cursor()
        cur.execute("SELECT usd_ars FROM fx_rates WHERE date = ?", (date_iso,))
        row = cur.fetchone()
        conn.close()
        return float(row[0]) if row else None

    def set_fx_rate(self, date_iso: str, usd_ars: float) -> None:
        conn = self._conn()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO fx_rates (date, usd_ars) VALUES (?, ?)
            ON CONFLICT(date) DO UPDATE SET usd_ars=excluded.usd_ars
        """, (date_iso, float(usd_ars)))
        conn.commit()
        conn.close()
    
    def get_latest_fx_rate(self) -> Optional[float]:
        conn = self._conn()
        cur = conn.cursor()
        cur.execute("SELECT usd_ars FROM fx_rates ORDER BY date DESC LIMIT 1")
        row = cur.fetchone()
        conn.close()
        return float(row[0]) if row else None


    # ---------- Sales ----------
    def create_sale(self, datetime_iso: str, fx_usd_ars: float, notes: Optional[str],
                    items: Iterable[dict]) -> int:
        """
        items: [{product_id, qty, unit_price_usd}]
        stock validation should be done in services, but we still keep it safe here.
        """
        conn = self._conn()
        cur = conn.cursor()

        # validate stock
        for it in items:
            cur.execute("SELECT stock FROM products WHERE id=? AND active=1", (int(it["product_id"]),))
            row = cur.fetchone()
            if not row:
                conn.rollback()
                conn.close()
                raise ValueError("Product not found/active.")
            if int(row[0]) < int(it["qty"]):
                conn.rollback()
                conn.close()
                raise ValueError("Not enough stock for one of the items.")

        total_usd = sum(float(it["unit_price_usd"]) * int(it["qty"]) for it in items)
        total_ars = total_usd * float(fx_usd_ars)

        cur.execute("""
            INSERT INTO sales (datetime, total_usd, fx_usd_ars, total_ars, notes)
            VALUES (?, ?, ?, ?, ?)
        """, (datetime_iso, float(total_usd), float(fx_usd_ars), float(total_ars), notes))
        sale_id = int(cur.lastrowid)

        for it in items:
            cur.execute("""
                INSERT INTO sale_items (sale_id, product_id, qty, unit_price_usd)
                VALUES (?, ?, ?, ?)
            """, (sale_id, int(it["product_id"]), int(it["qty"]), float(it["unit_price_usd"])))

            cur.execute("UPDATE products SET stock = stock - ? WHERE id = ? AND active=1",
                        (int(it["qty"]), int(it["product_id"])))

        conn.commit()
        conn.close()
        return sale_id

    def list_sales_between(self, start_iso: str, end_iso: str) -> list[SaleHeader]:
        conn = self._conn()
        cur = conn.cursor()
        cur.execute("""
            SELECT id, datetime, total_usd, fx_usd_ars, total_ars, notes
            FROM sales
            WHERE datetime >= ? AND datetime < ?
            ORDER BY datetime DESC
        """, (start_iso, end_iso))
        rows = cur.fetchall()
        conn.close()
        return [
            SaleHeader(
                id=int(r[0]), datetime=str(r[1]),
                total_usd=float(r[2]), fx_usd_ars=float(r[3]),
                total_ars=float(r[4]), notes=(r[5] if r[5] is not None else None),
            )
            for r in rows
        ]

    def get_sale_header(self, sale_id: int) -> Optional[SaleHeader]:
        conn = self._conn()
        cur = conn.cursor()
        cur.execute("""
            SELECT id, datetime, total_usd, fx_usd_ars, total_ars, notes
            FROM sales
            WHERE id = ?
        """, (int(sale_id),))
        r = cur.fetchone()
        conn.close()
        if not r:
            return None
        return SaleHeader(
            id=int(r[0]), datetime=str(r[1]),
            total_usd=float(r[2]), fx_usd_ars=float(r[3]),
            total_ars=float(r[4]), notes=(r[5] if r[5] is not None else None),
        )

    def sale_items_for_sale(self, sale_id: int) -> list[SaleLine]:
        conn = self._conn()
        cur = conn.cursor()
        cur.execute("""
            SELECT p.sku, p.name, si.qty, si.unit_price_usd,
                   (si.qty * si.unit_price_usd) AS line_total_usd,
                   p.cost_usd,
                   (si.qty * (si.unit_price_usd - p.cost_usd)) AS line_margin_usd
            FROM sale_items si
            JOIN products p ON p.id = si.product_id
            WHERE si.sale_id = ?
            ORDER BY p.name
        """, (int(sale_id),))
        rows = cur.fetchall()
        conn.close()
        return [
            SaleLine(
                sku=str(r[0]), name=str(r[1]), qty=int(r[2]),
                unit_price_usd=float(r[3]), line_total_usd=float(r[4]),
                cost_usd=float(r[5]), line_margin_usd=float(r[6]),
            )
            for r in rows
        ]

    def sales_summary_between(self, start_iso: str, end_iso: str) -> tuple[tuple[int, float, float, float], list[tuple]]:
        conn = self._conn()
        cur = conn.cursor()

        cur.execute("""
            SELECT COUNT(*),
                   COALESCE(SUM(total_usd), 0),
                   COALESCE(SUM(total_ars), 0)
            FROM sales
            WHERE datetime >= ? AND datetime < ?
        """, (start_iso, end_iso))
        c, total_usd, total_ars = cur.fetchone()

        cur.execute("""
            SELECT COALESCE(SUM(si.qty * (si.unit_price_usd - p.cost_usd)), 0)
            FROM sale_items si
            JOIN sales s ON s.id = si.sale_id
            JOIN products p ON p.id = si.product_id
            WHERE s.datetime >= ? AND s.datetime < ?
        """, (start_iso, end_iso))
        margin_usd = cur.fetchone()[0]

        cur.execute("""
            SELECT p.sku, p.name,
                   SUM(si.qty) AS units_sold,
                   SUM(si.qty * si.unit_price_usd) AS revenue_usd,
                   SUM(si.qty * (si.unit_price_usd - p.cost_usd)) AS margin_usd
            FROM sale_items si
            JOIN sales s ON s.id = si.sale_id
            JOIN products p ON p.id = si.product_id
            WHERE s.datetime >= ? AND s.datetime < ?
            GROUP BY p.id
            ORDER BY units_sold DESC
            LIMIT 20
        """, (start_iso, end_iso))
        top = cur.fetchall()

        conn.close()
        return (int(c), float(total_usd), float(total_ars), float(margin_usd)), top
    


    def create_purchase_with_items(self, datetime_iso: str, vendor: Optional[str], total_usd: float,
                                   notes: Optional[str], items: Iterable[dict]) -> int:
        """
        Atomic purchase creation: header + items + product stock/cost updates in one transaction.
        items: [{product_id, qty, unit_cost_usd}]
        """
        conn = self._conn()
        cur = conn.cursor()
        try:
            cur.execute("""
                INSERT INTO purchases (datetime, vendor, total_usd, notes)
                VALUES (?, ?, ?, ?)
            """, (datetime_iso, vendor, float(total_usd), notes))
            purchase_id = int(cur.lastrowid)

            for it in items:
                pid = int(it["product_id"])
                qty = int(it["qty"])
                unit_cost = float(it["unit_cost_usd"])

                cur.execute("""
                    SELECT stock, cost_usd
                    FROM products
                    WHERE id = ? AND active = 1
                """, (pid,))
                row = cur.fetchone()
                if not row:
                    raise ValueError(f"Product not found/active: {pid}")

                old_stock = int(row[0])
                old_cost = float(row[1])
                new_stock = old_stock + qty
                new_cost = ((old_stock * old_cost) + (qty * unit_cost)) / new_stock if new_stock > 0 else unit_cost

                cur.execute("""
                    INSERT INTO purchase_items (purchase_id, product_id, qty, unit_cost_usd)
                    VALUES (?, ?, ?, ?)
                """, (purchase_id, pid, qty, unit_cost))

                cur.execute("""
                    UPDATE products
                    SET stock = ?, cost_usd = ?
                    WHERE id = ? AND active = 1
                """, (new_stock, new_cost, pid))

            conn.commit()
            return purchase_id
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()


    # ---------- Purchases ----------
    def create_purchase_header(self, datetime_iso: str, vendor: Optional[str], total_usd: float, notes: Optional[str]) -> int:
        conn = self._conn()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO purchases (datetime, vendor, total_usd, notes)
            VALUES (?, ?, ?, ?)
        """, (datetime_iso, vendor, float(total_usd), notes))
        pid = int(cur.lastrowid)
        conn.commit()
        conn.close()
        return pid

    def add_purchase_item(self, purchase_id: int, product_id: int, qty: int, unit_cost_usd: float) -> None:
        conn = self._conn()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO purchase_items (purchase_id, product_id, qty, unit_cost_usd)
            VALUES (?, ?, ?, ?)
        """, (int(purchase_id), int(product_id), int(qty), float(unit_cost_usd)))
        conn.commit()
        conn.close()

    def list_purchases_between(self, start_iso: str, end_iso: str) -> list[PurchaseHeader]:
        conn = self._conn()
        cur = conn.cursor()
        cur.execute("""
            SELECT id, datetime, vendor, total_usd, notes
            FROM purchases
            WHERE datetime >= ? AND datetime < ?
            ORDER BY datetime DESC
        """, (start_iso, end_iso))
        rows = cur.fetchall()
        conn.close()
        return [
            PurchaseHeader(
                id=int(r[0]), datetime=str(r[1]),
                vendor=(r[2] if r[2] is not None else None),
                total_usd=float(r[3]),
                notes=(r[4] if r[4] is not None else None),
            )
            for r in rows
        ]

    def purchase_items_for_purchase(self, purchase_id: int) -> list[PurchaseLine]:
        conn = self._conn()
        cur = conn.cursor()
        cur.execute("""
            SELECT p.sku, p.name, pi.qty, pi.unit_cost_usd,
                   (pi.qty * pi.unit_cost_usd) AS line_total_usd
            FROM purchase_items pi
            JOIN products p ON p.id = pi.product_id
            WHERE pi.purchase_id = ?
            ORDER BY p.name
        """, (int(purchase_id),))
        rows = cur.fetchall()
        conn.close()
        return [
            PurchaseLine(
                sku=str(r[0]), name=str(r[1]), qty=int(r[2]),
                unit_cost_usd=float(r[3]), line_total_usd=float(r[4]),
            )
            for r in rows
        ]
