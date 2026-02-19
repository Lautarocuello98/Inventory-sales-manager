from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime, timedelta
import logging

log = logging.getLogger(__name__)

class RestockView:
    def __init__(self, notebook: ttk.Notebook, app):
        self.app = app
        self.frame = ttk.Frame(notebook)
        notebook.add(self.frame, text="Restock")

        self.restock_cart: list[dict] = []
        self.restock_pick = tk.StringVar()
        self.restock_total_var = tk.StringVar(value="Total USD: 0.00")

        self.restock_all_choices: list[str] = []
        self.restock_sku_map: dict[str, str] = {}

        self._build()
        self.refresh()

    def _build(self):
        tab = self.frame

        top = ttk.LabelFrame(tab, text="Add restock item")
        top.pack(fill="x", padx=10, pady=10)
        top.columnconfigure(1, weight=1)

        ttk.Label(top, text="Search product (SKU or name)").grid(row=0, column=0, padx=10, pady=8, sticky="w")

        self.combo = ttk.Combobox(top, textvariable=self.restock_pick, width=56)
        self.combo.grid(row=0, column=1, padx=10, pady=8, sticky="ew")
        self.combo.bind("<KeyRelease>", lambda e: self._filter_combobox(self.combo, self.restock_all_choices, self.restock_pick.get()))

        ttk.Label(top, text="Qty").grid(row=0, column=2, padx=10, pady=8, sticky="w")
        self.qty_e = ttk.Entry(top, width=10)
        self.qty_e.grid(row=0, column=3, padx=10, pady=8, sticky="w")

        ttk.Label(top, text="Unit cost USD").grid(row=0, column=4, padx=10, pady=8, sticky="w")
        self.cost_e = ttk.Entry(top, width=12)
        self.cost_e.grid(row=0, column=5, padx=10, pady=8, sticky="w")

        ttk.Button(top, text="Add", style="Big.TButton", command=self.add_item)\
            .grid(row=1, column=0, columnspan=7, padx=10, pady=(0, 8), sticky="e")

        mid = ttk.Frame(tab)
        mid.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        box = ttk.LabelFrame(mid, text="Restock cart")
        box.pack(side="left", fill="both", expand=True, padx=(0, 10))

        cols = ("sku", "name", "qty", "unit", "line")
        self.tree = ttk.Treeview(box, columns=cols, show="headings", height=12)
        heads = {"sku": "SKU", "name": "Name", "qty": "Qty", "unit": "Unit cost USD", "line": "Line USD"}
        widths = {"sku": 120, "name": 420, "qty": 70, "unit": 130, "line": 110}
        for c in cols:
            self.tree.heading(c, text=heads[c])
            self.tree.column(c, width=widths[c], anchor="w")
        self.tree.pack(fill="both", expand=True, padx=10, pady=10)

        btnrow = ttk.Frame(box)
        btnrow.pack(fill="x", padx=10, pady=(0, 10))
        ttk.Button(btnrow, text="Remove selected", command=self.remove_selected).pack(side="left")
        ttk.Button(btnrow, text="Clear", command=self.clear_cart).pack(side="left", padx=10)

        right = ttk.LabelFrame(mid, text="Confirm restock")
        right.pack(side="right", fill="y")

        ttk.Label(right, text="Vendor (optional)").pack(anchor="w", padx=10, pady=(10, 4))
        self.vendor_e = ttk.Entry(right, width=34)
        self.vendor_e.pack(padx=10)

        ttk.Label(right, text="Notes (optional)").pack(anchor="w", padx=10, pady=(10, 4))
        self.notes = tk.Text(right, width=34, height=5)
        self.notes.pack(padx=10)

        ttk.Label(right, textvariable=self.restock_total_var).pack(anchor="w", padx=10, pady=10)

        ttk.Button(right, text="Confirm restock", style="Big.TButton", command=self.confirm)\
            .pack(fill="x", padx=10, pady=(0, 10))

        # Purchases history
        hist = ttk.LabelFrame(tab, text="Purchases History (double click to view details)")
        hist.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        top2 = ttk.Frame(hist)
        top2.pack(fill="x", padx=10, pady=8)

        ttk.Label(top2, text="Window").pack(side="left")
        self.hist_window = tk.StringVar(value="30")
        ttk.Combobox(top2, textvariable=self.hist_window, values=["7", "30", "90"], width=6, state="readonly")\
            .pack(side="left", padx=10)
        ttk.Label(top2, text="days").pack(side="left")
        ttk.Button(top2, text="Refresh", command=self.refresh_history).pack(side="left", padx=10)

        cols = ("id", "dt", "vendor", "total", "notes")
        self.purchases_tree = ttk.Treeview(hist, columns=cols, show="headings", height=8)
        heads = {"id": "Purchase ID", "dt": "Datetime", "vendor": "Vendor", "total": "Total USD", "notes": "Notes"}
        widths = {"id": 110, "dt": 200, "vendor": 160, "total": 120, "notes": 520}
        for c in cols:
            self.purchases_tree.heading(c, text=heads[c])
            self.purchases_tree.column(c, width=widths[c], anchor="w")
        self.purchases_tree.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self.purchases_tree.bind("<Double-1>", self.open_purchase_details)

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
        self.restock_all_choices = choices
        self.restock_sku_map = mapping
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

    def _parse_float(self, s: str, field: str, min_value: float = 0.0) -> float:
        try:
            v = float(s)
        except Exception:
            raise ValueError(f"{field} must be a number.")
        if v < min_value:
            raise ValueError(f"{field} must be >= {min_value}.")
        return v

    def add_item(self):
        picked = self.restock_pick.get().strip()
        if not picked:
            messagebox.showwarning("Validation", "Select a product.")
            return

        sku = self.restock_sku_map.get(picked)
        if not sku:
            messagebox.showwarning("Validation", "Pick a product from the dropdown list.")
            return

        try:
            qty = self._parse_int(self.qty_e.get().strip(), "Qty", 1)
            cost = self._parse_float(self.cost_e.get().strip(), "Unit cost USD", 0.0)
        except Exception as e:
            messagebox.showwarning("Validation", str(e))
            return

        prod = self.app.inventory.get_product_by_sku(sku)

        for it in self.restock_cart:
            if it["product_id"] == prod.id:
                it["qty"] += qty
                it["unit_cost_usd"] = float(cost)
                self.refresh_cart_view()
                self.qty_e.delete(0, tk.END)
                self.app.toast("Updated restock qty.", kind="success", ms=1500)
                return

        self.restock_cart.append({
            "product_id": prod.id,
            "sku": prod.sku,
            "name": prod.name,
            "qty": qty,
            "unit_cost_usd": float(cost),
        })
        self.refresh_cart_view()
        self.qty_e.delete(0, tk.END)
        self.app.toast("Added to restock cart.", kind="success", ms=1500)

    def refresh_cart_view(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

        total = 0.0
        for it in self.restock_cart:
            line = it["qty"] * it["unit_cost_usd"]
            total += line
            self.tree.insert("", "end", values=(
                it["sku"], it["name"], it["qty"], f"{it['unit_cost_usd']:.2f}", f"{line:.2f}"
            ))
        self.restock_total_var.set(f"Total USD: {total:.2f}")

    def remove_selected(self):
        sel = self.tree.selection()
        if not sel:
            return
        sku = self.tree.item(sel[0], "values")[0]
        self.restock_cart = [it for it in self.restock_cart if it["sku"] != sku]
        self.refresh_cart_view()
        self.app.toast("Removed restock line.", kind="info", ms=1500)

    def clear_cart(self):
        self.restock_cart = []
        self.refresh_cart_view()
        self.app.toast("Restock cart cleared.", kind="info", ms=1500)

    def confirm(self):
        if not self.restock_cart:
            messagebox.showwarning("Empty", "Restock cart is empty.")
            return

        vendor = self.vendor_e.get().strip() or None
        notes = self.notes.get("1.0", "end").strip() or None
        items = [{"product_id": it["product_id"], "qty": it["qty"], "unit_cost_usd": it["unit_cost_usd"]} for it in self.restock_cart]

        try:
            if not self.app.can("admin", "seller"):
                raise PermissionError("Tu rol no puede registrar reposiciones.")
            purchase_id = self.app.purchases.create_purchase(vendor=vendor, notes=notes, items=items, actor_user_id=self.app.current_user.id)
        except Exception as e:
            self.app.handle_error("Restock failed", e, "Restock failed.")
            return

        messagebox.showinfo("OK", f"Restock saved. Purchase ID: {purchase_id}")
        self.app.toast(f"Restock saved (ID {purchase_id}).", kind="success")
        self.vendor_e.delete(0, tk.END)
        self.notes.delete("1.0", "end")
        self.clear_cart()
        self.app.refresh_all(silent_fx=True)

    # ---------- purchases history ----------
    def refresh_history(self):
        try:
            days = int(self.hist_window.get())
        except Exception:
            days = 30

        end = datetime.now().replace(microsecond=0)
        start = end - timedelta(days=days)

        rows = self.app.purchases.list_purchases_between(start.isoformat(sep=" "), end.isoformat(sep=" "))

        for item in self.purchases_tree.get_children():
            self.purchases_tree.delete(item)

        for p in rows:
            self.purchases_tree.insert("", "end", values=(
                p.id, p.datetime, p.vendor or "", f"{p.total_usd:.2f}", (p.notes or "")[:140]
            ))

    def open_purchase_details(self, _evt=None):
        sel = self.purchases_tree.selection()
        if not sel:
            return
        purchase_id = int(self.purchases_tree.item(sel[0], "values")[0])
        items = self.app.purchases.purchase_items_for_purchase(purchase_id)

        win = tk.Toplevel(self.app)
        win.title(f"Purchase Details #{purchase_id}")
        win.geometry("900x480")

        box = ttk.LabelFrame(win, text="Items")
        box.pack(fill="both", expand=True, padx=10, pady=10)

        cols = ("sku", "name", "qty", "unit", "line")
        tree = ttk.Treeview(box, columns=cols, show="headings", height=16)
        heads = {"sku": "SKU", "name": "Name", "qty": "Qty", "unit": "Unit Cost USD", "line": "Line Total USD"}
        widths = {"sku": 140, "name": 420, "qty": 70, "unit": 140, "line": 140}
        for c in cols:
            tree.heading(c, text=heads[c])
            tree.column(c, width=widths[c], anchor="w")
        tree.pack(fill="both", expand=True, padx=10, pady=10)

        total = 0.0
        for it in items:
            total += float(it.line_total_usd)
            tree.insert("", "end", values=(
                it.sku, it.name, int(it.qty), f"{it.unit_cost_usd:.2f}", f"{it.line_total_usd:.2f}"
            ))

        ttk.Label(win, text=f"Total USD: {total:.2f}").pack(anchor="w", padx=14, pady=(0, 10))
