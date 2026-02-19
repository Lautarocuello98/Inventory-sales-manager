from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime, timedelta
import logging


log = logging.getLogger(__name__)


class SalesView:
    def __init__(self, notebook: ttk.Notebook, app):
        self.app = app
        self.frame = ttk.Frame(notebook)
        notebook.add(self.frame, text="Sales")

        self.cart: list[dict] = []
        self.sale_pick = tk.StringVar()
        self.sale_total_var = tk.StringVar(value="Total USD: 0.00 | Total ARS: 0.00")

        self.sale_all_choices: list[str] = []
        self.sale_sku_map: dict[str, str] = {}

        self._build()
        self.refresh()

    def _build(self):
        tab = self.frame

        top = ttk.LabelFrame(tab, text="Add item to cart")
        top.pack(fill="x", padx=10, pady=10)

        ttk.Label(top, text="Search product (SKU or name)").grid(row=0, column=0, padx=10, pady=8, sticky="w")

        self.combo = ttk.Combobox(top, textvariable=self.sale_pick, width=56)
        self.combo.grid(row=0, column=1, padx=10, pady=8, sticky="w")
        self.combo.bind("<KeyRelease>", lambda e: self._filter_combobox(self.combo, self.sale_all_choices, self.sale_pick.get()))

        ttk.Label(top, text="Qty").grid(row=0, column=2, padx=10, pady=8, sticky="w")
        self.qty_e = ttk.Entry(top, width=10)
        self.qty_e.grid(row=0, column=3, padx=10, pady=8, sticky="w")

        ttk.Button(top, text="Add to cart", style="Big.TButton", command=self.add_to_cart)\
            .grid(row=0, column=4, padx=10, pady=8)

        self.combo.bind("<Return>", lambda _e: self.add_to_cart())
        self.qty_e.bind("<Return>", lambda _e: self.add_to_cart())

        mid = ttk.Frame(tab)
        mid.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        cart_box = ttk.LabelFrame(mid, text="Cart")
        cart_box.pack(side="left", fill="both", expand=True, padx=(0, 10))

        cols = ("sku", "name", "qty", "unit", "line")
        self.cart_tree = ttk.Treeview(cart_box, columns=cols, show="headings", height=16, style="Modern.Treeview")
        heads = {"sku": "SKU", "name": "Name", "qty": "Qty", "unit": "Unit USD", "line": "Line USD"}
        widths = {"sku": 120, "name": 420, "qty": 70, "unit": 110, "line": 110}
        for c in cols:
            self.cart_tree.heading(c, text=heads[c])
            self.cart_tree.column(c, width=widths[c], anchor="w")
        self.cart_tree.pack(fill="both", expand=True, padx=10, pady=10)

        btnrow = ttk.Frame(cart_box)
        btnrow.pack(fill="x", padx=10, pady=(0, 10))
        ttk.Button(btnrow, text="Remove selected", command=self.remove_selected).pack(side="left")
        ttk.Button(btnrow, text="Clear cart", command=self.clear_cart).pack(side="left", padx=10)

        right = ttk.LabelFrame(mid, text="Confirm sale")
        right.pack(side="right", fill="y")

        ttk.Label(right, text="Notes (optional)").pack(anchor="w", padx=10, pady=(10, 4))
        self.notes = tk.Text(right, width=34, height=6)
        self.notes.pack(padx=10)

        ttk.Label(right, textvariable=self.sale_total_var).pack(anchor="w", padx=10, pady=10)

        ttk.Button(right, text="Confirm sale", style="Big.TButton", command=self.confirm_sale)\
            .pack(fill="x", padx=10, pady=(0, 10))

        self.notes.bind("<Control-Return>", lambda _e: self.confirm_sale())

        # Sales history
        hist = ttk.LabelFrame(tab, text="Sales History (double click to view details)")
        hist.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        top2 = ttk.Frame(hist)
        top2.pack(fill="x", padx=10, pady=8)

        ttk.Label(top2, text="Window").pack(side="left")
        self.hist_window = tk.StringVar(value="7")
        ttk.Combobox(top2, textvariable=self.hist_window, values=["7", "30", "90"], width=6, state="readonly")\
            .pack(side="left", padx=10)
        ttk.Label(top2, text="days").pack(side="left")
        ttk.Button(top2, text="Refresh", command=self.refresh_history).pack(side="left", padx=10)

        cols = ("id", "dt", "usd", "fx", "ars", "notes")
        self.sales_tree = ttk.Treeview(hist, columns=cols, show="headings", height=8, style="Modern.Treeview")
        heads = {"id": "Sale ID", "dt": "Datetime", "usd": "Total USD", "fx": "FX", "ars": "Total ARS", "notes": "Notes"}
        widths = {"id": 90, "dt": 200, "usd": 110, "fx": 90, "ars": 120, "notes": 520}
        for c in cols:
            self.sales_tree.heading(c, text=heads[c])
            self.sales_tree.column(c, width=widths[c], anchor="w")
        self.sales_tree.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self.sales_tree.bind("<Double-1>", self.open_sale_details)

    def _filter_combobox(self, combo: ttk.Combobox, all_choices: list[str], typed: str):
        typed = typed.strip().lower()
        combo["values"] = all_choices if not typed else [c for c in all_choices if typed in c.lower()]

    def refresh_product_choices(self):
        rows = self.app.inventory.list_products()
        choices = []
        mapping = {}
        for p in rows:
            label = f"{p.sku} — {p.name} (stock: {p.stock})"
            choices.append(label)
            mapping[label] = p.sku
        self.sale_all_choices = choices
        self.sale_sku_map = mapping
        self.combo["values"] = choices

    def refresh(self):
        self.refresh_product_choices()
        self.refresh_cart_view()
        self.refresh_history()

    def _parse_int(self, s: str, field: str, min_value: int = 1) -> int:
        try:
            v = int(float(s))
        except Exception:
            raise ValueError(f"{field} must be an integer.")
        if v < min_value:
            raise ValueError(f"{field} must be >= {min_value}.")
        return v

    def add_to_cart(self):
        picked = self.sale_pick.get().strip()
        if not picked:
            messagebox.showwarning("Validation", "Select a product.")
            return

        sku = self.sale_sku_map.get(picked)
        if not sku:
            messagebox.showwarning("Validation", "Pick a product from the dropdown list.")
            return

        try:
            qty = self._parse_int(self.qty_e.get().strip(), "Qty", 1)
        except Exception as e:
            messagebox.showwarning("Validation", str(e))
            return

        prod = self.app.inventory.get_product_by_sku(sku)
        if qty > prod.stock:
            messagebox.showwarning("Stock", f"Not enough stock. Available: {prod.stock}")
            return

        for it in self.cart:
            if it["product_id"] == prod.id:
                new_qty = it["qty"] + qty
                if new_qty > prod.stock:
                    messagebox.showwarning("Stock", f"Not enough stock. Available: {prod.stock}")
                    return
                it["qty"] = new_qty
                self.refresh_cart_view()
                self.qty_e.delete(0, tk.END)
                self.app.toast("Updated qty in cart.", kind="success", ms=1500)
                return

        self.cart.append({
            "product_id": prod.id,
            "sku": prod.sku,
            "name": prod.name,
            "qty": qty,
            "unit_price_usd": float(prod.price_usd),
        })
        self.refresh_cart_view()
        self.qty_e.delete(0, tk.END)
        self.app.toast("Added to cart.", kind="success", ms=1500)

    def refresh_cart_view(self):
        for item in self.cart_tree.get_children():
            self.cart_tree.delete(item)

        total_usd = 0.0
        for it in self.cart:
            line = it["qty"] * it["unit_price_usd"]
            total_usd += line
            self.cart_tree.insert("", "end", values=(
                it["sku"], it["name"], it["qty"], f"{it['unit_price_usd']:.2f}", f"{line:.2f}"
            ))

        try:
            fx = self.app.fx.get_today_rate()
            self.app.fx_var.set(f"FX (USD→ARS): {fx:.4f}")
            self.sale_total_var.set(f"Total USD: {total_usd:.2f} | Total ARS: {(total_usd * fx):.2f}")
        except Exception:
            self.sale_total_var.set(f"Total USD: {total_usd:.2f} | Total ARS: (update FX)")

    def remove_selected(self):
        sel = self.cart_tree.selection()
        if not sel:
            return
        sku = self.cart_tree.item(sel[0], "values")[0]
        self.cart = [it for it in self.cart if it["sku"] != sku]
        self.refresh_cart_view()
        self.app.toast("Removed from cart.", kind="info", ms=1500)

    def clear_cart(self):
        self.cart = []
        self.refresh_cart_view()
        self.app.toast("Cart cleared.", kind="info", ms=1500)

    def confirm_sale(self):
        if not self.cart:
            messagebox.showwarning("Empty", "Cart is empty.")
            return

        notes = self.notes.get("1.0", "end").strip() or None
        items = [{"product_id": it["product_id"], "qty": it["qty"], "unit_price_usd": it["unit_price_usd"]} for it in self.cart]

        try:
            if not self.app.can("admin", "seller"):
                raise PermissionError("Tu rol no puede registrar ventas.")
            sale_id = self.app.sales.create_sale(notes, items, actor_user_id=self.app.current_user.id)
        except Exception as e:
            self.app.handle_error("Sale failed", e, "Sale failed.")
            return

        messagebox.showinfo("OK", f"Sale saved. ID: {sale_id}")
        self.app.toast(f"Sale saved (ID {sale_id}).", kind="success")
        self.notes.delete("1.0", "end")
        self.clear_cart()
        self.app.refresh_all(silent_fx=True)

    # ---------- history ----------
    def refresh_history(self):
        try:
            days = int(self.hist_window.get())
        except Exception:
            days = 7

        end = datetime.now().replace(microsecond=0)
        start = end - timedelta(days=days)

        rows = self.app.sales.list_sales_between(start.isoformat(sep=" "), end.isoformat(sep=" "))

        for item in self.sales_tree.get_children():
            self.sales_tree.delete(item)

        for s in rows:
            self.sales_tree.insert("", "end", values=(
                s.id, s.datetime, f"{s.total_usd:.2f}", f"{s.fx_usd_ars:.4f}", f"{s.total_ars:.2f}", (s.notes or "")[:140]
            ))

    def open_sale_details(self, _evt=None):
        sel = self.sales_tree.selection()
        if not sel:
            return
        sale_id = int(self.sales_tree.item(sel[0], "values")[0])

        header = self.app.sales.get_sale_header(sale_id)
        items = self.app.sales.sale_items_for_sale(sale_id)
        if not header:
            return

        win = tk.Toplevel(self.app)
        win.title(f"Sale Details #{sale_id}")
        win.geometry("980x520")

        h = ttk.LabelFrame(win, text="Header")
        h.pack(fill="x", padx=10, pady=10)

        ttk.Label(h, text=f"Datetime: {header.datetime}").pack(anchor="w", padx=10, pady=2)
        ttk.Label(h, text=f"Total USD: {header.total_usd:.2f} | FX: {header.fx_usd_ars:.4f} | Total ARS: {header.total_ars:.2f}")\
            .pack(anchor="w", padx=10, pady=2)
        ttk.Label(h, text=f"Notes: {header.notes or ''}").pack(anchor="w", padx=10, pady=2)

        box = ttk.LabelFrame(win, text="Items")
        box.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        cols = ("sku", "name", "qty", "unit", "line", "cost", "margin")
        tree = ttk.Treeview(box, columns=cols, show="headings", height=16, style="Modern.Treeview")
        heads = {"sku": "SKU", "name": "Name", "qty": "Qty", "unit": "Unit USD", "line": "Line USD",
                 "cost": "Cost USD", "margin": "Line Profit USD"}
        widths = {"sku": 120, "name": 380, "qty": 70, "unit": 110, "line": 110, "cost": 110, "margin": 140}
        for c in cols:
            tree.heading(c, text=heads[c])
            tree.column(c, width=widths[c], anchor="w")
        tree.pack(fill="both", expand=True, padx=10, pady=10)

        total_margin = 0.0
        for it in items:
            total_margin += float(it.line_margin_usd)
            tree.insert("", "end", values=(
                it.sku, it.name, it.qty, f"{it.unit_price_usd:.2f}", f"{it.line_total_usd:.2f}",
                f"{it.cost_usd:.2f}", f"{it.line_margin_usd:.2f}"
            ))

        ttk.Label(win, text=f"Profit USD (this sale): {total_margin:.2f}").pack(anchor="w", padx=14, pady=(0, 10))
