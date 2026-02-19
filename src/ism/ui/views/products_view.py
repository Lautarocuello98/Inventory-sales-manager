from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox
import logging


log = logging.getLogger(__name__)


class ProductsView:
    def __init__(self, notebook: ttk.Notebook, app):
        self.app = app
        self.frame = ttk.Frame(notebook)
        notebook.add(self.frame, text="Products")

        tab = self.frame
        style = ttk.Style(self.frame)
        style.configure("ProductsCompact.Treeview", rowheight=24, font=("Segoe UI", 9))
        style.configure("ProductsCompact.Treeview.Heading", font=("Segoe UI", 9, "bold"))

        left = ttk.LabelFrame(tab, text="Add product", width=255)
        left.pack(side="left", fill="y", padx=(0, 6), pady=8)
        left.pack_propagate(False)

        right = ttk.LabelFrame(tab, text="Products list")
        right.pack(side="right", fill="both", expand=True, pady=8)

        self.p_sku = self._entry(left, "SKU", 0)
        self.p_name = self._entry(left, "Name", 1)
        self.p_cost = self._entry(left, "Cost USD", 2)
        self.p_price = self._entry(left, "Price USD", 3)
        self.p_stock = self._entry(left, "Stock", 4)
        self.p_min = self._entry(left, "Min stock", 5)

        btns = ttk.Frame(left)
        btns.grid(row=6, column=0, columnspan=2, sticky="ew", padx=8, pady=(6, 8))
        btns.columnconfigure(0, weight=1)
        btns.columnconfigure(1, weight=1)
        btns.columnconfigure(2, weight=1)

        ttk.Button(btns, text="Add", command=self.on_add_product)            .grid(row=0, column=0, sticky="ew", padx=(0, 6))
        ttk.Button(btns, text="Delete", command=self.on_delete_product)            .grid(row=0, column=1, sticky="ew", padx=6)
        ttk.Button(btns, text="Clear", command=self.clear_form)            .grid(row=0, column=2, sticky="ew", padx=(6, 0))
        
        for entry in (self.p_sku, self.p_name, self.p_cost, self.p_price, self.p_stock, self.p_min):
            entry.bind("<Return>", self._on_enter_add_product)
        tree_wrap = ttk.Frame(right)
        tree_wrap.pack(fill="both", expand=True, padx=6, pady=6)

        cols = ("id", "sku", "name", "cost", "price", "stock", "min")
        self.tree = ttk.Treeview(tree_wrap, columns=cols, show="headings", height=20, style="ProductsCompact.Treeview")
        heads = {
            "id": "ID", "sku": "SKU", "name": "Name",
            "cost": "Cost USD", "price": "Price USD",
            "stock": "Stock", "min": "Min"
        }
        widths = {"id": 48, "sku": 105, "name": 280, "cost": 92, "price": 92, "stock": 78, "min": 86}
        for c in cols:
            self.tree.heading(c, text=heads[c])
            self.tree.column(c, width=widths[c], anchor="w")

        self.tree.tag_configure("low", background="#ffdddd")

        vsb = ttk.Scrollbar(tree_wrap, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(tree_wrap, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")

        tree_wrap.columnconfigure(0, weight=1)
        tree_wrap.rowconfigure(0, weight=1)

        # IMPORTANT:
        # Do NOT call refresh() here.
        # App will call refresh_all() after all views are created.

    def _entry(self, parent, label, row):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=8, pady=4)
        e = ttk.Entry(parent, width=16)
        e.grid(row=row, column=1, sticky="ew", padx=8, pady=4)
        parent.columnconfigure(1, weight=1)
        return e

    def _parse_int(self, s: str, field: str, default: int = 0) -> int:
        s = (s or "").strip()
        if s == "":
            return default
        try:
            return int(float(s))
        except Exception:
            raise ValueError(f"{field} must be an integer.")

    def _parse_float(self, s: str, field: str, default: float = 0.0) -> float:
        s = (s or "").strip()
        if s == "":
            return default
        try:
            return float(s)
        except Exception:
            raise ValueError(f"{field} must be a number.")

    def _on_enter_add_product(self, _event=None):
        self.on_add_product()
        return "break"

    def on_add_product(self):
        try:
            sku = self.p_sku.get().strip()
            name = self.p_name.get().strip()
            cost = self._parse_float(self.p_cost.get(), "Cost USD", 0.0)
            price = self._parse_float(self.p_price.get(), "Price USD", 0.0)
            stock = self._parse_int(self.p_stock.get(), "Stock", 0)
            min_stock = self._parse_int(self.p_min.get(), "Min stock", 0)

            # Create with stock=0 first. If initial stock is provided,
            # it is applied as a purchase so inventory history remains consistent.
            if not self.app.can_action("create_product"):
                raise PermissionError("Only admin can create products.")
            pid = self.app.inventory.add_product(sku, name, cost, price, 0, min_stock)

            # If user set initial stock, log as an INITIAL purchase (so it appears in history)
            if stock > 0:
                prod = self.app.inventory.get_product_by_sku(sku)
                self.app.purchases.create_purchase(
                    vendor="INITIAL",
                    notes=f"Initial stock on product creation ({sku})",
                    items=[{"product_id": prod.id, "qty": stock, "unit_cost_usd": cost}],
                    actor_user_id=self.app.current_user.id,
                )

            self.app.toast(f"Product added (ID {pid}).", kind="success")
            self.clear_form()

            # Now do a coordinated refresh (safe: all views already exist at runtime)
            self.app.refresh_all(silent_fx=True)

        except Exception as e:
            self.app.handle_error("Error", e, "Failed to add product.")
            
    def on_delete_product(self):
        try:
            if not self.app.can_action("delete_product"):
                raise PermissionError("Only admin can delete products.")

            selected = self.tree.selection()
            if not selected:
                raise ValueError("Select a product.")

            values = self.tree.item(selected[0], "values")
            product_id = int(values[0])
            product_name = str(values[2])

            confirmed = messagebox.askyesno(
                "Confirm delete",
                f"Delete product '{product_name}' (ID {product_id})?\n\nOnly products with stock 0 can be deleted.",
                parent=self.frame,
            )
            if not confirmed:
                return

            self.app.inventory.delete_product(product_id)
            self.app.toast("Product deleted.", kind="success")
            self.app.refresh_all(silent_fx=True)
        except Exception as e:
            self.app.handle_error("Delete product", e, "Failed to delete product.")

    def clear_form(self):
        for e in (self.p_sku, self.p_name, self.p_cost, self.p_price, self.p_stock, self.p_min):
            e.delete(0, tk.END)
        self.p_sku.focus_set()

    def refresh(self):
        # Refresh tree itself
        for item in self.tree.get_children():
            self.tree.delete(item)

        rows = self.app.inventory.list_products()
        for p in rows:
            tag = "low" if int(p.stock) <= int(p.min_stock) else ""
            self.tree.insert(
                "", "end",
                values=(p.id, p.sku, p.name, f"{p.cost_usd:.2f}", f"{p.price_usd:.2f}", p.stock, p.min_stock),
                tags=(tag,) if tag else ()
            )

        # Update dropdown choices used in other views (only if they exist)
        if hasattr(self.app, "sales_view"):
            self.app.sales_view.refresh_product_choices()
        if hasattr(self.app, "restock_view"):
            self.app.restock_view.refresh_product_choices()

    def select_product_in_tree(self, sku: str):
        for iid in self.tree.get_children():
            vals = self.tree.item(iid, "values")
            if len(vals) >= 2 and str(vals[1]) == str(sku):
                self.tree.selection_set(iid)
                self.tree.focus(iid)
                self.tree.see(iid)
                return
