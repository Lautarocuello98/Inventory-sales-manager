import sqlite3
from typing import Iterable

DB_NAME = "sales.db"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_NAME)
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db() -> None:
    conn = get_connection()
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

    # Purchases / Restock
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


# ---------------- Products ----------------

def add_product(sku: str, name: str, cost_usd: float, price_usd: float, stock: int, min_stock: int) -> None:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO products (sku, name, cost_usd, price_usd, stock, min_stock)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (sku, name, cost_usd, price_usd, stock, min_stock))
    conn.commit()
    conn.close()


def upsert_product(sku: str, name: str, cost_usd: float, price_usd: float, stock: int, min_stock: int) -> None:
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT id FROM products WHERE sku = ?", (sku,))
    row = cur.fetchone()
    if row:
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

    conn.commit()
    conn.close()


def list_products():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, sku, name, cost_usd, price_usd, stock, min_stock
        FROM products
        WHERE active = 1
        ORDER BY name
    """)
    rows = cur.fetchall()
    conn.close()
    return rows


def get_product_by_sku(sku: str):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, sku, name, cost_usd, price_usd, stock, min_stock
        FROM products
        WHERE active=1 AND sku=?
    """, (sku,))
    row = cur.fetchone()
    conn.close()
    return row


# ---------------- Sales ----------------

def create_sale(datetime_iso: str, fx_usd_ars: float, notes: str | None, items: Iterable[dict]) -> int:
    """
    items: {product_id, qty, unit_price_usd}
    """
    conn = get_connection()
    cur = conn.cursor()

    # validate stock
    for it in items:
        cur.execute("SELECT stock FROM products WHERE id=? AND active=1", (it["product_id"],))
        row = cur.fetchone()
        if not row:
            conn.rollback()
            conn.close()
            raise ValueError("Product not found/active.")
        if row[0] < int(it["qty"]):
            conn.rollback()
            conn.close()
            raise ValueError("Not enough stock for one of the items.")

    total_usd = 0.0
    for it in items:
        total_usd += float(it["unit_price_usd"]) * int(it["qty"])
    total_ars = total_usd * float(fx_usd_ars)

    cur.execute("""
        INSERT INTO sales (datetime, total_usd, fx_usd_ars, total_ars, notes)
        VALUES (?, ?, ?, ?, ?)
    """, (datetime_iso, total_usd, fx_usd_ars, total_ars, notes))
    sale_id = cur.lastrowid

    for it in items:
        cur.execute("""
            INSERT INTO sale_items (sale_id, product_id, qty, unit_price_usd)
            VALUES (?, ?, ?, ?)
        """, (sale_id, it["product_id"], int(it["qty"]), float(it["unit_price_usd"])))

        cur.execute("UPDATE products SET stock = stock - ? WHERE id = ?", (int(it["qty"]), it["product_id"]))

    conn.commit()
    conn.close()
    return int(sale_id)


def list_sales_between(start_iso: str, end_iso: str):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, datetime, total_usd, fx_usd_ars, total_ars, notes
        FROM sales
        WHERE datetime >= ? AND datetime < ?
        ORDER BY datetime DESC
    """, (start_iso, end_iso))
    rows = cur.fetchall()
    conn.close()
    return rows


def get_sale_header(sale_id: int):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, datetime, total_usd, fx_usd_ars, total_ars, notes
        FROM sales
        WHERE id = ?
    """, (sale_id,))
    row = cur.fetchone()
    conn.close()
    return row


def sale_items_for_sale(sale_id: int):
    conn = get_connection()
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
    """, (sale_id,))
    rows = cur.fetchall()
    conn.close()
    return rows


def sales_summary_between(start_iso: str, end_iso: str):
    """
    totals: (sales_count, total_usd, total_ars, margin_usd)
    """
    conn = get_connection()
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

    # (top products not needed for your new simplified report, but we keep it if you want later)
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


# ---------------- Purchases / Restock ----------------

def create_purchase(datetime_iso: str, vendor: str | None, notes: str | None, items: Iterable[dict]) -> int:
    """
    items: {product_id, qty, unit_cost_usd}
    Increases stock and updates product cost using weighted average cost.
    """
    conn = get_connection()
    cur = conn.cursor()

    total_usd = 0.0
    for it in items:
        total_usd += float(it["unit_cost_usd"]) * int(it["qty"])

    cur.execute("""
        INSERT INTO purchases (datetime, vendor, total_usd, notes)
        VALUES (?, ?, ?, ?)
    """, (datetime_iso, vendor, total_usd, notes))
    purchase_id = cur.lastrowid

    for it in items:
        pid = int(it["product_id"])
        qty = int(it["qty"])
        unit_cost = float(it["unit_cost_usd"])

        cur.execute("""
            INSERT INTO purchase_items (purchase_id, product_id, qty, unit_cost_usd)
            VALUES (?, ?, ?, ?)
        """, (purchase_id, pid, qty, unit_cost))

        # Get current stock and cost
        cur.execute("SELECT stock, cost_usd FROM products WHERE id=? AND active=1", (pid,))
        row = cur.fetchone()
        if not row:
            conn.rollback()
            conn.close()
            raise ValueError("Product not found/active.")

        old_stock = int(row[0])
        old_cost = float(row[1])

        # Weighted average cost
        new_stock = old_stock + qty
        if new_stock > 0:
            new_cost = ((old_stock * old_cost) + (qty * unit_cost)) / new_stock
        else:
            new_cost = unit_cost

        cur.execute("""
            UPDATE products
            SET stock = ?, cost_usd = ?
            WHERE id = ?
        """, (new_stock, new_cost, pid))

    conn.commit()
    conn.close()
    return int(purchase_id)


def list_purchases_between(start_iso: str, end_iso: str):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, datetime, vendor, total_usd, notes
        FROM purchases
        WHERE datetime >= ? AND datetime < ?
        ORDER BY datetime DESC
    """, (start_iso, end_iso))
    rows = cur.fetchall()
    conn.close()
    return rows


def purchase_items_for_purchase(purchase_id: int):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT p.sku, p.name, pi.qty, pi.unit_cost_usd,
               (pi.qty * pi.unit_cost_usd) AS line_total_usd
        FROM purchase_items pi
        JOIN products p ON p.id = pi.product_id
        WHERE pi.purchase_id = ?
        ORDER BY p.name
    """, (purchase_id,))
    rows = cur.fetchall()
    conn.close()
    return rows
