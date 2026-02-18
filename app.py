import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime, date, timedelta

from db import (
    init_db, add_product, list_products, get_product_by_sku,
    create_sale, list_sales_between, get_sale_header, sale_items_for_sale,
    create_purchase
)
from api_fx import get_today_rate
from excel_io import import_products_from_excel, export_sales_report_excel


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Inventory & Sales Manager (USD + ARS)")
        self.geometry("1150x680")
        self.minsize(1000, 600)

        init_db()
        self.cart = []
        self.restock_cart = []

        self.fx_var = tk.StringVar(value="FX (USD→ARS): not loaded")
        self._build_topbar()

        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="both", expand=True, padx=12, pady=10)

        self._build_tab_products()
        self._build_tab_sales()
        self._build_tab_sales_history()
        self._build_tab_restock()
        self._build_tab_excel_reports()

        self.refresh_products()

    # ---------- Top bar ----------
    def _build_topbar(self):
        top = ttk.Frame(self)
        top.pack(fill="x", padx=12, pady=10)

        ttk.Label(top, textvariable=self.fx_var).pack(side="left")
        ttk.Button(top, text="Update FX", command=self.update_fx).pack(side="left", padx=10)
        ttk.Button(top, text="Refresh Products", command=self.refresh_products).pack(side="right")

    def update_fx(self):
        try:
            rate = get_today_rate()
            self.fx_var.set(f"FX (USD→ARS): {rate:.4f}")
        except Exception as e:
            messagebox.showerror("FX Error", str(e))

    # ---------- Products tab ----------
    def _build_tab_products(self):
        tab = ttk.Frame(self.nb)
        self.nb.add(tab, text="Products")

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
        ttk.Button(btns, text="Add", command=self.on_add_product).grid(row=0, column=0, sticky="ew", padx=(0, 6))
        ttk.Button(btns, text="Clear", command=self.clear_product_form).grid(row=0, column=1, sticky="ew", padx=(6, 0))

        cols = ("id", "sku", "name", "cost", "price", "stock", "min")
        self.prod_tree = ttk.Treeview(right, columns=cols, show="headings", height=20)
        heads = {"id":"ID","sku":"SKU","name":"Name","cost":"Cost USD","price":"Price USD","stock":"Stock","min":"Min"}
        widths = {"id":60,"sku":120,"name":300,"cost":110,"price":110,"stock":90,"min":90}
        for c in cols:
            self.prod_tree.heading(c, text=heads[c])
            self.prod_tree.column(c, width=widths[c], anchor="w")

        vsb = ttk.Scrollbar(right, orient="vertical", command=self.prod_tree.yview)
        self.prod_tree.configure(yscrollcommand=vsb.set)
        self.prod_tree.pack(side="left", fill="both", expand=True, padx=(10, 0), pady=10)
        vsb.pack(side="right", fill="y", padx=(0, 10), pady=10)

    def on_add_product(self):
        sku = self.p_sku.get().strip()
        name = self.p_name.get().strip()
        if not sku or not name:
            messagebox.showwarning("Validation", "SKU and Name are required.")
            return

        cost = self._parse_float(self.p_cost.get().strip(), "Cost USD", 0.0)
        price = self._parse_float(self.p_price.get().strip(), "Price USD", 0.0)
        stock = self._parse_int(self.p_stock.get().strip(), "Stock", 0)
        min_stock = self._parse_int(self.p_min.get().strip(), "Min stock", 0)
        if None in (cost, price, stock, min_stock):
            return

        try:
            add_product(sku, name, cost, price, stock, min_stock)
            messagebox.showinfo("OK", "Product added.")
            self.refresh_products()
            self.clear_product_form()
        except Exception as e:
            messagebox.showerror("DB Error", str(e))

    def clear_product_form(self):
        for e in (self.p_sku, self.p_name, self.p_cost, self.p_price, self.p_stock, self.p_min):
            e.delete(0, tk.END)
        self.p_sku.focus_set()

    def refresh_products(self):
        try:
            rows = list_products()
        except Exception as e:
            messagebox.showerror("DB Error", str(e))
            return

        for item in self.prod_tree.get_children():
            self.prod_tree.delete(item)

        skus = []
        for r in rows:
            self.prod_tree.insert("", "end", values=(
                r[0], r[1], r[2], f"{r[3]:.2f}", f"{r[4]:.2f}", r[5], r[6]
            ))
            skus.append(r[1])

        if hasattr(self, "sale_sku_combo"):
            self.sale_sku_combo["values"] = skus
        if hasattr(self, "restock_sku_combo"):
            self.restock_sku_combo["values"] = skus

    # ---------- Sales tab ----------
    def _build_tab_sales(self):
        tab = ttk.Frame(self.nb)
        self.nb.add(tab, text="Sales")

        top = ttk.LabelFrame(tab, text="Add item to cart")
        top.pack(fill="x", padx=10, pady=10)

        ttk.Label(top, text="Product SKU").grid(row=0, column=0, padx=10, pady=8, sticky="w")
        self.sale_sku = tk.StringVar()
        self.sale_sku_combo = ttk.Combobox(top, textvariable=self.sale_sku, width=24, state="readonly")
        self.sale_sku_combo.grid(row=0, column=1, padx=10, pady=8, sticky="w")

        ttk.Label(top, text="Qty").grid(row=0, column=2, padx=10, pady=8, sticky="w")
        self.sale_qty_e = ttk.Entry(top, width=10)
        self.sale_qty_e.grid(row=0, column=3, padx=10, pady=8, sticky="w")

        ttk.Button(top, text="Add to cart", command=self.add_to_cart).grid(row=0, column=4, padx=10, pady=8)

        mid = ttk.Frame(tab)
        mid.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        cart_box = ttk.LabelFrame(mid, text="Cart")
        cart_box.pack(side="left", fill="both", expand=True, padx=(0, 10))

        cols = ("sku", "name", "qty", "unit", "line")
        self.cart_tree = ttk.Treeview(cart_box, columns=cols, show="headings", height=16)
        heads = {"sku":"SKU","name":"Name","qty":"Qty","unit":"Unit USD","line":"Line USD"}
        widths = {"sku":120,"name":360,"qty":70,"unit":110,"line":110}
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

        ttk.Button(right, text="Confirm sale", command=self.confirm_sale).pack(fill="x", padx=10, pady=(0, 10))

    def add_to_cart(self):
        sku = self.sale_sku.get().strip()
        if not sku:
            messagebox.showwarning("Validation", "Select a SKU.")
            return
        qty = self._parse_int(self.sale_qty_e.get().strip(), "Qty", 1)
        if qty is None:
            return

        prod = get_product_by_sku(sku)
        if not prod:
            messagebox.showerror("Not found", "Product not found.")
            return

        prod_id, _, name, _, price_usd, stock, _ = prod
        if qty > stock:
            messagebox.showwarning("Stock", f"Not enough stock. Available: {stock}")
            return

        for it in self.cart:
            if it["product_id"] == prod_id:
                new_qty = it["qty"] + qty
                if new_qty > stock:
                    messagebox.showwarning("Stock", f"Not enough stock. Available: {stock}")
                    return
                it["qty"] = new_qty
                self.refresh_cart_view()
                self.sale_qty_e.delete(0, tk.END)
                return

        self.cart.append({"product_id": prod_id, "sku": sku, "name": name, "qty": qty, "unit_price_usd": float(price_usd)})
        self.refresh_cart_view()
        self.sale_qty_e.delete(0, tk.END)

    def refresh_cart_view(self):
        for item in self.cart_tree.get_children():
            self.cart_tree.delete(item)

        total_usd = 0.0
        for it in self.cart:
            line = it["qty"] * it["unit_price_usd"]
            total_usd += line
            self.cart_tree.insert("", "end", values=(it["sku"], it["name"], it["qty"], f"{it['unit_price_usd']:.2f}", f"{line:.2f}"))

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
        values = self.cart_tree.item(sel[0], "values")
        sku = values[0]
        self.cart = [it for it in self.cart if it["sku"] != sku]
        self.refresh_cart_view()

    def clear_cart(self):
        self.cart = []
        self.refresh_cart_view()

    def confirm_sale(self):
        if not self.cart:
            messagebox.showwarning("Empty", "Cart is empty.")
            return

        try:
            fx = get_today_rate()
            self.fx_var.set(f"FX (USD→ARS): {fx:.4f}")
        except Exception as e:
            messagebox.showerror("FX Error", f"Cannot confirm sale without FX.\n\n{e}")
            return

        notes = self.sale_notes.get("1.0", "end").strip() or None
        dt_iso = datetime.now().replace(microsecond=0).isoformat(sep=" ")

        try:
            sale_id = create_sale(dt_iso, fx, notes, self.cart)
        except Exception as e:
            messagebox.showerror("Sale failed", str(e))
            return

        messagebox.showinfo("OK", f"Sale saved. ID: {sale_id}")
        self.sale_notes.delete("1.0", "end")
        self.clear_cart()
        self.refresh_products()
        self.refresh_sales_history()

    # ---------- Sales History tab ----------
    def _build_tab_sales_history(self):
        tab = ttk.Frame(self.nb)
        self.nb.add(tab, text="Sales History")

        top = ttk.Frame(tab)
        top.pack(fill="x", padx=10, pady=10)

        ttk.Label(top, text="Window").pack(side="left")
        self.hist_window = tk.StringVar(value="7")
        ttk.Combobox(top, textvariable=self.hist_window, values=["7", "30", "90"], width=6, state="readonly").pack(side="left", padx=10)
        ttk.Label(top, text="days").pack(side="left")

        ttk.Button(top, text="Refresh", command=self.refresh_sales_history).pack(side="left", padx=10)

        box = ttk.LabelFrame(tab, text="Double click a sale to view details")
        box.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        cols = ("id", "dt", "usd", "fx", "ars", "notes")
        self.sales_tree = ttk.Treeview(box, columns=cols, show="headings", height=18)
        heads = {"id":"Sale ID","dt":"Datetime","usd":"Total USD","fx":"FX","ars":"Total ARS","notes":"Notes"}
        widths = {"id":80,"dt":190,"usd":110,"fx":90,"ars":120,"notes":420}
        for c in cols:
            self.sales_tree.heading(c, text=heads[c])
            self.sales_tree.column(c, width=widths[c], anchor="w")
        self.sales_tree.pack(fill="both", expand=True, padx=10, pady=10)

        self.sales_tree.bind("<Double-1>", self.open_sale_details)

        self.refresh_sales_history()

    def refresh_sales_history(self):
        days = int(self.hist_window.get())
        end = datetime.now().replace(microsecond=0)
        start = end - timedelta(days=days)

        rows = list_sales_between(start.isoformat(sep=" "), end.isoformat(sep=" "))

        for item in self.sales_tree.get_children():
            self.sales_tree.delete(item)

        for s in rows:
            self.sales_tree.insert("", "end", values=(
                s[0], s[1], f"{float(s[2]):.2f}", f"{float(s[3]):.4f}", f"{float(s[4]):.2f}", (s[5] or "")[:120]
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
        win.geometry("900x500")

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
        heads = {"sku":"SKU","name":"Name","qty":"Qty","unit":"Unit USD","line":"Line USD","cost":"Cost USD","margin":"Line Margin USD"}
        widths = {"sku":120,"name":320,"qty":70,"unit":110,"line":110,"cost":110,"margin":130}
        for c in cols:
            tree.heading(c, text=heads[c])
            tree.column(c, width=widths[c], anchor="w")
        tree.pack(fill="both", expand=True, padx=10, pady=10)

        total_margin = 0.0
        for sku, name, qty, unit, line, cost, margin in items:
            total_margin += float(margin)
            tree.insert("", "end", values=(sku, name, qty, f"{unit:.2f}", f"{line:.2f}", f"{cost:.2f}", f"{margin:.2f}"))

        ttk.Label(win, text=f"Margin USD (this sale): {total_margin:.2f}").pack(anchor="w", padx=14, pady=(0, 10))

    # ---------- Restock tab ----------
    def _build_tab_restock(self):
        tab = ttk.Frame(self.nb)
        self.nb.add(tab, text="Restock")

        top = ttk.LabelFrame(tab, text="Add restock item")
        top.pack(fill="x", padx=10, pady=10)

        ttk.Label(top, text="Product SKU").grid(row=0, column=0, padx=10, pady=8, sticky="w")
        self.restock_sku = tk.StringVar()
        self.restock_sku_combo = ttk.Combobox(top, textvariable=self.restock_sku, width=24, state="readonly")
        self.restock_sku_combo.grid(row=0, column=1, padx=10, pady=8, sticky="w")

        ttk.Label(top, text="Qty").grid(row=0, column=2, padx=10, pady=8, sticky="w")
        self.restock_qty_e = ttk.Entry(top, width=10)
        self.restock_qty_e.grid(row=0, column=3, padx=10, pady=8, sticky="w")

        ttk.Label(top, text="Unit cost USD").grid(row=0, column=4, padx=10, pady=8, sticky="w")
        self.restock_cost_e = ttk.Entry(top, width=12)
        self.restock_cost_e.grid(row=0, column=5, padx=10, pady=8, sticky="w")

        ttk.Button(top, text="Add", command=self.add_restock_item).grid(row=0, column=6, padx=10, pady=8)

        mid = ttk.Frame(tab)
        mid.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        box = ttk.LabelFrame(mid, text="Restock cart")
        box.pack(side="left", fill="both", expand=True, padx=(0, 10))

        cols = ("sku", "name", "qty", "unit", "line")
        self.restock_tree = ttk.Treeview(box, columns=cols, show="headings", height=16)
        heads = {"sku":"SKU","name":"Name","qty":"Qty","unit":"Unit cost USD","line":"Line USD"}
        widths = {"sku":120,"name":360,"qty":70,"unit":130,"line":110}
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

        ttk.Button(right, text="Confirm restock", command=self.confirm_restock).pack(fill="x", padx=10, pady=(0, 10))

    def add_restock_item(self):
        sku = self.restock_sku.get().strip()
        if not sku:
            messagebox.showwarning("Validation", "Select a SKU.")
            return
        qty = self._parse_int(self.restock_qty_e.get().strip(), "Qty", 1)
        cost = self._parse_float(self.restock_cost_e.get().strip(), "Unit cost USD", 0.0)
        if qty is None or cost is None:
            return

        prod = get_product_by_sku(sku)
        if not prod:
            messagebox.showerror("Not found", "Product not found.")
            return
        prod_id, _, name, _, _, _, _ = prod

        # accumulate if exists
        for it in self.restock_cart:
            if it["product_id"] == prod_id:
                it["qty"] += qty
                it["unit_cost_usd"] = cost  # last cost
                self.refresh_restock_view()
                self.restock_qty_e.delete(0, tk.END)
                return

        self.restock_cart.append({"product_id": prod_id, "sku": sku, "name": name, "qty": qty, "unit_cost_usd": float(cost)})
        self.refresh_restock_view()
        self.restock_qty_e.delete(0, tk.END)

    def refresh_restock_view(self):
        for item in self.restock_tree.get_children():
            self.restock_tree.delete(item)

        total = 0.0
        for it in self.restock_cart:
            line = it["qty"] * it["unit_cost_usd"]
            total += line
            self.restock_tree.insert("", "end", values=(it["sku"], it["name"], it["qty"], f"{it['unit_cost_usd']:.2f}", f"{line:.2f}"))

        self.restock_total_var.set(f"Total USD: {total:.2f}")

    def remove_selected_restock(self):
        sel = self.restock_tree.selection()
        if not sel:
            return
        sku = self.restock_tree.item(sel[0], "values")[0]
        self.restock_cart = [it for it in self.restock_cart if it["sku"] != sku]
        self.refresh_restock_view()

    def clear_restock(self):
        self.restock_cart = []
        self.refresh_restock_view()

    def confirm_restock(self):
        if not self.restock_cart:
            messagebox.showwarning("Empty", "Restock cart is empty.")
            return

        vendor = self.vendor_e.get().strip() or None
        notes = self.restock_notes.get("1.0", "end").strip() or None
        dt_iso = datetime.now().replace(microsecond=0).isoformat(sep=" ")

        try:
            purchase_id = create_purchase(dt_iso, vendor, notes, self.restock_cart)
        except Exception as e:
            messagebox.showerror("Restock failed", str(e))
            return

        messagebox.showinfo("OK", f"Restock saved. Purchase ID: {purchase_id}")
        self.vendor_e.delete(0, tk.END)
        self.restock_notes.delete("1.0", "end")
        self.clear_restock()
        self.refresh_products()

    # ---------- Excel + Reports tab ----------
    def _build_tab_excel_reports(self):
        tab = ttk.Frame(self.nb)
        self.nb.add(tab, text="Excel + Reports")

        box1 = ttk.LabelFrame(tab, text="Import products from Excel")
        box1.pack(fill="x", padx=10, pady=10)

        ttk.Label(box1, text="Headers required: sku | name | cost_usd | price_usd | stock | min_stock").pack(
            anchor="w", padx=10, pady=(8, 4)
        )
        ttk.Button(box1, text="Choose file and import", command=self.import_excel).pack(
            anchor="w", padx=10, pady=(0, 10)
        )

        box2 = ttk.LabelFrame(tab, text="Export sales report to Excel")
        box2.pack(fill="x", padx=10, pady=10)

        row = ttk.Frame(box2)
        row.pack(fill="x", padx=10, pady=10)

        ttk.Label(row, text="Preset window").pack(side="left")
        self.period = tk.StringVar(value="weekly")
        ttk.Radiobutton(row, text="Weekly (last 7 days)", value="weekly", variable=self.period).pack(side="left", padx=10)
        ttk.Radiobutton(row, text="Monthly (last 30 days)", value="monthly", variable=self.period).pack(side="left", padx=10)

        ttk.Button(box2, text="Export report", command=self.export_report).pack(anchor="w", padx=10, pady=(0, 10))

    def import_excel(self):
        path = filedialog.askopenfilename(title="Select Excel file", filetypes=[("Excel files", "*.xlsx")])
        if not path:
            return
        try:
            ok, skipped = import_products_from_excel(path)
            messagebox.showinfo("Import done", f"Imported/updated: {ok}\nSkipped: {skipped}")
            self.refresh_products()
        except Exception as e:
            messagebox.showerror("Import error", str(e))

    def export_report(self):
        today = datetime.now().replace(microsecond=0)
        start = today - timedelta(days=7 if self.period.get() == "weekly" else 30)

        start_iso = start.isoformat(sep=" ")
        end_iso = today.isoformat(sep=" ")

        path = filedialog.asksaveasfilename(
            title="Save report as",
            defaultextension=".xlsx",
            filetypes=[("Excel files", "*.xlsx")],
            initialfile=f"sales_report_{self.period.get()}_{date.today().isoformat()}.xlsx"
        )
        if not path:
            return

        try:
            export_sales_report_excel(path, start_iso, end_iso)
            messagebox.showinfo("Export done", f"Report saved:\n{path}")
        except Exception as e:
            messagebox.showerror("Export error", str(e))

    # ---------- Helpers ----------
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
            return None
        if min_value is not None and v < min_value:
            messagebox.showwarning("Validation", f"{field} must be >= {min_value}.")
            return None
        return v

    def _parse_float(self, s: str, field: str, min_value: float | None = None):
        try:
            v = float(s)
        except ValueError:
            messagebox.showwarning("Validation", f"{field} must be a number (use dot, e.g. 12.50).")
            return None
        if min_value is not None and v < min_value:
            messagebox.showwarning("Validation", f"{field} must be >= {min_value}.")
            return None
        return v


if __name__ == "__main__":
    app = App()
    app.mainloop()
