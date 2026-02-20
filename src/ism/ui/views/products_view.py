from __future__ import annotations

import logging
import tkinter as tk
from tkinter import messagebox, ttk


log = logging.getLogger(__name__)


class ProductsView:
    def __init__(self, notebook: ttk.Notebook, app):
        self.app = app
        self.frame = ttk.Frame(notebook)
        notebook.add(self.frame, text="Products")

        style = ttk.Style(self.frame)
        style.configure("ProductsCompact.Treeview", rowheight=24, font=("Segoe UI", 9))
        style.configure("ProductsCompact.Treeview.Heading", font=("Segoe UI", 9, "bold"))

        sub_tabs = ttk.Notebook(self.frame)
        sub_tabs.pack(fill="both", expand=True, padx=6, pady=8)

        add_tab = ttk.Frame(sub_tabs)
        manage_tab = ttk.Frame(sub_tabs)
        sub_tabs.add(add_tab, text="Add")
        sub_tabs.add(manage_tab, text="Edit / Delete")

        self._build_add_tab(add_tab)
        self._build_manage_tab(manage_tab)

    def _build_add_tab(self, tab: ttk.Frame) -> None:
        left = ttk.LabelFrame(tab, text="Add product")
        left.pack(fill="y", padx=8, pady=8, anchor="nw")

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
        ttk.Button(btns, text="Add", command=self.on_add_product).grid(row=0, column=0, sticky="ew", padx=(0, 6))
        ttk.Button(btns, text="Clear", command=self.clear_form).grid(row=0, column=1, sticky="ew", padx=(6, 0))
        
        for entry in (self.p_sku, self.p_name, self.p_cost, self.p_price, self.p_stock, self.p_min):
            entry.bind("<Return>", self._on_enter_add_product)

    def _build_manage_tab(self, tab: ttk.Frame) -> None:
        right = ttk.LabelFrame(tab, text="Products list")
        right.pack(fill="both", expand=True, padx=8, pady=8)

        tree_wrap = ttk.Frame(right)
        tree_wrap.pack(fill="both", expand=True, padx=6, pady=6)

        cols = ("id", "sku", "name", "cost", "price", "stock", "min")
        self.tree = ttk.Treeview(tree_wrap, columns=cols, show="headings", height=18, style="ProductsCompact.Treeview")
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

        edit_box = ttk.LabelFrame(right, text="Edit selected product")
        edit_box.pack(fill="x", padx=6, pady=(0, 6))
        ttk.Label(edit_box, text="Price USD").grid(row=0, column=0, sticky="w", padx=8, pady=(8, 4))
        ttk.Label(edit_box, text="Min stock").grid(row=0, column=1, sticky="w", padx=8, pady=(8, 4))
        self.edit_price = ttk.Entry(edit_box, width=14)
        self.edit_price.grid(row=1, column=0, sticky="ew", padx=8, pady=(0, 8))
        self.edit_min = ttk.Entry(edit_box, width=14)
        self.edit_min.grid(row=1, column=1, sticky="ew", padx=8, pady=(0, 8))
        ttk.Label(edit_box, text="Remove stock qty").grid(row=0, column=2, sticky="w", padx=8, pady=(8, 4))
        self.remove_stock_qty = ttk.Entry(edit_box, width=14)
        self.remove_stock_qty.grid(row=1, column=2, sticky="ew", padx=8, pady=(0, 8))
        ttk.Button(edit_box, text="Save changes", command=self.on_update_product).grid(row=1, column=3, sticky="ew", padx=8, pady=(0, 8))
        ttk.Button(edit_box, text="Remove qty", command=self.on_remove_stock_qty).grid(row=1, column=4, sticky="ew", padx=8, pady=(0, 8))
        ttk.Button(edit_box, text="Clear stock", command=self.on_clear_stock).grid(row=1, column=5, sticky="ew", padx=8, pady=(0, 8))
        ttk.Button(edit_box, text="Delete product", command=self.on_delete_product).grid(row=1, column=6, sticky="ew", padx=8, pady=(0, 8))
        edit_box.columnconfigure(0, weight=1)
        edit_box.columnconfigure(1, weight=1)
        edit_box.columnconfigure(2, weight=1)

        self.tree.bind("<<TreeviewSelect>>", self._load_selected_product_for_edit)

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
    
    def _load_selected_product_for_edit(self, _event=None):
        selected = self.tree.selection()
        if not selected:
            return
        values = self.tree.item(selected[0], "values")
        if len(values) < 7:
            return
        self.edit_price.delete(0, tk.END)
        self.edit_price.insert(0, str(values[4]))
        self.edit_min.delete(0, tk.END)
        self.edit_min.insert(0, str(values[6]))

    def on_add_product(self):
        try:
            sku = self.p_sku.get().strip()
            name = self.p_name.get().strip()
            cost = self._parse_float(self.p_cost.get(), "Cost USD", 0.0)
            price = self._parse_float(self.p_price.get(), "Price USD", 0.0)
            stock = self._parse_int(self.p_stock.get(), "Stock", 0)
            min_stock = self._parse_int(self.p_min.get(), "Min stock", 0)

            if not self.app.can_action("create_product"):
                raise PermissionError("Only admin can create products.")
            pid = self.app.inventory.add_product(sku, name, cost, price, 0, min_stock)

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
            self.app.refresh_all(silent_fx=True)
        except Exception as e:
            self.app.handle_error("Error", e, "Failed to add product.")

    def on_update_product(self):
        try:
            if not self.app.can_action("edit_product"):
                raise PermissionError("Only admin can edit products.")

            selected = self.tree.selection()
            if not selected:
                raise ValueError("Select a product.")

            values = self.tree.item(selected[0], "values")
            product_id = int(values[0])
            price = self._parse_float(self.edit_price.get(), "Price USD")
            min_stock = self._parse_int(self.edit_min.get(), "Min stock")

            self.app.inventory.update_product(product_id, price, min_stock)
            self.app.toast("Product updated.", kind="success")
            self.app.refresh_all(silent_fx=True)
            self.select_product_in_tree(values[1])
        except Exception as e:
            self.app.handle_error("Edit product", e, "Failed to update product.")
     
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
                (
                    f"Delete product '{product_name}' (ID {product_id})?\n\n"
                    "It will be hidden from active products even if it has historical movements."
                ),
                parent=self.frame,
            )
            if not confirmed:
                return

            self.app.inventory.delete_product(product_id)
            self.app.toast("Product deleted.", kind="success")
            self.app.refresh_all(silent_fx=True)
        except Exception as e:
            self.app.handle_error("Delete product", e, "Failed to delete product.")
            
    def on_remove_stock_qty(self):
        try:
            if not self.app.can_action("edit_product"):
                raise PermissionError("Only admin can adjust stock.")

            selected = self.tree.selection()
            if not selected:
                raise ValueError("Select a product.")

            values = self.tree.item(selected[0], "values")
            product_id = int(values[0])
            product_name = str(values[2])
            qty = self._parse_int(self.remove_stock_qty.get(), "Remove stock qty")

            self.app.inventory.remove_product_stock(
                product_id,
                qty,
                actor_user_id=self.app.current_user.id,
                notes=f"Manual stock removal for {product_name}",
            )
            self.app.toast(f"Removed {qty} units from stock.", kind="success")
            self.remove_stock_qty.delete(0, tk.END)
            self.app.refresh_all(silent_fx=True)
            self.select_product_in_tree(values[1])
        except Exception as e:
            self.app.handle_error("Remove stock", e, "Failed to remove stock.")

    def on_clear_stock(self):
        try:
            if not self.app.can_action("edit_product"):
                raise PermissionError("Only admin can adjust stock.")

            selected = self.tree.selection()
            if not selected:
                raise ValueError("Select a product.")

            values = self.tree.item(selected[0], "values")
            product_id = int(values[0])
            product_name = str(values[2])
            current_stock = int(values[5])
            if current_stock <= 0:
                self.app.toast("This product already has zero stock.", kind="info")
                return

            confirmed = messagebox.askyesno(
                "Confirm clear stock",
                f"Set stock of '{product_name}' to zero? (remove {current_stock} units)",
                parent=self.frame,
            )
            if not confirmed:
                return

            self.app.inventory.clear_product_stock(
                product_id,
                actor_user_id=self.app.current_user.id,
                notes=f"Manual stock clear for {product_name}",
            )
            self.app.toast("Stock cleared to zero.", kind="success")
            self.app.refresh_all(silent_fx=True)
            self.select_product_in_tree(values[1])
        except Exception as e:
            self.app.handle_error("Clear stock", e, "Failed to clear stock.")

    def clear_form(self):
        for e in (self.p_sku, self.p_name, self.p_cost, self.p_price, self.p_stock, self.p_min):
            e.delete(0, tk.END)
        self.p_sku.focus_set()

    def refresh(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

        rows = self.app.inventory.list_products()
        for p in rows:
            tag = "low" if int(p.stock) <= int(p.min_stock) else ""
            self.tree.insert(
                "", "end",
                values=(p.id, p.sku, p.name, f"{p.cost_usd:.2f}", f"{p.price_usd:.2f}", p.stock, p.min_stock),
                tags=(tag,) if tag else (),
            )

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
