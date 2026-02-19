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
        self.configure(bg="#0b1220")

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

        main = ttk.Frame(self, style="App.TFrame")
        main.pack(fill="both", expand=True, padx=12, pady=(0, 10))

        self.sidebar = ttk.Frame(main, style="Card.TFrame", width=270)
        self.sidebar.pack(side="left", fill="y", padx=(0, 14))
        self.sidebar.pack_propagate(False)

        self.content = ttk.Frame(main, style="App.TFrame")
        self.content.pack(side="right", fill="both", expand=True)

        self.nb = ttk.Notebook(self.content, style="Side.TNotebook")
        self.nb.pack(fill="both", expand=True)

        self.products_view = ProductsView(self.nb, self)
        self.sales_view = SalesView(self.nb, self)
        self.restock_view = RestockView(self.nb, self)
        self.reports_view = ReportsView(self.nb, self)
        self.admin_view = None
        if self.can("admin"):
            self.admin_view = self._build_admin_tab()

        self._build_sidebar()
        self._build_status_bar()
        self._bind_keyboard_shortcuts()

        self.refresh_all(silent_fx=True, show_toast=False)
        self.toast("Ready.", kind="info", ms=1200)

    def _login_dialog(self):
        users = self.auth.list_users()
        dialog = tk.Toplevel(self)
        dialog.title("Login")
        dialog.geometry("430x240")
        dialog.transient(self)
        dialog.grab_set()

        username = tk.StringVar(value=users[0].username if users else "")
        pin = tk.StringVar()
        result = {"user": None}

        ttk.Label(dialog, text="Welcome", style="Title.TLabel").pack(anchor="w", padx=20, pady=(16, 2))
        ttk.Label(dialog, text="Sign in to continue.").pack(anchor="w", padx=20, pady=(0, 12))

        ttk.Label(dialog, text="User", font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=20, pady=(2, 4))
        cb = ttk.Combobox(dialog, textvariable=username, values=[u.username for u in users], state="readonly")
        cb.pack(fill="x", padx=20)

        ttk.Label(dialog, text="PIN", font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=20, pady=(12, 4))
        pin_entry = ttk.Entry(dialog, textvariable=pin, show="*")
        pin_entry.pack(fill="x", padx=20)

        def submit():
            try:
                result["user"] = self.auth.login(username.get(), pin.get())
                dialog.destroy()
            except Exception as e:
                messagebox.showerror("Login inválido", str(e), parent=dialog)

        def submit_on_enter(_event=None):
            submit()
            return "break"

        ttk.Button(dialog, text="Enter", style="Primary.TButton", command=submit).pack(pady=18)
        dialog.bind("<Return>", submit_on_enter)
        pin_entry.focus_set()

        self.wait_window(dialog)
        if not result["user"]:
            raise RuntimeError("Login is required")
        return result["user"]

    def _build_styles(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        
        bg = "#f4f7fb"
        panel = "#ffffff"
        accent = "#2563eb"
        accent_hover = "#1d4ed8"
        text_primary = "#0f172a"
        text_muted = "#64748b"
        border = "#dbe3ef"

        style.configure(".", background=bg, foreground=text_primary, font=("Segoe UI", 10))

        style.configure("Side.TNotebook", tabmargins=(0, 6, 0, 0), background=bg, borderwidth=0)
        style.configure(
            "Side.TNotebook.Tab",
            padding=(18, 10),
            font=("Segoe UI", 10, "bold"),
            background="#e2e8f0",
            foreground="#334155",
            borderwidth=0,
        )
        style.map(
            "Side.TNotebook.Tab",
            background=[("selected", panel), ("active", "#dbeafe")],
            foreground=[("selected", accent), ("active", accent)],
        )

        style.configure("App.TFrame", background=bg)
        style.configure("Card.TFrame", background=panel, relief="flat", borderwidth=1)
        style.configure("TFrame", background=bg)
        style.configure("TLabelframe", background=bg, borderwidth=1, relief="solid", bordercolor=border)
        style.configure("TLabelframe.Label", font=("Segoe UI", 10, "bold"), foreground="#334155")

        style.configure(
            "Topbar.TFrame",
            background="#0f172a",
        )
        style.configure("TopbarTitle.TLabel", background="#0f172a", foreground="#f8fafc", font=("Segoe UI", 13, "bold"))
        style.configure("TopbarMeta.TLabel", background="#0f172a", foreground="#cbd5e1", font=("Segoe UI", 9))
        style.configure("Status.TLabel", background=bg, foreground=text_muted)

        style.configure("TButton", padding=(12, 9), font=("Segoe UI", 10), borderwidth=0)
        style.configure("Big.TButton", padding=(14, 10), font=("Segoe UI", 10, "bold"))

        style.configure(
            "Primary.TButton",
            padding=(14, 10),
            font=("Segoe UI", 10, "bold"),
            foreground="white",
            background=accent,
            focusthickness=0,
        )
        style.map("Primary.TButton", background=[("active", accent_hover), ("pressed", accent_hover)])
        style.configure("Ghost.TButton", background="#e2e8f0", foreground="#334155")
        style.map("Ghost.TButton", background=[("active", "#cbd5e1")])

        style.configure("Title.TLabel", font=("Segoe UI", 12, "bold"), foreground=text_primary)
        style.configure("Subtitle.TLabel", font=("Segoe UI", 10), foreground=text_muted)
        style.configure("KPI.TLabel", font=("Segoe UI", 10), foreground=text_muted)
        style.configure("KPIValue.TLabel", font=("Segoe UI", 14, "bold"), foreground="#1e3a8a")

        style.configure("Modern.Treeview", rowheight=30, background="#f8fafc", fieldbackground=panel, borderwidth=0)
        style.configure("Modern.Treeview.Heading", font=("Segoe UI", 10, "bold"), background="#e2e8f0", foreground="#0f172a")
        style.map("Modern.Treeview", background=[("selected", "#dbeafe")], foreground=[("selected", "#0f172a")])

    def _build_topbar(self):
        top = ttk.Frame(self, style="Topbar.TFrame")
        top.pack(fill="x", padx=16, pady=(12, 10))

        left = ttk.Frame(top, style="Topbar.TFrame")
        left.pack(side="left", fill="x", expand=True, padx=14, pady=12)
        ttk.Label(left, text="Inventory & Sales Manager", style="TopbarTitle.TLabel").pack(anchor="w")
        ttk.Label(left, textvariable=self.fx_var, style="TopbarMeta.TLabel").pack(anchor="w", pady=(2, 0))

        ttk.Button(top, text="Refresh FX", style="Primary.TButton", command=self.update_fx).pack(side="left", padx=10)

        right = ttk.Frame(top, style="Topbar.TFrame")
        right.pack(side="right", padx=14)
        ttk.Label(right, text=f"User: {self.current_user.username} ({self.current_user.role})", style="TopbarMeta.TLabel").pack(anchor="e")
        ttk.Label(right, text=f"Base: {Path(self.db_path).name}", style="TopbarMeta.TLabel").pack(anchor="e")

    def _build_sidebar(self):
        header = ttk.Frame(self.sidebar, style="Card.TFrame")
        header.pack(fill="x", padx=12, pady=(12, 10))
        ttk.Label(header, text="Overview", style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            header,
            text="Use the tabs to navigate products, sales, restock and reports.",
            style="Subtitle.TLabel",
            wraplength=280,
        ).pack(anchor="w", pady=(3, 6))
        ttk.Button(header, text="🔄 Refresh data", style="Primary.TButton", command=self.refresh_all).pack(fill="x", pady=(4, 0))

        kpi = ttk.LabelFrame(self.sidebar, text="KPIs (7d)")
        kpi.pack(fill="x", padx=8)

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
        lowbox.pack(fill="both", expand=True, pady=(10, 10), padx=8)

        low_hint = ttk.Label(lowbox, text="Items at or below minimum stock", style="Subtitle.TLabel")
        low_hint.pack(anchor="w", padx=8, pady=(8, 0))

        low_wrap = ttk.Frame(lowbox, style="App.TFrame")
        low_wrap.pack(fill="both", expand=True, padx=8, pady=8)

        self.low_list = tk.Listbox(
            low_wrap,
            height=10,
            relief="flat",
            highlightthickness=1,
            highlightbackground="#cbd5e1",
            background="#f8fafc",
            foreground="#0f172a",
            selectbackground="#bfdbfe",
            activestyle="none",
        )
        low_scroll = ttk.Scrollbar(low_wrap, orient="vertical", command=self.low_list.yview)
        self.low_list.configure(yscrollcommand=low_scroll.set)
        self.low_list.pack(side="left", fill="both", expand=True)
        low_scroll.pack(side="right", fill="y")
        self.low_list.bind("<Double-1>", self.on_low_stock_open)
        self._low_items = []

    def _build_admin_tab(self):
        panel = ttk.Frame(self.nb, style="App.TFrame")
        self.nb.add(panel, text="Admin")

        ttk.Label(panel, text="Admin · User Management", style="Title.TLabel").pack(anchor="w", padx=12, pady=(12, 6))
        ttk.Label(panel, text="Gestiona usuarios y contraseñas desde una sección separada.", style="Subtitle.TLabel").pack(anchor="w", padx=12, pady=(0, 8))

        forms = ttk.Frame(panel, style="App.TFrame")
        forms.pack(fill="both", expand=True, padx=12, pady=(0, 10))

        create_box = ttk.LabelFrame(forms, text="Add user")
        create_box.pack(side="left", fill="both", expand=True, padx=(0, 8))

        password_box = ttk.LabelFrame(forms, text="Change my password")
        password_box.pack(side="right", fill="both", expand=True, padx=(8, 0))

        ttk.Label(create_box, text="New User").grid(row=0, column=0, sticky="w", padx=10, pady=(8, 4))
        self.new_user_e = ttk.Entry(create_box)
        self.new_user_e.grid(row=1, column=0, sticky="ew", padx=10)

        ttk.Label(create_box, text="PIN").grid(row=2, column=0, sticky="w", padx=10, pady=(8, 4))
        self.new_pin_e = ttk.Entry(create_box, show="*")
        self.new_pin_e.grid(row=3, column=0, sticky="ew", padx=10)

        ttk.Label(create_box, text="Rol").grid(row=4, column=0, sticky="w", padx=10, pady=(8, 4))
        self.new_role_var = tk.StringVar(value="seller")        
        ttk.Combobox(create_box, textvariable=self.new_role_var, values=["seller", "viewer"], state="readonly").grid(row=5, column=0, sticky="ew", padx=10)

        ttk.Button(create_box, text="Create User", style="Primary.TButton", command=self.create_user_from_admin).grid(row=6, column=0, sticky="ew", padx=10, pady=(10, 10))

        ttk.Label(password_box, text="Current").grid(row=0, column=0, sticky="w", padx=10, pady=(8, 4))
        self.current_pin_e = ttk.Entry(password_box, show="*")
        self.current_pin_e.grid(row=1, column=0, sticky="ew", padx=10)

        ttk.Label(password_box, text="New").grid(row=2, column=0, sticky="w", padx=10, pady=(8, 4))
        self.new_admin_pin_e = ttk.Entry(password_box, show="*")
        self.new_admin_pin_e.grid(row=3, column=0, sticky="ew", padx=10)

        ttk.Label(password_box, text="Confirm new").grid(row=4, column=0, sticky="w", padx=10, pady=(8, 4))
        self.confirm_admin_pin_e = ttk.Entry(password_box, show="*")
        self.confirm_admin_pin_e.grid(row=5, column=0, sticky="ew", padx=10)

        ttk.Button(password_box, text="Update password", style="Primary.TButton", command=self.change_my_password_from_admin).grid(row=6, column=0, sticky="ew", padx=10, pady=(10, 10))

        create_box.columnconfigure(0, weight=1)
        password_box.columnconfigure(0, weight=1)
        return panel

    def _build_status_bar(self):
        bar = ttk.Frame(self, style="App.TFrame")
        bar.pack(fill="x", padx=12, pady=(0, 10))
        ttk.Label(bar, textvariable=self.status_var, style="Status.TLabel").pack(side="left")
        ttk.Label(bar, text="Shortcut: Enter=main action | Ctrl+1..4 navegate", style="Status.TLabel").pack(side="left", padx=18)
        ttk.Label(bar, text=f"Logs: {self.logs_dir}", style="Status.TLabel").pack(side="right")

    def _bind_keyboard_shortcuts(self):
        self.bind("<Control-Key-1>", lambda _e: self.nb.select(self.products_view.frame))
        self.bind("<Control-Key-2>", lambda _e: self.nb.select(self.sales_view.frame))
        self.bind("<Control-Key-3>", lambda _e: self.nb.select(self.restock_view.frame))
        self.bind("<Control-Key-4>", lambda _e: self.nb.select(self.reports_view.frame))
        if self.admin_view is not None:
            self.bind("<Control-Key-5>", lambda _e: self.nb.select(self.admin_view))

        self.bind_class("TEntry", "<Return>", self._invoke_default_action, add="+")
        self.bind_class("Entry", "<Return>", self._invoke_default_action, add="+")
        self.bind_class("TCombobox", "<Return>", self._invoke_default_action, add="+")

    def _collect_buttons(self, container):
        if container is None or not hasattr(container, "winfo_children"):
            return []
        found = []
        stack = list(container.winfo_children())
        while stack:
            child = stack.pop(0)
            if isinstance(child, ttk.Button):
                found.append(child)
            if hasattr(child, "winfo_children"):
                stack.extend(child.winfo_children())
        return found

    def _invoke_default_action(self, event):
        widget = event.widget
        current_tab = self.nametowidget(self.nb.select()) if self.nb.select() else None

        containers = []
        cursor = widget
        while cursor is not None:
            containers.append(cursor)
            if cursor == current_tab:
                break
            parent_name = cursor.winfo_parent()
            if not parent_name:
                break
            cursor = cursor.nametowidget(parent_name)

        def first_enabled(buttons):
            for btn in buttons:
                state = str(btn.cget("state"))
                if state != "disabled" and btn.winfo_ismapped():
                    return btn
            return None

        for container in containers:
            btn = first_enabled(self._collect_buttons(container))
            if btn is not None:
                btn.invoke()
                return "break"

        btn = first_enabled(self._collect_buttons(current_tab))
        if btn is not None:
            btn.invoke()
            return "break"
        return None

    def create_user_from_admin(self):
        try:
            user = self.new_user_e.get().strip()
            pin = self.new_pin_e.get().strip()
            role = self.new_role_var.get().strip().lower()
            uid = self.auth.create_user(self.current_user, user, pin, role)
            self.new_user_e.delete(0, tk.END)
            self.new_pin_e.delete(0, tk.END)
            self.new_role_var.set("seller")
            self.toast(f"User created successfuly (ID {uid}).", kind="success")
        except Exception as e:
            self.handle_error("User management", e, "The user could not be created.")

    def change_my_password_from_admin(self):
        try:
            current_pin = self.current_pin_e.get().strip()
            new_pin = self.new_admin_pin_e.get().strip()
            confirm_pin = self.confirm_admin_pin_e.get().strip()
            self.auth.change_my_pin(self.current_user, current_pin, new_pin, confirm_pin)
            self.current_pin_e.delete(0, tk.END)
            self.new_admin_pin_e.delete(0, tk.END)
            self.confirm_admin_pin_e.delete(0, tk.END)
            self.toast("Password successfuly updated.", kind="success")
        except Exception as e:
            self.handle_error("Admin profile", e, "The password could not be updated.")

    def handle_error(self, title: str, err: Exception, toast_text: str) -> None:
        if isinstance(err, AppError):
            message = str(err)
        else:
            message = f"Unexpected error: {err}"
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
        if not low:
            self.low_list.insert(tk.END, "✅ No low stock products")
            return
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
