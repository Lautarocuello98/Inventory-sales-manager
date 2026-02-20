from __future__ import annotations

import sqlite3
import hashlib
import hmac
import os   
import secrets
import shutil
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional

from ism.domain.models import Product, SaleHeader, SaleLine, PurchaseHeader, PurchaseLine, User, LedgerEntry


class SqliteRepository:
    def __init__(self, db_path: Path | str):
        self.db_path = str(db_path)

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    def init_db(self) -> None:
        self.run_migrations()
        self._ensure_bootstrap_admin()

    def run_migrations(self) -> None:
        conn = self._conn()
        backup_path = self._create_pre_migration_backup()
        try:
            cur = conn.cursor()
            cur.execute("BEGIN")
            cur.execute("CREATE TABLE IF NOT EXISTS schema_migrations (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)")
            cur.execute("SELECT COALESCE(MAX(version), 0) FROM schema_migrations")
            current_version = int(cur.fetchone()[0])

            migrations = [
                (1, self._migration_v1_base),
                (2, self._migration_v2_constraints_and_ledger),
                (3, self._migration_v3_auth_hardening),
            ]

            for version, migration in migrations:
                if version <= current_version:
                    continue
                migration(cur)
                cur.execute(
                    "INSERT INTO schema_migrations (version, applied_at) VALUES (?, datetime('now'))",
                    (version,),
                )
            conn.commit()
        except Exception as exc:
            conn.rollback()
            self._restore_pre_migration_backup(backup_path)
            raise RuntimeError(
                "Database migration failed. Original database restored from automatic backup."
            ) from exc
        finally:
            conn.close()

    def _create_pre_migration_backup(self) -> Path | None:
        db_file = Path(self.db_path)
        if not db_file.exists() or db_file.stat().st_size == 0:
            return None
        backup_file = db_file.with_name(f"{db_file.stem}.pre_migration_{datetime.now().strftime('%Y%m%d%H%M%S')}.bak")
        shutil.copy2(db_file, backup_file)
        return backup_file

    def _restore_pre_migration_backup(self, backup_path: Path | None) -> None:
        if backup_path is None or not backup_path.exists():
            return
        shutil.copy2(backup_path, self.db_path)

    def _migration_v1_base(self, cur: sqlite3.Cursor) -> None:
        cur.execute(
            """
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
        """
        )

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

        cur.execute(
            """
        CREATE TABLE IF NOT EXISTS sale_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sale_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            qty INTEGER NOT NULL,
            unit_price_usd REAL NOT NULL,
            FOREIGN KEY(sale_id) REFERENCES sales(id) ON DELETE CASCADE,
            FOREIGN KEY(product_id) REFERENCES products(id)
        )
        """
        )

        cur.execute(
            """
        CREATE TABLE IF NOT EXISTS fx_rates (
            date TEXT PRIMARY KEY,
            usd_ars REAL NOT NULL
        )
        """
        )

        cur.execute(
            """
        CREATE TABLE IF NOT EXISTS purchases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            datetime TEXT NOT NULL,
            vendor TEXT,
            total_usd REAL NOT NULL,
            notes TEXT
        )
        """
        )

        cur.execute(
            """
        CREATE TABLE IF NOT EXISTS purchase_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            purchase_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            qty INTEGER NOT NULL,
            unit_cost_usd REAL NOT NULL,
            FOREIGN KEY(purchase_id) REFERENCES purchases(id) ON DELETE CASCADE,
            FOREIGN KEY(product_id) REFERENCES products(id)
        )
        """
        )

    def _migration_v2_constraints_and_ledger(self, cur: sqlite3.Cursor) -> None:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                pin TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('admin','seller','viewer')),
                active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS stock_ledger (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                datetime TEXT NOT NULL,
                product_id INTEGER NOT NULL,
                movement_type TEXT NOT NULL CHECK(movement_type IN ('sale','purchase','adjustment')),
                qty_delta INTEGER NOT NULL,
                stock_after INTEGER NOT NULL CHECK(stock_after >= 0),
                unit_value_usd REAL NOT NULL CHECK(unit_value_usd >= 0),
                reference_type TEXT NOT NULL CHECK(reference_type IN ('sale','purchase','manual')),
                reference_id INTEGER NOT NULL,
                actor_user_id INTEGER,
                notes TEXT,
                FOREIGN KEY(product_id) REFERENCES products(id),
                FOREIGN KEY(actor_user_id) REFERENCES users(id)
            )
            """
        )

        self._add_column_if_missing(cur, "sales", "actor_user_id", "INTEGER REFERENCES users(id)")
        self._add_column_if_missing(cur, "purchases", "actor_user_id", "INTEGER REFERENCES users(id)")

        self._rebuild_products_with_constraints(cur)
        self._rebuild_sale_items_with_constraints(cur)
        self._rebuild_purchase_items_with_constraints(cur)
        self._rebuild_fx_rates_with_constraints(cur)

    def _migration_v3_auth_hardening(self, cur: sqlite3.Cursor) -> None:
        self._add_column_if_missing(cur, "users", "failed_attempts", "INTEGER NOT NULL DEFAULT 0")
        self._add_column_if_missing(cur, "users", "locked_until", "TEXT")
        self._add_column_if_missing(cur, "users", "must_change_pin", "INTEGER NOT NULL DEFAULT 0")

        # If legacy predictable bootstrap credentials still exist, force reset on first login.
        cur.execute(
            """
            UPDATE users
            SET must_change_pin = 1
            WHERE username = 'admin'
            """
        )

    def _ensure_bootstrap_admin(self) -> None:
        conn = self._conn()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM users WHERE active=1")
        active_users = int(cur.fetchone()[0])
        if active_users > 0:
            conn.close()
            return

        bootstrap_pin = os.environ.get("ISM_BOOTSTRAP_ADMIN_PIN", "").strip() or secrets.token_urlsafe(12)
        cur.execute(
            """
            INSERT INTO users (username, pin, role, active, must_change_pin)
            VALUES ('admin', ?, 'admin', 1, 1)
            """,
            (self._hash_pin(bootstrap_pin),),
        )
        conn.commit()
        conn.close()

        # Secure local onboarding channel: store one-time bootstrap PIN in a file with restricted permissions.
        pin_file = Path(self.db_path).parent / ".admin_bootstrap_pin"
        pin_file.write_text(bootstrap_pin + "\n", encoding="utf-8")
        try:
            pin_file.chmod(0o600)
        except Exception:
            pass

    def _add_column_if_missing(self, cur: sqlite3.Cursor, table: str, column: str, definition: str) -> None:
        cur.execute(f"PRAGMA table_info({table})")
        cols = {str(r[1]) for r in cur.fetchall()}
        if column in cols:
            return
        cur.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    def _rebuild_products_with_constraints(self, cur: sqlite3.Cursor) -> None:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS products_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sku TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                cost_usd REAL NOT NULL CHECK(cost_usd >= 0),
                price_usd REAL NOT NULL CHECK(price_usd > 0),
                stock INTEGER NOT NULL DEFAULT 0 CHECK(stock >= 0),
                min_stock INTEGER NOT NULL DEFAULT 0 CHECK(min_stock >= 0),
                active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1))
            )
            """
        )
        cur.execute(
            """
            INSERT OR IGNORE INTO products_new (id, sku, name, cost_usd, price_usd, stock, min_stock, active)
            SELECT id, sku, name, MAX(cost_usd,0), CASE WHEN price_usd <= 0 THEN 0.01 ELSE price_usd END,
                   MAX(stock,0), MAX(min_stock,0), CASE WHEN active=0 THEN 0 ELSE 1 END
            FROM products
            """
        )
        cur.execute("DROP TABLE products")
        cur.execute("ALTER TABLE products_new RENAME TO products")

    def _rebuild_sale_items_with_constraints(self, cur: sqlite3.Cursor) -> None:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS sale_items_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sale_id INTEGER NOT NULL,
                product_id INTEGER NOT NULL,
                qty INTEGER NOT NULL CHECK(qty > 0),
                unit_price_usd REAL NOT NULL CHECK(unit_price_usd > 0),
                FOREIGN KEY(sale_id) REFERENCES sales(id) ON DELETE CASCADE,
                FOREIGN KEY(product_id) REFERENCES products(id),
                UNIQUE(sale_id, product_id)
            )
            """
        )
        cur.execute(
            """
            INSERT OR IGNORE INTO sale_items_new (id, sale_id, product_id, qty, unit_price_usd)
            SELECT id, sale_id, product_id, CASE WHEN qty <= 0 THEN 1 ELSE qty END,
                   CASE WHEN unit_price_usd <= 0 THEN 0.01 ELSE unit_price_usd END
            FROM sale_items
            """
        )
        cur.execute("DROP TABLE sale_items")
        cur.execute("ALTER TABLE sale_items_new RENAME TO sale_items")

    def _rebuild_purchase_items_with_constraints(self, cur: sqlite3.Cursor) -> None:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS purchase_items_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                purchase_id INTEGER NOT NULL,
                product_id INTEGER NOT NULL,
                qty INTEGER NOT NULL CHECK(qty > 0),
                unit_cost_usd REAL NOT NULL CHECK(unit_cost_usd >= 0),
                FOREIGN KEY(purchase_id) REFERENCES purchases(id) ON DELETE CASCADE,
                FOREIGN KEY(product_id) REFERENCES products(id),
                UNIQUE(purchase_id, product_id)
            )
            """
        )
        cur.execute(
            """
            INSERT OR IGNORE INTO purchase_items_new (id, purchase_id, product_id, qty, unit_cost_usd)
            SELECT id, purchase_id, product_id,
                   CASE WHEN qty <= 0 THEN 1 ELSE qty END,
                   MAX(unit_cost_usd, 0)
            FROM purchase_items
            """
        )
        cur.execute("DROP TABLE purchase_items")
        cur.execute("ALTER TABLE purchase_items_new RENAME TO purchase_items")

    def _rebuild_fx_rates_with_constraints(self, cur: sqlite3.Cursor) -> None:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS fx_rates_new (
                date TEXT PRIMARY KEY,
                usd_ars REAL NOT NULL CHECK(usd_ars > 0)
            )
            """
        )
        cur.execute(
            """
            INSERT OR IGNORE INTO fx_rates_new (date, usd_ars)
            SELECT date, CASE WHEN usd_ars <= 0 THEN 1 ELSE usd_ars END
            FROM fx_rates
            """
        )
        cur.execute("DROP TABLE fx_rates")
        cur.execute("ALTER TABLE fx_rates_new RENAME TO fx_rates")

    # ---------- Users ----------
    def list_users(self) -> list[User]:
        conn = self._conn()
        cur = conn.cursor()
        cur.execute(
            "SELECT id, username, role, active, COALESCE(must_change_pin, 0) FROM users WHERE active=1 ORDER BY username"
        )
        rows = cur.fetchall()
        conn.close()
        return [
            User(
                id=int(r[0]),
                username=str(r[1]),
                role=str(r[2]),
                active=int(r[3]),
                must_change_pin=int(r[4]),
            )
            for r in rows
        ]

    def _get_user_row(self, cur: sqlite3.Cursor, username: str):
        cur.execute(
            """
            SELECT id, username, role, active, pin,
                   COALESCE(failed_attempts, 0), locked_until, COALESCE(must_change_pin, 0)
            FROM users
            WHERE active=1 AND username=?
            """,
            (username,),
        )
        return cur.fetchone()

    def get_user_security_state(self, username: str) -> tuple[int, Optional[str]] | None:
        conn = self._conn()
        cur = conn.cursor()
        row = self._get_user_row(cur, username)
        conn.close()
        if not row:
            return None
        return int(row[5]), (str(row[6]) if row[6] is not None else None)

    def record_login_failure(self, username: str, max_attempts: int, lockout_seconds: int) -> tuple[int, Optional[str]]:
        conn = self._conn()
        cur = conn.cursor()
        row = self._get_user_row(cur, username)
        if not row:
            conn.close()
            return 0, None

        attempts = int(row[5]) + 1
        locked_until = None
        if attempts >= int(max_attempts):
            attempts = 0
            cur.execute(
                "UPDATE users SET failed_attempts=?, locked_until=datetime('now', ?) WHERE id=?",
                (attempts, f"+{int(lockout_seconds)} seconds", int(row[0])),
            )
            cur.execute("SELECT locked_until FROM users WHERE id=?", (int(row[0]),))
            locked_until = str(cur.fetchone()[0])
        else:
            cur.execute("UPDATE users SET failed_attempts=? WHERE id=?", (attempts, int(row[0])))
        conn.commit()
        conn.close()
        return attempts, locked_until

    def clear_login_guard(self, user_id: int) -> None:
        conn = self._conn()
        cur = conn.cursor()
        cur.execute("UPDATE users SET failed_attempts=0, locked_until=NULL WHERE id=?", (int(user_id),))
        conn.commit()
        conn.close()

    def authenticate_user(self, username: str, pin: str) -> Optional[User]:
        conn = self._conn()
        cur = conn.cursor()
        row = self._get_user_row(cur, username)
        if row and self._verify_pin(str(row[4]), pin):
            # transparent upgrade from legacy plain-text pins
            if not str(row[4]).startswith("pbkdf2_sha256$"):
                cur.execute("UPDATE users SET pin=? WHERE id=?", (self._hash_pin(pin), int(row[0])))
            cur.execute("UPDATE users SET failed_attempts=0, locked_until=NULL WHERE id=?", (int(row[0]),))
            conn.commit()
            conn.close()
            return User(
                id=int(row[0]),
                username=str(row[1]),
                role=str(row[2]),
                active=int(row[3]),
                must_change_pin=int(row[7]),
            )
        conn.close()
        return None

    def create_user(self, username: str, pin: str, role: str, must_change_pin: int = 0) -> int:
        conn = self._conn()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO users (username, pin, role, active, must_change_pin)
            VALUES (?, ?, ?, 1, ?)
            """,
            (username, self._hash_pin(pin), role, int(must_change_pin)),
        )
        uid = int(cur.lastrowid)
        conn.commit()
        conn.close()
        return uid
    
    def change_user_pin(self, user_id: int, current_pin: str, new_pin: str) -> bool:
        conn = self._conn()
        cur = conn.cursor()
        cur.execute("SELECT pin FROM users WHERE id=? AND active=1", (int(user_id),))
        row = cur.fetchone()
        if not row or not self._verify_pin(str(row[0]), current_pin):
            conn.close()
            return False

        cur.execute(
            "UPDATE users SET pin=?, must_change_pin=0 WHERE id=?",
            (self._hash_pin(new_pin), int(user_id)),
        )
        conn.commit()
        conn.close()
        return True

    # ---------- Products ----------
    def add_product(self, sku: str, name: str, cost_usd: float, price_usd: float, stock: int, min_stock: int) -> int:
        conn = self._conn()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO products (sku, name, cost_usd, price_usd, stock, min_stock)
            VALUES (?, ?, ?, ?, ?, ?)
        """, 
            (sku, name, cost_usd, price_usd, stock, min_stock)
        )
        pid = cur.lastrowid
        conn.commit()
        conn.close()
        return int(pid)

    def upsert_product(
        self, sku: str, name: str, cost_usd: float, price_usd: float, stock: int, min_stock: int
    ) -> int:
        conn = self._conn()
        cur = conn.cursor()

        cur.execute("SELECT id FROM products WHERE sku = ?", (sku,))
        row = cur.fetchone()
        if row:
            pid = int(row[0])
            cur.execute(
                """
                UPDATE products
                SET name=?, cost_usd=?, price_usd=?, stock=?, min_stock=?, active=1
                WHERE sku=?
            """,
                (name, cost_usd, price_usd, stock, min_stock, sku),
            )
        else:
            cur.execute(
                """
                INSERT INTO products (sku, name, cost_usd, price_usd, stock, min_stock)
                VALUES (?, ?, ?, ?, ?, ?)
            """,
                (sku, name, cost_usd, price_usd, stock, min_stock),
            )
            pid = int(cur.lastrowid)

        conn.commit()
        conn.close()
        return int(pid)

    def list_products(self) -> list[Product]:
        conn = self._conn()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, sku, name, cost_usd, price_usd, stock, min_stock, active
            FROM products
            WHERE active = 1
            ORDER BY name
        """
        )
        rows = cur.fetchall()
        conn.close()
        return [
            Product(
                id=int(r[0]),
                sku=str(r[1]),
                name=str(r[2]),
                cost_usd=float(r[3]),
                price_usd=float(r[4]),
                stock=int(r[5]),
                min_stock=int(r[6]),
                active=int(r[7]),
            )
            for r in rows
        ]
    
    def list_top_critical_stock(self, limit: int = 10) -> list[tuple[str, int, int]]:
        conn = self._conn()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT sku, stock, min_stock
            FROM products
            WHERE active=1
            ORDER BY (stock - min_stock) ASC, name ASC
            LIMIT ?
            """,
            (int(limit),),
        )
        rows = cur.fetchall()
        conn.close()
        return [(str(r[0]), int(r[1]), int(r[2])) for r in rows]

    def deactivate_product(self, product_id: int) -> bool:
        conn = self._conn()
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE products
            SET active=0
            WHERE id=? AND active=1
            """,
            (int(product_id),),
        )
        changed = cur.rowcount > 0
        conn.commit()
        conn.close()
        return bool(changed)

    def get_product_by_sku(self, sku: str) -> Optional[Product]:
        conn = self._conn()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, sku, name, cost_usd, price_usd, stock, min_stock, active
            FROM products
            WHERE active=1 AND sku=?
        """,
            (sku,),
        )
        r = cur.fetchone()
        conn.close()
        if not r:
            return None
        return Product(
            id=int(r[0]),
            sku=str(r[1]),
            name=str(r[2]),
            cost_usd=float(r[3]),
            price_usd=float(r[4]),
            stock=int(r[5]),
            min_stock=int(r[6]),
            active=int(r[7]),
        )

    def get_product_by_id(self, product_id: int) -> Optional[Product]:
        conn = self._conn()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, sku, name, cost_usd, price_usd, stock, min_stock, active
            FROM products
            WHERE active=1 AND id=?
        """,
            (int(product_id),),
        )
        r = cur.fetchone()
        conn.close()
        if not r:
            return None
        return Product(
            id=int(r[0]),
            sku=str(r[1]),
            name=str(r[2]),
            cost_usd=float(r[3]),
            price_usd=float(r[4]),
            stock=int(r[5]),
            min_stock=int(r[6]),
            active=int(r[7]),
        )

    def append_ledger(
        self,
        datetime_iso: str,
        product_id: int,
        movement_type: str,
        qty_delta: int,
        stock_after: int,
        unit_value_usd: float,
        reference_type: str,
        reference_id: int,
        actor_user_id: Optional[int],
        notes: Optional[str],
    ) -> None:
        conn = self._conn()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO stock_ledger (
                datetime, product_id, movement_type, qty_delta, stock_after, unit_value_usd,
                reference_type, reference_id, actor_user_id, notes
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                datetime_iso,
                int(product_id),
                movement_type,
                int(qty_delta),
                int(stock_after),
                float(unit_value_usd),
                reference_type,
                int(reference_id),
                actor_user_id,
                notes,
            ),
        )
        conn.commit()
        conn.close()

    def recent_ledger(self, limit: int = 100) -> list[LedgerEntry]:
        conn = self._conn()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, datetime, product_id, movement_type, qty_delta, stock_after, unit_value_usd,
                   reference_type, reference_id, actor_user_id, notes
            FROM stock_ledger
            ORDER BY datetime DESC, id DESC
            LIMIT ?
            """,
            (int(limit),),
        )
        rows = cur.fetchall()
        conn.close()
        return [LedgerEntry(*r) for r in rows]

    # ---------- FX ----------
    def integrity_check(self) -> str:
        conn = self._conn()
        cur = conn.cursor()
        cur.execute("PRAGMA integrity_check")
        row = cur.fetchone()
        conn.close()
        return str(row[0]) if row else "unknown"

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
        cur.execute(
            """
            INSERT INTO fx_rates (date, usd_ars) VALUES (?, ?)
            ON CONFLICT(date) DO UPDATE SET usd_ars=excluded.usd_ars
        """,
            (date_iso, float(usd_ars)),
        )
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
    def create_sale(self, datetime_iso: str, fx_usd_ars: float, notes: Optional[str], items: Iterable[dict], actor_user_id: Optional[int] = None) -> int:
        conn = self._conn()
        cur = conn.cursor()

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

        cur.execute(
            """
            INSERT INTO sales (datetime, total_usd, fx_usd_ars, total_ars, notes, actor_user_id)
            VALUES (?, ?, ?, ?, ?, ?)
        """,
            (datetime_iso, float(total_usd), float(fx_usd_ars), float(total_ars), notes, actor_user_id),
        )
        sale_id = int(cur.lastrowid)

        for it in items:
            cur.execute(
                """
                INSERT INTO sale_items (sale_id, product_id, qty, unit_price_usd)
                VALUES (?, ?, ?, ?)
            """,
                (sale_id, int(it["product_id"]), int(it["qty"]), float(it["unit_price_usd"])),
            )

            cur.execute("UPDATE products SET stock = stock - ? WHERE id = ? AND active=1", (int(it["qty"]), int(it["product_id"])))
            cur.execute("SELECT stock FROM products WHERE id=?", (int(it["product_id"]),))
            stock_after = int(cur.fetchone()[0])
            cur.execute(
                """
                INSERT INTO stock_ledger (
                    datetime, product_id, movement_type, qty_delta, stock_after, unit_value_usd,
                    reference_type, reference_id, actor_user_id, notes
                ) VALUES (?, ?, 'sale', ?, ?, ?, 'sale', ?, ?, ?)
                """,
                (datetime_iso, int(it["product_id"]), -int(it["qty"]), stock_after, float(it["unit_price_usd"]), sale_id, actor_user_id, notes),
            )

        conn.commit()
        conn.close()
        return sale_id

    def list_sales_between(self, start_iso: str, end_iso: str) -> list[SaleHeader]:
        conn = self._conn()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, datetime, total_usd, fx_usd_ars, total_ars, notes
            FROM sales
            WHERE datetime >= ? AND datetime < ?
            ORDER BY datetime DESC
        """,
            (start_iso, end_iso),
        )
        rows = cur.fetchall()
        conn.close()
        return [
            SaleHeader(
                id=int(r[0]),
                datetime=str(r[1]),
                total_usd=float(r[2]),
                fx_usd_ars=float(r[3]),
                total_ars=float(r[4]),
                notes=(r[5] if r[5] is not None else None),
            )
            for r in rows
        ]
    def monthly_sales_totals(self, months: int = 6) -> list[tuple[str, float]]:
        conn = self._conn()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT substr(datetime,1,7) AS ym, COALESCE(SUM(total_usd),0)
            FROM sales
            GROUP BY ym
            ORDER BY ym DESC
            LIMIT ?
            """,
            (int(months),),
        )
        rows = list(reversed(cur.fetchall()))
        conn.close()
        return [(str(r[0]), float(r[1])) for r in rows]

    def cumulative_profit_series(self) -> list[tuple[str, float]]:
        conn = self._conn()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT substr(s.datetime,1,10) as d,
                   COALESCE(SUM(si.qty * (si.unit_price_usd - p.cost_usd)),0)
            FROM sale_items si
            JOIN sales s ON s.id = si.sale_id
            JOIN products p ON p.id = si.product_id
            GROUP BY d ORDER BY d
            """
        )
        rows = cur.fetchall()
        conn.close()
        out: list[tuple[str, float]] = []
        acc = 0.0
        for d, val in rows:
            acc += float(val)
            out.append((str(d), acc))
        return out

    def get_sale_header(self, sale_id: int) -> Optional[SaleHeader]:
        conn = self._conn()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, datetime, total_usd, fx_usd_ars, total_ars, notes
            FROM sales
            WHERE id = ?
        """,
            (int(sale_id),),
        )
        r = cur.fetchone()
        conn.close()
        if not r:
            return None
        return SaleHeader(
            id=int(r[0]), datetime=str(r[1]), total_usd=float(r[2]), fx_usd_ars=float(r[3]), total_ars=float(r[4]), notes=(r[5] if r[5] is not None else None)
        )

    def sale_items_for_sale(self, sale_id: int) -> list[SaleLine]:
        conn = self._conn()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT p.sku, p.name, si.qty, si.unit_price_usd,
                   (si.qty * si.unit_price_usd) AS line_total_usd,
                   p.cost_usd,
                   (si.qty * (si.unit_price_usd - p.cost_usd)) AS line_margin_usd
            FROM sale_items si
            JOIN products p ON p.id = si.product_id
            WHERE si.sale_id = ?
            ORDER BY p.name
        """,
            (int(sale_id),),
        )
        rows = cur.fetchall()
        conn.close()
        return [SaleLine(sku=str(r[0]), name=str(r[1]), qty=int(r[2]), unit_price_usd=float(r[3]), line_total_usd=float(r[4]), cost_usd=float(r[5]), line_margin_usd=float(r[6])) for r in rows]
    
    def sales_summary_between(self, start_iso: str, end_iso: str) -> tuple[tuple[int, float, float, float], list[tuple]]:
        conn = self._conn()
        cur = conn.cursor()

        cur.execute(
            """
            SELECT COUNT(*),
                   COALESCE(SUM(total_usd), 0),
                   COALESCE(SUM(total_ars), 0)
            FROM sales
            WHERE datetime >= ? AND datetime < ?
        """,
            (start_iso, end_iso),
        )
        c, total_usd, total_ars = cur.fetchone()

        cur.execute(
            """
            SELECT COALESCE(SUM(si.qty * (si.unit_price_usd - p.cost_usd)), 0)
            FROM sale_items si
            JOIN sales s ON s.id = si.sale_id
            JOIN products p ON p.id = si.product_id
            WHERE s.datetime >= ? AND s.datetime < ?
        """,
            (start_iso, end_iso),
        )
        margin_usd = cur.fetchone()[0]

        cur.execute(
            """
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
        """,
            (start_iso, end_iso),
        )
        top = cur.fetchall()

        conn.close()
        return (int(c), float(total_usd), float(total_ars), float(margin_usd)), top
    

    def create_purchase_with_items(
        self,
        datetime_iso: str,
        vendor: Optional[str],
        total_usd: float,
        notes: Optional[str],
        items: Iterable[dict],
        actor_user_id: Optional[int] = None,
    ) -> int:
        conn = self._conn()
        cur = conn.cursor()
        try:
            cur.execute(
                """
                INSERT INTO purchases (datetime, vendor, total_usd, notes, actor_user_id)
                VALUES (?, ?, ?, ?, ?)
            """,
                (datetime_iso, vendor, float(total_usd), notes, actor_user_id),
            )
            purchase_id = int(cur.lastrowid)

            for it in items:
                pid = int(it["product_id"])
                qty = int(it["qty"])
                unit_cost = float(it["unit_cost_usd"])

                cur.execute(
                    """
                    SELECT stock, cost_usd
                    FROM products
                    WHERE id = ? AND active = 1
                """,
                    (pid,),
                )
                row = cur.fetchone()
                if not row:
                    raise ValueError(f"Product not found/active: {pid}")

                old_stock = int(row[0])
                old_cost = float(row[1])
                new_stock = old_stock + qty
                new_cost = ((old_stock * old_cost) + (qty * unit_cost)) / new_stock if new_stock > 0 else unit_cost

                cur.execute(
                    """
                    INSERT INTO purchase_items (purchase_id, product_id, qty, unit_cost_usd)
                    VALUES (?, ?, ?, ?)
                """,
                    (purchase_id, pid, qty, unit_cost),
                )

                cur.execute(
                    """
                    UPDATE products
                    SET stock = ?, cost_usd = ?
                    WHERE id = ? AND active = 1
                """,
                    (new_stock, new_cost, pid),
                )
                cur.execute(
                    """
                    INSERT INTO stock_ledger (
                        datetime, product_id, movement_type, qty_delta, stock_after, unit_value_usd,
                        reference_type, reference_id, actor_user_id, notes
                    ) VALUES (?, ?, 'purchase', ?, ?, ?, 'purchase', ?, ?, ?)
                    """,
                    (datetime_iso, pid, qty, new_stock, unit_cost, purchase_id, actor_user_id, notes),
                )

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
        cur.execute(
            """
            INSERT INTO purchases (datetime, vendor, total_usd, notes)
            VALUES (?, ?, ?, ?)
        """,
            (datetime_iso, vendor, float(total_usd), notes),
        )
        pid = int(cur.lastrowid)
        conn.commit()
        conn.close()
        return pid

    def add_purchase_item(self, purchase_id: int, product_id: int, qty: int, unit_cost_usd: float) -> None:
        conn = self._conn()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO purchase_items (purchase_id, product_id, qty, unit_cost_usd)
            VALUES (?, ?, ?, ?)
        """,
            (int(purchase_id), int(product_id), int(qty), float(unit_cost_usd)),
        )
        conn.commit()
        conn.close()

    def list_purchases_between(self, start_iso: str, end_iso: str) -> list[PurchaseHeader]:
        conn = self._conn()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, datetime, vendor, total_usd, notes
            FROM purchases
            WHERE datetime >= ? AND datetime < ?
            ORDER BY datetime DESC
        """,
            (start_iso, end_iso),
        )
        rows = cur.fetchall()
        conn.close()
        return [
            PurchaseHeader(
                id=int(r[0]), datetime=str(r[1]), vendor=(r[2] if r[2] is not None else None), total_usd=float(r[3]), notes=(r[4] if r[4] is not None else None)
            )
            for r in rows
        ]

    def purchase_items_for_purchase(self, purchase_id: int) -> list[PurchaseLine]:
        conn = self._conn()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT p.sku, p.name, pi.qty, pi.unit_cost_usd,
                   (pi.qty * pi.unit_cost_usd) AS line_total_usd
            FROM purchase_items pi
            JOIN products p ON p.id = pi.product_id
            WHERE pi.purchase_id = ?
            ORDER BY p.name
        """,
            (int(purchase_id),),
        )
        rows = cur.fetchall()
        conn.close()
        return [PurchaseLine(sku=str(r[0]), name=str(r[1]), qty=int(r[2]), unit_cost_usd=float(r[3]), line_total_usd=float(r[4])) for r in rows]

    @staticmethod
    def _hash_pin(pin: str, *, rounds: int = 200_000, salt: str | None = None) -> str:
        salt = salt or secrets.token_hex(16)
        digest = hashlib.pbkdf2_hmac("sha256", pin.encode("utf-8"), bytes.fromhex(salt), rounds).hex()
        return f"pbkdf2_sha256${rounds}${salt}${digest}"

    @staticmethod
    def _verify_pin(stored: str, provided: str) -> bool:
        if stored.startswith("pbkdf2_sha256$"):
            try:
                _algo, rounds_s, salt, digest = stored.split("$", 3)
                rounds = int(rounds_s)
                candidate = hashlib.pbkdf2_hmac(
                    "sha256",
                    provided.encode("utf-8"),
                    bytes.fromhex(salt),
                    rounds,
                ).hex()
                return hmac.compare_digest(candidate, digest)
            except Exception:
                return False
        return hmac.compare_digest(stored, provided)