import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime, date, timedelta

from db import (
    init_db, add_product, list_products, get_product_by_sku,
    create_sale, list_sales_between, get_sale_header, sale_items_for_sale,
    create_purchase, sales_summary_between,
    list_purchases_between, purchase_items_for_purchase,
)

from api_fx import get_today_rate
from excel_io import import_products_from_excel, export_sales_report_excel


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Inventory & Sales Manager (USD + ARS)")
        self.geometry("1280x720")
        self.minsize(1120, 640)

        init_db()

        self.cart = []
        self.restock_cart = []
        self._last_low_count = None
        self._toast_after_id = None
        self._low_items = []

        # ---------- Styles ----------
        style = ttk.Style(self)
        try:
            style.configure("Big.TButton", padding=(14, 10))
            style.configure("Title.TLabel", font=("Segoe UI", 12, "bold"))
            style.configure("KPI.TLabel", font=("Segoe UI", 10))
            style.configure("KPIValue.TLabel", font=("Segoe UI", 11, "bold"))
        except Exception:
            pass

        # HIDE notebook tabs -> navigation ONLY via sidebar
        style.layout("Side.TNotebook.Tab", [])  # no tab UI
        style.configure("Side.TNotebook", tabmargins=0)

        # ---------- Topbar ----------
        self.fx_var = tk.StringVar(value="FX (USD→ARS): not loaded")
        self._build_topbar()

        # ---------- Layout ----------
        main = ttk.Frame(self)
        main.pack(fill="both", expand=True, padx=12, pady=(0, 8))

        self.sidebar = ttk.Frame(main)
        self.sidebar.pack(side="left", fill="y", padx=(0, 10))

        self.content = ttk.Frame(main)
        self.content.pack(side="right", fill="both", expand=True)

        self.nb = ttk.Notebook(self.content, style="Side.TNotebook")
        self.nb.pack(fill="both", expand=True)

        # Build pages (NO visible tabs)
        self._build_tab_products()
        self._build_tab_sales()
        self._build_tab_sales_history()
        self._build_tab_restock()
        self._build_tab_excel_reports()

        # Sidebar uses these tabs, so build it AFTER pages exist
        self._build_sidebar()

        # Status bar / toast
        self._build_status_bar()

        # Initial refresh
        self.update_fx(silent=True)
        self.refresh_products()
        self.refresh_sales_history()
        self.refresh_kpis()
        self.toast("Ready.", kind="info", ms=1200)

    # ---------------- Topbar ----------------
    def _build_topbar(self):
        top = ttk.Frame(self)
        top.pack(fill="x", padx=12, pady=10)

        ttk.Label(top, textvariable=self.fx_var).pack(side="left")
        ttk.Button(top, text="Update FX", command=self.update_fx).pack(side="left", padx=10)

        # Remove duplicate navigation/controls from top (keep it clean)
        ttk.Label(top, text="").pack(side="right")  # spacer

    def update_fx(self, silent: bool = False):
        try:
            rate = get_today_rate()
            self.fx_var.set(f"FX (USD→ARS): {rate:.4f}")
            if not silent:
                self.toast(f"FX updated: {rate:.4f}", kind="success")
        except Exception as e:
            if not silent:
                messagebox.showerror("FX Error", str(e))
                self.toast("FX update failed.", kind="error")

    # ---------------- Sidebar ----------------
    def _build_sidebar(self):
        box = ttk.LabelFrame(self.sidebar, text="Quick Actions")
        box.pack(fill="x", pady=(0, 10))

        ttk.Button(box, text="📦 Products", style="Big.TButton",
                   command=lambda: self.nb.select(self.tab_products)).pack(fill="x", padx=10, pady=(10, 6))
        ttk.Button(box, text="🧾 New Sale", style="Big.TButton",
                   command=lambda: self.nb.select(self.tab_sales)).pack(fill="x", padx=10, pady=6)
        ttk.Button(box, text="📜 Sales History", style="Big.TButton",
                   command=lambda: self.nb.select(self.tab_sales_history)).pack(fill="x", padx=10, pady=6)
        ttk.Button(box, text="🔁 Restock", style="Big.TButton",
                   command=lambda: self.nb.select(self.tab_restock)).pack(fill="x", padx=10, pady=6)
        ttk.Button(box, text="📊 Excel + Reports", style="Big.TButton",
                   command=lambda: self.nb.select(self.tab_excel)).pack(fill="x", padx=10, pady=6)

        ttk.Button(box, text="🔄 Refresh", style="Big.TButton",
                   command=self.on_refresh_all).pack(fill="x", padx=10, pady=(6, 10))

        kpi = ttk.LabelFrame(self.sidebar, text="KPIs")
        kpi.pack(fill="x")

        ttk.Label(kpi, text="Products", style="KPI.TLabel").grid(row=0, column=0, sticky="w", padx=10, pady=(10, 2))
        self.k_products = ttk.Label(kpi, text="-", style="KPIValue.TLabel")
        self.k_products.grid(row=0, column=1, sticky="e", padx=10, pady=(10, 2))

        ttk.Label(kpi, text="Total stock units", style="KPI.TLabel").grid(row=1, column=0, sticky="w", padx=10, pady=2)
        self.k_units = ttk.Label(kpi, text="-", style="KPIValue.TLabel")
        self.k_units.grid(row=1, column=1, sticky="e", padx=10, pady=2)

        ttk.Label(kpi, text="Low stock items", style="KPI.TLabel").grid(row=2, column=0, sticky="w", padx=10, pady=2)
        self.k_low = ttk.Label(kpi, text="-", style="KPIValue.TLabel")
        self.k_low.grid(row=2, column=1, sticky="e", padx=10, pady=2)

        ttk.Label(kpi, text="Revenue (7d) USD", style="KPI.TLabel").grid(row=3, column=0, sticky="w", padx=10, pady=2)
        self.k_rev7 = ttk.Label(kpi, text="-", style="KPIValue.TLabel")
        self.k_rev7.grid(row=3, column=1, sticky="e", padx=10, pady=2)

        ttk.Label(kpi, text="Profit (7d) USD", style="KPI.TLabel").grid(row=4, column=0, sticky="w", padx=10, pady=2)
        self.k_profit7 = ttk.Label(kpi, text="-", style="KPIValue.TLabel")
        self.k_profit7.grid(row=4, column=1, sticky="e", padx=10, pady=2)

        kpi.columnconfigure(0, weight=1)
        kpi.columnconfigure(1, weight=1)

        lowbox = ttk.LabelFrame(self.sidebar, text="Low Stock (double click)")
        lowbox.pack(fill="both", expand=True, pady=(10, 0))

        self.low_list = tk.Listbox(lowbox, height=10)
        self.low_list.pack(fill="both", expand=True, padx=10, pady=10)
        self.low_list.bind("<Double-1>", self.on_low_stock_open)

        ttk.Label(self.sidebar, text="Tip: type product name in Sales/Restock search.",
                  wraplength=220).pack(fill="x", pady=10)

    def on_refresh_all(self):
        self.update_fx(silent=True)
        self.refresh_products()
        self.refresh_sales_history()
        self.refresh_kpis()
        self.toast("Refreshed.", kind="info", ms=1200)

    # ---------------- Status bar / toast ----------------
    def _build_status_bar(self):
        bar = ttk.Frame(self)
        bar.pack(fill="x", padx=12, pady=(0, 10))
        self.status_var = tk.StringVar(value="")
        ttk.Label(bar, textvariable=self.status_var).pack(side="left")

    def toast(self, msg: str, kind: str = "info", ms: int = 2500):
        prefix = {"info": "ℹ ", "success": "✅ ", "warn": "⚠ ", "error": "❌ "}.get(kind, "")
        self.status_var.set(prefix + msg)

        if self._toast_after_id is not None:
            try:
                self.after_cancel(self._toast_after_id)
            except Exception:
                pass

        self._toast_after_id = self.after(ms, lambda: self.status_var.set(""))

    # ---------------- Shared helpers: product search combo ----------------
    def _product_choices(self):
        rows = list_products()
        choices = []
        mapping = {}
        for _id, sku, name, _cost, _price, stock, _min in rows:
            label = f"{sku} — {name} (stock: {stock})"
            choices.append(label)
            mapping[label] = sku
        return choices, mapping

    def _filter_combobox(self, combo: ttk.Combobox, all_choices: list[str], typed: str):
        typed = typed.strip().lower()
        if not typed:
            combo["values"] = all_choices
            return
        combo["values"] = [c for c in all_choices if typed in c.lower()]

    # ---------------- Low stock panel ----------------
    def refresh_low_stock_panel(self, rows):
        if not hasattr(self, "low_list"):
            return
        self.low_list.delete(0, tk.END)
        self._low_items = []
        low = [r for r in rows if int(r[5]) <= int(r[6])]
        for r in low:
            _id, sku, name, _cost, _price, stock, min_stock = r
            self.low_list.insert(tk.END, f"{sku} — {name} ({stock}/{min_stock})")
            self._low_items.append((sku, name))

    def on_low_stock_open(self, _evt=None):
        if not self._low_items:
            return
        sel = self.low_list.curselection()
        if not sel:
            return
        sku, _name = self._low_items[sel[0]]
        self.nb.select(self.tab_products)
        self.select_product_in_tree(sku)
        self.toast(f"Selected low stock: {sku}", kind="warn", ms=2000)

    def select_product_in_tree(self, sku: str):
        for iid in self.prod_tree.get_children():
            vals = self.prod_tree.item(iid, "values")
            if len(vals) >= 2 and str(vals[1]) == str(sku):
                self.prod_tree.selection_set(iid)
                self.prod_tree.focus(iid)
                self.prod_tree.see(iid)
                return

    # ---------------- KPIs ----------------
    def refresh_kpis(self):
        try:
            rows = list_products()
            products_count = len(rows)
            units = sum(int(r[5]) for r in rows)
            low_count = sum(1 for r in rows if int(r[5]) <= int(r[6]))

            end = datetime.now().replace(microsecond=0)
            start = end - timedelta(days=7)
            totals, _ = sales_summary_between(start.isoformat(sep=" "), end.isoformat(sep=" "))
            _cnt, rev_usd, _rev_ars, profit_usd = totals

            self.k_products.config(text=str(products_count))
            self.k_units.config(text=str(units))
            self.k_low.config(text=str(low_count))
            self.k_rev7.config(text=f"{float(rev_usd):.2f}")
            self.k_profit7.config(text=f"{float(profit_usd):.2f}")
        except Exception:
            pass

    # ---------------- Products tab ----------------
    def _build_tab_products(self):
        self.tab_products = ttk.Frame(self.nb)
        self.nb.add(self.tab_products, text="Products")

        tab = self.tab_products

        left = ttk.LabelFrame(tab, text="Add product")
        left.pack(side="left", fill="y", padx=(0, 12), pady=10)

        right = ttk.LabelFrame(tab, text="Products list")
        right.pack(side="right", fill="both", expand=True, pady=10)

        self.p_sku = self._entry(left, "SKU", 0)
        self.p_name = self._entry(left, "Name", 1)
        self.p_cost = self._entry(left, "Cost USD", 2)
        self.p_price = self._entry(left, "Price USD", 3)
        self.p_stock = self._entry(left, "Stock", 4)
        self.p_min = self._entry(left, "Min stock", 5)

        btns = ttk.Frame(left)
        btns.grid(row=6, column=0, columnspan=2, sticky="ew", padx=10, pady=(10, 10))
        btns.columnconfigure(0, weight=1)
        btns.columnconfigure(1, weight=1)

        ttk.Button(btns, text="Add", style="Big.TButton", command=self.on_add_product)\
            .grid(row=0, column=0, sticky="ew", padx=(0, 6))
        ttk.Button(btns, text="Clear", style="Big.TButton", command=self.clear_product_form)\
            .grid(row=0, column=1, sticky="ew", padx=(6, 0))

        cols = ("id", "sku", "name", "cost", "price", "stock", "min")
        self.prod_tree = ttk.Treeview(right, columns=cols, show="headings", height=20)
        heads = {"id": "ID", "sku": "SKU", "name": "Name", "cost": "Cost USD", "price": "Price USD",
                 "stock": "Stock", "min": "Min"}
        widths = {"id": 60, "sku": 130, "name": 360, "cost": 110, "price": 110, "stock": 90, "min": 90}
        for c in cols:
            self.prod_tree.heading(c, text=heads[c])
            self.prod_tree.column(c, width=widths[c], anchor="w")

        self.prod_tree.tag_configure("low", background="#ffdddd")

        vsb = ttk.Scrollbar(right, orient="vertical", command=self.prod_tree.yview)
        self.prod_tree.configure(yscrollcommand=vsb.set)
        self.prod_tree.pack(side="left", fill="both", expand=True, padx=(10, 0), pady=10)
        vsb.pack(side="right", fill="y", padx=(0, 10), pady=10)

    def on_add_product(self):
        sku = self.p_sku.get().strip()
        name = self.p_name.get().strip()
        if not sku or not name:
            messagebox.showwarning("Validation", "SKU and Name are required.")
            self.toast("Missing SKU/Name.", kind="warn")
            return

        cost = self._parse_float(self.p_cost.get().strip(), "Cost USD", 0.0)
        price = self._parse_float(self.p_price.get().strip(), "Price USD", 0.0)
        stock = self._parse_int(self.p_stock.get().strip(), "Stock", 0)
        min_stock = self._parse_int(self.p_min.get().strip(), "Min stock", 0)
        if None in (cost, price, stock, min_stock):
            return

        try:
            add_product(sku, name, cost, price, stock, min_stock)
            self.toast("Product added.", kind="success")
            self.refresh_products()
            self.refresh_kpis()
            self.clear_product_form()
        except Exception as e:
            messagebox.showerror("DB Error", str(e))
            self.toast("Failed to add product.", kind="error")

    def clear_product_form(self):
        for e in (self.p_sku, self.p_name, self.p_cost, self.p_price, self.p_stock, self.p_min):
            e.delete(0, tk.END)
        self.p_sku.focus_set()

    def refresh_products(self):
        try:
            rows = list_products()
        except Exception as e:
            messagebox.showerror("DB Error", str(e))
            self.toast("DB error refreshing products.", kind="error")
            return

        for item in self.prod_tree.get_children():
            self.prod_tree.delete(item)

        for r in rows:
            tag = "low" if int(r[5]) <= int(r[6]) else ""
            self.prod_tree.insert(
                "", "end",
                values=(r[0], r[1], r[2], f"{r[3]:.2f}", f"{r[4]:.2f}", r[5], r[6]),
                tags=(tag,) if tag else ()
            )

        # Refresh search combos
        choices, mapping = self._product_choices()
        if hasattr(self, "sale_sku_combo"):
            self.sale_all_choices = choices
            self.sale_sku_map = mapping
            self.sale_sku_combo["values"] = choices
        if hasattr(self, "restock_sku_combo"):
            self.restock_all_choices = choices
            self.restock_sku_map = mapping
            self.restock_sku_combo["values"] = choices

        # Sidebar low stock list
        self.refresh_low_stock_panel(rows)

        # Low stock popup (avoid spam)
        low = [r for r in rows if int(r[5]) <= int(r[6])]
        if self._last_low_count is None:
            self._last_low_count = len(low)

        if low and len(low) != self._last_low_count:
            msg = "LOW STOCK:\n\n" + "\n".join([f"- {r[2]} ({r[1]}): {r[5]} <= min {r[6]}" for r in low[:12]])
            if len(low) > 12:
                msg += f"\n...and {len(low)-12} more"
            messagebox.showwarning("Low stock alert", msg)
            self.toast(f"Low stock items: {len(low)}", kind="warn")
            self._last_low_count = len(low)
        elif not low:
            self._last_low_count = 0

    # ---------------- Sales tab ----------------
    def _build_tab_sales(self):
        self.tab_sales = ttk.Frame(self.nb)
        self.nb.add(self.tab_sales, text="Sales")

        tab = self.tab_sales

        top = ttk.LabelFrame(tab, text="Add item to cart")
        top.pack(fill="x", padx=10, pady=10)

        ttk.Label(top, text="Search product (SKU or name)").grid(row=0, column=0, padx=10, pady=8, sticky="w")

        self.sale_pick = tk.StringVar()
        self.sale_sku_map = {}
        self.sale_all_choices = []

        self.sale_sku_combo = ttk.Combobox(top, textvariable=self.sale_pick, width=56)
        self.sale_sku_combo.grid(row=0, column=1, padx=10, pady=8, sticky="w")
        self.sale_sku_combo.bind("<KeyRelease>", lambda e: self._filter_combobox(
            self.sale_sku_combo, self.sale_all_choices, self.sale_pick.get()
        ))

        ttk.Label(top, text="Qty").grid(row=0, column=2, padx=10, pady=8, sticky="w")
        self.sale_qty_e = ttk.Entry(top, width=10)
        self.sale_qty_e.grid(row=0, column=3, padx=10, pady=8, sticky="w")

        ttk.Button(top, text="Add to cart", style="Big.TButton", command=self.add_to_cart)\
            .grid(row=0, column=4, padx=10, pady=8)

        mid = ttk.Frame(tab)
        mid.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        cart_box = ttk.LabelFrame(mid, text="Cart")
        cart_box.pack(side="left", fill="both", expand=True, padx=(0, 10))

        cols = ("sku", "name", "qty", "unit", "line")
        self.cart_tree = ttk.Treeview(cart_box, columns=cols, show="headings", height=16)
        heads = {"sku": "SKU", "name": "Name", "qty": "Qty", "unit": "Unit USD", "line": "Line USD"}
        widths = {"sku": 120, "name": 420, "qty": 70, "unit": 110, "line": 110}
        for c in cols:
            self.cart_tree.heading(c, text=heads[c])
            self.cart_tree.column(c, width=widths[c], anchor="w")
        self.cart_tree.pack(fill="both", expand=True, padx=10, pady=10)

        btnrow = ttk.Frame(cart_box)
        btnrow.pack(fill="x", padx=10, pady=(0, 10))
        ttk.Button(btnrow, text="Remove selected", command=self.remove_selected_cart).pack(side="left")
        ttk.Button(btnrow, text="Clear cart", command=self.clear_cart).pack(side="left", padx=10)

        right = ttk.LabelFrame(mid, text="Confirm sale")
        right.pack(side="right", fill="y")

        ttk.Label(right, text="Notes (optional)").pack(anchor="w", padx=10, pady=(10, 4))
        self.sale_notes = tk.Text(right, width=34, height=6)
        self.sale_notes.pack(padx=10)

        self.sale_total_var = tk.StringVar(value="Total USD: 0.00 | Total ARS: 0.00")
        ttk.Label(right, textvariable=self.sale_total_var).pack(anchor="w", padx=10, pady=10)

        ttk.Button(right, text="Confirm sale", style="Big.TButton", command=self.confirm_sale)\
            .pack(fill="x", padx=10, pady=(0, 10))

    def add_to_cart(self):
        picked = self.sale_pick.get().strip()
        if not picked:
            messagebox.showwarning("Validation", "Select a product.")
            self.toast("No product selected.", kind="warn")
            return

        sku = self.sale_sku_map.get(picked)
        if not sku:
            messagebox.showwarning("Validation", "Pick a product from the dropdown list.")
            self.toast("Pick from dropdown list.", kind="warn")
            return

        qty = self._parse_int(self.sale_qty_e.get().strip(), "Qty", 1)
        if qty is None:
            return

        prod = get_product_by_sku(sku)
        if not prod:
            messagebox.showerror("Not found", "Product not found.")
            self.toast("Product not found.", kind="error")
            return

        prod_id, _, name, _cost, price_usd, stock, _min = prod
        if qty > stock:
            messagebox.showwarning("Stock", f"Not enough stock. Available: {stock}")
            self.toast("Not enough stock.", kind="warn")
            return

        for it in self.cart:
            if it["product_id"] == prod_id:
                new_qty = it["qty"] + qty
                if new_qty > stock:
                    messagebox.showwarning("Stock", f"Not enough stock. Available: {stock}")
                    self.toast("Not enough stock.", kind="warn")
                    return
                it["qty"] = new_qty
                self.refresh_cart_view()
                self.sale_qty_e.delete(0, tk.END)
                self.toast("Updated qty in cart.", kind="success", ms=1500)
                return

        self.cart.append({
            "product_id": prod_id,
            "sku": sku,
            "name": name,
            "qty": qty,
            "unit_price_usd": float(price_usd),
        })
        self.refresh_cart_view()
        self.sale_qty_e.delete(0, tk.END)
        self.toast("Added to cart.", kind="success", ms=1500)

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
            fx = get_today_rate()
            self.fx_var.set(f"FX (USD→ARS): {fx:.4f}")
            self.sale_total_var.set(f"Total USD: {total_usd:.2f} | Total ARS: {(total_usd * fx):.2f}")
        except Exception:
            self.sale_total_var.set(f"Total USD: {total_usd:.2f} | Total ARS: (update FX)")

    def remove_selected_cart(self):
        sel = self.cart_tree.selection()
        if not sel:
            return
        sku = self.cart_tree.item(sel[0], "values")[0]
        self.cart = [it for it in self.cart if it["sku"] != sku]
        self.refresh_cart_view()
        self.toast("Removed from cart.", kind="info", ms=1500)

    def clear_cart(self):
        self.cart = []
        self.refresh_cart_view()
        self.toast("Cart cleared.", kind="info", ms=1500)

    def confirm_sale(self):
        if not self.cart:
            messagebox.showwarning("Empty", "Cart is empty.")
            self.toast("Cart is empty.", kind="warn")
            return

        try:
            fx = get_today_rate()
            self.fx_var.set(f"FX (USD→ARS): {fx:.4f}")
        except Exception as e:
            messagebox.showerror("FX Error", f"Cannot confirm sale without FX.\n\n{e}")
            self.toast("Cannot confirm sale (FX).", kind="error")
            return

        notes = self.sale_notes.get("1.0", "end").strip() or None
        dt_iso = datetime.now().replace(microsecond=0).isoformat(sep=" ")

        try:
            sale_id = create_sale(dt_iso, fx, notes, self.cart)
        except Exception as e:
            messagebox.showerror("Sale failed", str(e))
            self.toast("Sale failed.", kind="error")
            return

        messagebox.showinfo("OK", f"Sale saved. ID: {sale_id}")
        self.toast(f"Sale saved (ID {sale_id}).", kind="success")
        self.sale_notes.delete("1.0", "end")
        self.clear_cart()
        self.refresh_products()
        self.refresh_sales_history()
        self.refresh_kpis()

    # ---------------- Sales History tab ----------------
    def _build_tab_sales_history(self):
        self.tab_sales_history = ttk.Frame(self.nb)
        self.nb.add(self.tab_sales_history, text="Sales History")

        tab = self.tab_sales_history

        top = ttk.Frame(tab)
        top.pack(fill="x", padx=10, pady=10)

        ttk.Label(top, text="Window").pack(side="left")
        self.hist_window = tk.StringVar(value="7")
        ttk.Combobox(top, textvariable=self.hist_window, values=["7", "30", "90"], width=6, state="readonly")\
            .pack(side="left", padx=10)
        ttk.Label(top, text="days").pack(side="left")

        ttk.Button(top, text="Refresh", command=self.refresh_sales_history).pack(side="left", padx=10)

        box = ttk.LabelFrame(tab, text="Double click a sale to view details")
        box.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        cols = ("id", "dt", "usd", "fx", "ars", "notes")
        self.sales_tree = ttk.Treeview(box, columns=cols, show="headings", height=18)
        heads = {"id": "Sale ID", "dt": "Datetime", "usd": "Total USD", "fx": "FX", "ars": "Total ARS", "notes": "Notes"}
        widths = {"id": 90, "dt": 200, "usd": 110, "fx": 90, "ars": 120, "notes": 520}
        for c in cols:
            self.sales_tree.heading(c, text=heads[c])
            self.sales_tree.column(c, width=widths[c], anchor="w")
        self.sales_tree.pack(fill="both", expand=True, padx=10, pady=10)

        self.sales_tree.bind("<Double-1>", self.open_sale_details)

    def refresh_sales_history(self):
        try:
            days = int(self.hist_window.get())
        except ValueError:
            days = 7

        end = datetime.now().replace(microsecond=0)
        start = end - timedelta(days=days)

        try:
            rows = list_sales_between(start.isoformat(sep=" "), end.isoformat(sep=" "))
        except Exception:
            return

        for item in self.sales_tree.get_children():
            self.sales_tree.delete(item)

        for s in rows:
            self.sales_tree.insert("", "end", values=(
                s[0], s[1], f"{float(s[2]):.2f}", f"{float(s[3]):.4f}", f"{float(s[4]):.2f}", (s[5] or "")[:140]
            ))

    def open_sale_details(self, _evt=None):
        sel = self.sales_tree.selection()
        if not sel:
            return
        sale_id = int(self.sales_tree.item(sel[0], "values")[0])

        header = get_sale_header(sale_id)
        items = sale_items_for_sale(sale_id)

        win = tk.Toplevel(self)
        win.title(f"Sale Details #{sale_id}")
        win.geometry("980x520")

        h = ttk.LabelFrame(win, text="Header")
        h.pack(fill="x", padx=10, pady=10)

        dt, usd, fx, ars, notes = header[1], header[2], header[3], header[4], header[5] or ""
        ttk.Label(h, text=f"Datetime: {dt}").pack(anchor="w", padx=10, pady=2)
        ttk.Label(h, text=f"Total USD: {usd:.2f} | FX: {fx:.4f} | Total ARS: {ars:.2f}").pack(anchor="w", padx=10, pady=2)
        ttk.Label(h, text=f"Notes: {notes}").pack(anchor="w", padx=10, pady=2)

        box = ttk.LabelFrame(win, text="Items")
        box.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        cols = ("sku", "name", "qty", "unit", "line", "cost", "margin")
        tree = ttk.Treeview(box, columns=cols, show="headings", height=16)
        heads = {"sku": "SKU", "name": "Name", "qty": "Qty", "unit": "Unit USD", "line": "Line USD",
                 "cost": "Cost USD", "margin": "Line Profit USD"}
        widths = {"sku": 120, "name": 380, "qty": 70, "unit": 110, "line": 110, "cost": 110, "margin": 140}
        for c in cols:
            tree.heading(c, text=heads[c])
            tree.column(c, width=widths[c], anchor="w")
        tree.pack(fill="both", expand=True, padx=10, pady=10)

        total_margin = 0.0
        for sku, name, qty, unit, line, cost, margin in items:
            total_margin += float(margin)
            tree.insert("", "end", values=(sku, name, qty, f"{unit:.2f}", f"{line:.2f}", f"{cost:.2f}", f"{margin:.2f}"))

        ttk.Label(win, text=f"Profit USD (this sale): {total_margin:.2f}").pack(anchor="w", padx=14, pady=(0, 10))

    # ---------------- Restock tab ----------------
    def _build_tab_restock(self):
        self.tab_restock = ttk.Frame(self.nb)
        self.nb.add(self.tab_restock, text="Restock")

        tab = self.tab_restock

        top = ttk.LabelFrame(tab, text="Add restock item")
        top.pack(fill="x", padx=10, pady=10)

        ttk.Label(top, text="Search product (SKU or name)").grid(row=0, column=0, padx=10, pady=8, sticky="w")

        self.restock_pick = tk.StringVar()
        self.restock_sku_map = {}
        self.restock_all_choices = []

        self.restock_sku_combo = ttk.Combobox(top, textvariable=self.restock_pick, width=56)
        self.restock_sku_combo.grid(row=0, column=1, padx=10, pady=8, sticky="w")
        self.restock_sku_combo.bind("<KeyRelease>", lambda e: self._filter_combobox(
            self.restock_sku_combo, self.restock_all_choices, self.restock_pick.get()
        ))

        ttk.Label(top, text="Qty").grid(row=0, column=2, padx=10, pady=8, sticky="w")
        self.restock_qty_e = ttk.Entry(top, width=10)
        self.restock_qty_e.grid(row=0, column=3, padx=10, pady=8, sticky="w")

        ttk.Label(top, text="Unit cost USD").grid(row=0, column=4, padx=10, pady=8, sticky="w")
        self.restock_cost_e = ttk.Entry(top, width=12)
        self.restock_cost_e.grid(row=0, column=5, padx=10, pady=8, sticky="w")

        ttk.Button(top, text="Add", style="Big.TButton", command=self.add_restock_item)\
            .grid(row=0, column=6, padx=10, pady=8)

        mid = ttk.Frame(tab)
        mid.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        box = ttk.LabelFrame(mid, text="Restock cart")
        box.pack(side="left", fill="both", expand=True, padx=(0, 10))

        cols = ("sku", "name", "qty", "unit", "line")
        self.restock_tree = ttk.Treeview(box, columns=cols, show="headings", height=16)
        heads = {"sku": "SKU", "name": "Name", "qty": "Qty", "unit": "Unit cost USD", "line": "Line USD"}
        widths = {"sku": 120, "name": 420, "qty": 70, "unit": 130, "line": 110}
        for c in cols:
            self.restock_tree.heading(c, text=heads[c])
            self.restock_tree.column(c, width=widths[c], anchor="w")
        self.restock_tree.pack(fill="both", expand=True, padx=10, pady=10)

        btnrow = ttk.Frame(box)
        btnrow.pack(fill="x", padx=10, pady=(0, 10))
        ttk.Button(btnrow, text="Remove selected", command=self.remove_selected_restock).pack(side="left")
        ttk.Button(btnrow, text="Clear", command=self.clear_restock).pack(side="left", padx=10)

        right = ttk.LabelFrame(mid, text="Confirm restock")
        right.pack(side="right", fill="y")

        ttk.Label(right, text="Vendor (optional)").pack(anchor="w", padx=10, pady=(10, 4))
        self.vendor_e = ttk.Entry(right, width=34)
        self.vendor_e.pack(padx=10)

        ttk.Label(right, text="Notes (optional)").pack(anchor="w", padx=10, pady=(10, 4))
        self.restock_notes = tk.Text(right, width=34, height=6)
        self.restock_notes.pack(padx=10)

        self.restock_total_var = tk.StringVar(value="Total USD: 0.00")
        ttk.Label(right, textvariable=self.restock_total_var).pack(anchor="w", padx=10, pady=10)

        ttk.Button(right, text="Confirm restock", style="Big.TButton", command=self.confirm_restock)\
            .pack(fill="x", padx=10, pady=(0, 10))
        

    def add_restock_item(self):
        picked = self.restock_pick.get().strip()
        if not picked:
            messagebox.showwarning("Validation", "Select a product.")
            self.toast("No product selected.", kind="warn")
            return

        sku = self.restock_sku_map.get(picked)
        if not sku:
            messagebox.showwarning("Validation", "Pick a product from the dropdown list.")
            self.toast("Pick from dropdown list.", kind="warn")
            return

        qty = self._parse_int(self.restock_qty_e.get().strip(), "Qty", 1)
        cost = self._parse_float(self.restock_cost_e.get().strip(), "Unit cost USD", 0.0)
        if qty is None or cost is None:
            return

        prod = get_product_by_sku(sku)
        if not prod:
            messagebox.showerror("Not found", "Product not found.")
            self.toast("Product not found.", kind="error")
            return
        prod_id, _, name, _cost, _price, _stock, _min = prod

        for it in self.restock_cart:
            if it["product_id"] == prod_id:
                it["qty"] += qty
                it["unit_cost_usd"] = float(cost)
                self.refresh_restock_view()
                self.restock_qty_e.delete(0, tk.END)
                self.toast("Updated restock qty.", kind="success", ms=1500)
                return

        self.restock_cart.append({
            "product_id": prod_id,
            "sku": sku,
            "name": name,
            "qty": qty,
            "unit_cost_usd": float(cost)
        })
        self.refresh_restock_view()
        self.restock_qty_e.delete(0, tk.END)
        self.toast("Added to restock cart.", kind="success", ms=1500)

    def refresh_restock_view(self):
        for item in self.restock_tree.get_children():
            self.restock_tree.delete(item)

        total = 0.0
        for it in self.restock_cart:
            line = it["qty"] * it["unit_cost_usd"]
            total += line
            self.restock_tree.insert("", "end", values=(
                it["sku"], it["name"], it["qty"], f"{it['unit_cost_usd']:.2f}", f"{line:.2f}"
            ))
        self.restock_total_var.set(f"Total USD: {total:.2f}")

    def remove_selected_restock(self):
        sel = self.restock_tree.selection()
        if not sel:
            return
        sku = self.restock_tree.item(sel[0], "values")[0]
        self.restock_cart = [it for it in self.restock_cart if it["sku"] != sku]
        self.refresh_restock_view()
        self.toast("Removed restock line.", kind="info", ms=1500)

    def clear_restock(self):
        self.restock_cart = []
        self.refresh_restock_view()
        self.toast("Restock cart cleared.", kind="info", ms=1500)

    def confirm_restock(self):
        if not self.restock_cart:
            messagebox.showwarning("Empty", "Restock cart is empty.")
            self.toast("Restock cart empty.", kind="warn")
            return

        vendor = self.vendor_e.get().strip() or None
        notes = self.restock_notes.get("1.0", "end").strip() or None
        dt_iso = datetime.now().replace(microsecond=0).isoformat(sep=" ")

        try:
            purchase_id = create_purchase(dt_iso, vendor, notes, self.restock_cart)
        except Exception as e:
            messagebox.showerror("Restock failed", str(e))
            self.toast("Restock failed.", kind="error")
            return

        messagebox.showinfo("OK", f"Restock saved. Purchase ID: {purchase_id}")
        self.toast(f"Restock saved (ID {purchase_id}).", kind="success")
        self.vendor_e.delete(0, tk.END)
        self.restock_notes.delete("1.0", "end")
        self.clear_restock()
        self.refresh_products()
        self.refresh_kpis()

    # ---------------- Excel + Reports tab ----------------
    def _build_tab_excel_reports(self):
        self.tab_excel = ttk.Frame(self.nb)
        self.nb.add(self.tab_excel, text="Excel + Reports")

        tab = self.tab_excel

        box1 = ttk.LabelFrame(tab, text="Import products from Excel")
        box1.pack(fill="x", padx=10, pady=10)

        ttk.Label(box1, text="Headers: sku | name | cost_usd | price_usd | stock | min_stock").pack(
            anchor="w", padx=10, pady=(8, 4)
        )
        ttk.Button(box1, text="Choose file and import", style="Big.TButton", command=self.import_excel)\
            .pack(anchor="w", padx=10, pady=(0, 10))

        box2 = ttk.LabelFrame(tab, text="Export report to Excel")
        box2.pack(fill="x", padx=10, pady=10)

        row = ttk.Frame(box2)
        row.pack(fill="x", padx=10, pady=10)

        ttk.Label(row, text="Preset window").pack(side="left")
        self.period = tk.StringVar(value="weekly")
        ttk.Radiobutton(row, text="Weekly (last 7 days)", value="weekly", variable=self.period).pack(side="left", padx=10)
        ttk.Radiobutton(row, text="Monthly (last 30 days)", value="monthly", variable=self.period).pack(side="left", padx=10)

        ttk.Button(box2, text="Export report", style="Big.TButton", command=self.export_report)\
            .pack(anchor="w", padx=10, pady=(0, 10))

    def import_excel(self):
        path = filedialog.askopenfilename(title="Select Excel file", filetypes=[("Excel files", "*.xlsx")])
        if not path:
            return
        try:
            ok, skipped = import_products_from_excel(path)
            messagebox.showinfo("Import done", f"Imported/updated: {ok}\nSkipped: {skipped}")
            self.toast(f"Excel import: {ok} ok, {skipped} skipped.", kind="success")
            self.refresh_products()
            self.refresh_kpis()
        except Exception as e:
            messagebox.showerror("Import error", str(e))
            self.toast("Excel import failed.", kind="error")

    def export_report(self):
        today = datetime.now().replace(microsecond=0)
        start = today - timedelta(days=7 if self.period.get() == "weekly" else 30)
        start_iso = start.isoformat(sep=" ")
        end_iso = today.isoformat(sep=" ")

        path = filedialog.asksaveasfilename(
            title="Save report as",
            defaultextension=".xlsx",
            filetypes=[("Excel files", "*.xlsx")],
            initialfile=f"report_{self.period.get()}_{date.today().isoformat()}.xlsx"
        )
        if not path:
            return
        try:
            export_sales_report_excel(path, start_iso, end_iso)
            messagebox.showinfo("Export done", f"Report saved:\n{path}")
            self.toast("Excel report exported.", kind="success")
        except Exception as e:
            messagebox.showerror("Export error", str(e))
            self.toast("Excel export failed.", kind="error")

    # ---------------- Helpers ----------------
    def _entry(self, parent, label, row):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=10, pady=6)
        e = ttk.Entry(parent, width=28)
        e.grid(row=row, column=1, sticky="ew", padx=10, pady=6)
        parent.columnconfigure(1, weight=1)
        return e

    def _parse_int(self, s: str, field: str, min_value: int | None = None):
        try:
            v = int(s)
        except ValueError:
            messagebox.showwarning("Validation", f"{field} must be an integer.")
            self.toast(f"{field} invalid.", kind="warn")
            return None
        if min_value is not None and v < min_value:
            messagebox.showwarning("Validation", f"{field} must be >= {min_value}.")
            self.toast(f"{field} too small.", kind="warn")
            return None
        return v

    def _parse_float(self, s: str, field: str, min_value: float | None = None):
        try:
            v = float(s)
        except ValueError:
            messagebox.showwarning("Validation", f"{field} must be a number (use dot, e.g. 12.50).")
            self.toast(f"{field} invalid.", kind="warn")
            return None
        if min_value is not None and v < min_value:
            messagebox.showwarning("Validation", f"{field} must be >= {min_value}.")
            self.toast(f"{field} too small.", kind="warn")
            return None
        return v


if __name__ == "__main__":
    App().mainloop()
