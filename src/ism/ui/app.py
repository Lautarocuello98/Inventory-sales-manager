from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime, timedelta
import logging
from pathlib import Path

from ism.domain.errors import AppError
from ism.ui.views.products_view import ProductsView
from ism.ui.views.sales_view import SalesView
from ism.ui.views.restock_view import RestockView
from ism.ui.views.reports_view import ReportsView

log = logging.getLogger(__name__)


class App(tk.Tk):
    def __init__(
        self,
        fx_service,
        inventory_service,
        sales_service,
        purchase_service,
        excel_service,
        reporting_service,
        auth_service,
        db_path: str,
        logs_dir: str,
    ):
        super().__init__()
        self.title("Inventory & Sales Manager Pro")
        self.geometry("1360x820")
        self.minsize(1180, 680)

        self.fx = fx_service
        self.inventory = inventory_service
        self.sales = sales_service
        self.purchases = purchase_service
        self.excel = excel_service
        self.reporting = reporting_service
        self.auth = auth_service
        self.current_user = self._login_dialog()

        self.db_path = db_path
        self.logs_dir = logs_dir

        self.fx_var = tk.StringVar(value="FX (USD→ARS): not loaded")
        self.status_var = tk.StringVar(value="")
        self._toast_after_id = None

        self._build_styles()
        self._build_topbar()

        main = ttk.Frame(self)
        main.pack(fill="both", expand=True, padx=16, pady=(0, 10))

        self.sidebar = ttk.Frame(main)
        self.sidebar.pack(side="left", fill="y", padx=(0, 14))

        self.content = ttk.Frame(main)
        self.content.pack(side="right", fill="both", expand=True)

        self.nb = ttk.Notebook(self.content, style="Side.TNotebook")
        self.nb.pack(fill="both", expand=True)

        self.products_view = ProductsView(self.nb, self)
        self.sales_view = SalesView(self.nb, self)
        self.restock_view = RestockView(self.nb, self)
        self.reports_view = ReportsView(self.nb, self)

        self._build_sidebar()
        self._build_status_bar()

        self.refresh_all(silent_fx=True, show_toast=False)
        self.toast("Ready.", kind="info", ms=1200)

    def _login_dialog(self):
        users = self.auth.list_users()
        dialog = tk.Toplevel(self)
        dialog.title("Login")
        dialog.geometry("420x220")
        dialog.transient(self)
        dialog.grab_set()

        username = tk.StringVar(value=users[0].username if users else "")
        pin = tk.StringVar()
        result = {"user": None}

        ttk.Label(dialog, text="Usuario", font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=20, pady=(20, 4))
        cb = ttk.Combobox(dialog, textvariable=username, values=[u.username for u in users], state="readonly")
        cb.pack(fill="x", padx=20)
        ttk.Label(dialog, text="PIN", font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=20, pady=(12, 4))
        ttk.Entry(dialog, textvariable=pin, show="*").pack(fill="x", padx=20)

        def submit():
            try:
                result["user"] = self.auth.login(username.get(), pin.get())
                dialog.destroy()
            except Exception as e:
                messagebox.showerror("Login inválido", str(e), parent=dialog)

        ttk.Button(dialog, text="Ingresar", command=submit).pack(pady=18)
        self.wait_window(dialog)
        if not result["user"]:
            raise RuntimeError("Login is required")
        return result["user"]

    def _build_styles(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.layout("Side.TNotebook.Tab", [])
        style.configure("Side.TNotebook", tabmargins=0, background="#f4f7fb")
        style.configure("TFrame", background="#f4f7fb")
        style.configure("TLabelframe", background="#f4f7fb")
        style.configure("TLabelframe.Label", font=("Segoe UI", 10, "bold"))
        style.configure("Big.TButton", padding=(14, 10))
        style.configure("Title.TLabel", font=("Segoe UI", 12, "bold"))
        style.configure("KPI.TLabel", font=("Segoe UI", 10))
        style.configure("KPIValue.TLabel", font=("Segoe UI", 11, "bold"), foreground="#1f4e79")

    def _build_topbar(self):
        top = ttk.Frame(self)
        top.pack(fill="x", padx=16, pady=12)

        ttk.Label(top, textvariable=self.fx_var, style="Title.TLabel").pack(side="left")
        ttk.Button(top, text="Update FX", command=self.update_fx).pack(side="left", padx=10)

        ttk.Label(top, text=f"Usuario: {self.current_user.username} ({self.current_user.role})").pack(side="right", padx=16)
        ttk.Label(top, text=f"DB: {Path(self.db_path).name}").pack(side="right")

    def _build_sidebar(self):
        box = ttk.LabelFrame(self.sidebar, text="Quick Actions")
        box.pack(fill="x", pady=(0, 10))

        ttk.Button(box, text="📦 Products", style="Big.TButton", command=lambda: self.nb.select(self.products_view.frame)).pack(fill="x", padx=10, pady=(10, 6))
        ttk.Button(box, text="🧾 New Sale", style="Big.TButton", command=lambda: self.nb.select(self.sales_view.frame)).pack(fill="x", padx=10, pady=6)
        ttk.Button(box, text="🔁 Restock", style="Big.TButton", command=lambda: self.nb.select(self.restock_view.frame)).pack(fill="x", padx=10, pady=6)
        ttk.Button(box, text="📊 Reports + Dashboard", style="Big.TButton", command=lambda: self.nb.select(self.reports_view.frame)).pack(fill="x", padx=10, pady=6)
        ttk.Button(box, text="🔄 Refresh", style="Big.TButton", command=self.refresh_all).pack(fill="x", padx=10, pady=(6, 10))

        kpi = ttk.LabelFrame(self.sidebar, text="KPIs (7d)")
        kpi.pack(fill="x")

        self.k_products = ttk.Label(kpi, text="-", style="KPIValue.TLabel")
        self.k_units = ttk.Label(kpi, text="-", style="KPIValue.TLabel")
        self.k_low = ttk.Label(kpi, text="-", style="KPIValue.TLabel")
        self.k_rev7 = ttk.Label(kpi, text="-", style="KPIValue.TLabel")
        self.k_profit7 = ttk.Label(kpi, text="-", style="KPIValue.TLabel")

        labels = ["Products", "Units", "Low stock", "Revenue USD", "Profit USD"]
        widgets = [self.k_products, self.k_units, self.k_low, self.k_rev7, self.k_profit7]
        for i, (lab, w) in enumerate(zip(labels, widgets)):
            ttk.Label(kpi, text=lab, style="KPI.TLabel").grid(row=i, column=0, sticky="w", padx=10, pady=(8 if i == 0 else 2, 2))
            w.grid(row=i, column=1, sticky="e", padx=10, pady=(8 if i == 0 else 2, 2))

        lowbox = ttk.LabelFrame(self.sidebar, text="Low Stock (double click)")
        lowbox.pack(fill="both", expand=True, pady=(10, 0))

        self.low_list = tk.Listbox(lowbox, height=10)
        self.low_list.pack(fill="both", expand=True, padx=10, pady=10)
        self.low_list.bind("<Double-1>", self.on_low_stock_open)
        self._low_items = []

    def _build_status_bar(self):
        bar = ttk.Frame(self)
        bar.pack(fill="x", padx=12, pady=(0, 10))
        ttk.Label(bar, textvariable=self.status_var).pack(side="left")
        ttk.Label(bar, text=f"Logs: {self.logs_dir}").pack(side="right")

    def handle_error(self, title: str, err: Exception, toast_text: str) -> None:
        if isinstance(err, AppError):
            message = str(err)
        else:
            message = f"Error inesperado: {err}"
        log.exception("%s: %s", title, err)
        messagebox.showerror(title, message)
        self.toast(toast_text, kind="error")

    def can(self, *roles: str) -> bool:
        return self.current_user.role in set(roles)

    def toast(self, msg: str, kind: str = "info", ms: int = 2500):
        prefix = {"info": "ℹ ", "success": "✅ ", "warn": "⚠ ", "error": "❌ "}.get(kind, "")
        self.status_var.set(prefix + msg)
        if self._toast_after_id is not None:
            try:
                self.after_cancel(self._toast_after_id)
            except Exception:
                pass
        self._toast_after_id = self.after(ms, lambda: self.status_var.set(""))

    def update_fx(self, silent: bool = False):
        try:
            rate = self.fx.get_today_rate()
            self.fx_var.set(f"FX (USD→ARS): {rate:.4f}")
            if not silent:
                self.toast(f"FX updated: {rate:.4f}", kind="success")
        except Exception as e:
            if not silent:
                self.handle_error("FX", e, "FX update failed.")

    def refresh_all(self, silent_fx: bool = False, show_toast: bool = True):
        self.update_fx(silent=silent_fx)

        self.products_view.refresh()
        self.sales_view.refresh()
        self.restock_view.refresh()
        self.refresh_kpis()
        self.refresh_low_stock_panel()
        if show_toast:
            self.toast("Refreshed.", kind="info", ms=1200)

    def refresh_kpis(self):
        try:
            products = self.inventory.list_products()
            products_count = len(products)
            units = sum(int(p.stock) for p in products)
            low_count = sum(1 for p in products if int(p.stock) <= int(p.min_stock))

            end = datetime.now().replace(microsecond=0)
            start = end - timedelta(days=7)
            totals, _ = self.sales.sales_summary_between(start.isoformat(sep=" "), end.isoformat(sep=" "))
            _cnt, rev_usd, _rev_ars, profit_usd = totals

            self.k_products.config(text=str(products_count))
            self.k_units.config(text=str(units))
            self.k_low.config(text=str(low_count))
            self.k_rev7.config(text=f"{float(rev_usd):.2f}")
            self.k_profit7.config(text=f"{float(profit_usd):.2f}")
        except Exception as e:
            log.exception("KPI refresh failed: %s", e)

    def refresh_low_stock_panel(self):
        self.low_list.delete(0, tk.END)
        self._low_items = []
        rows = self.inventory.list_products()
        low = [p for p in rows if int(p.stock) <= int(p.min_stock)]
        for p in low:
            self.low_list.insert(tk.END, f"{p.sku} — {p.name} ({p.stock}/{p.min_stock})")
            self._low_items.append(p.sku)

    def on_low_stock_open(self, _evt=None):
        sel = self.low_list.curselection()
        if not sel:
            return
        sku = self._low_items[sel[0]]
        self.nb.select(self.products_view.frame)
        self.products_view.select_product_in_tree(sku)
        self.toast(f"Selected low stock: {sku}", kind="warn", ms=2000)
