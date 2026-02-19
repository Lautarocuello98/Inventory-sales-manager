from __future__ import annotations

import tkinter as tk
from tkinter import ttk, filedialog
from datetime import datetime, date, timedelta


class ReportsView:
    def __init__(self, notebook: ttk.Notebook, app):
        self.app = app
        self.frame = ttk.Frame(notebook)
        notebook.add(self.frame, text="Excel + Reports")

        self.period = tk.StringVar(value="weekly")
        self._build()

    def _build(self):
        tab = self.frame

        box1 = ttk.LabelFrame(tab, text="Import restock from Excel")
        box1.pack(fill="x", padx=10, pady=10)

        ttk.Label(box1, text="Headers: sku | name | cost_usd | price_usd | stock | min_stock").pack(anchor="w", padx=10, pady=(8, 4))
        ttk.Button(box1, text="Choose file and import", style="Big.TButton", command=self.import_excel).pack(anchor="w", padx=10, pady=(0, 10))

        box2 = ttk.LabelFrame(tab, text="Export report to Excel")
        box2.pack(fill="x", padx=10, pady=10)

        row = ttk.Frame(box2)
        row.pack(fill="x", padx=10, pady=10)

        ttk.Label(row, text="Preset window").pack(side="left")
        ttk.Radiobutton(row, text="Weekly (last 7 days)", value="weekly", variable=self.period).pack(side="left", padx=10)
        ttk.Radiobutton(row, text="Monthly (last 30 days)", value="monthly", variable=self.period).pack(side="left", padx=10)

        ttk.Button(box2, text="Export report", style="Big.TButton", command=self.export_report).pack(anchor="w", padx=10, pady=(0, 10))

        dash = ttk.LabelFrame(tab, text="Dashboard")
        dash.pack(fill="both", expand=True, padx=10, pady=10)
        dash.columnconfigure(0, weight=1)
        dash.columnconfigure(1, weight=1)

        self.sales_canvas = tk.Canvas(dash, height=200, bg="#f8fafc", highlightthickness=1, highlightbackground="#cbd5e1")
        self.sales_canvas.grid(row=0, column=0, sticky="nsew", padx=6, pady=6)

        self.stock_canvas = tk.Canvas(dash, height=200, bg="#f8fafc", highlightthickness=1, highlightbackground="#cbd5e1")
        self.stock_canvas.grid(row=0, column=1, sticky="nsew", padx=6, pady=6)

        self.profit_canvas = tk.Canvas(dash, height=200, bg="#f8fafc", highlightthickness=1, highlightbackground="#cbd5e1")
        self.profit_canvas.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=6, pady=6)

    def refresh(self):
        self._draw_monthly_sales()
        self._draw_critical_stock()
        self._draw_cumulative_profit()

    def _draw_monthly_sales(self):
        data = self.app.reporting.monthly_sales_totals(6)
        self._draw_bar_chart(self.sales_canvas, "Ventas mensuales (USD)", data, color="#2563eb")

    def _draw_critical_stock(self):
        rows = self.app.inventory.top_critical_stock(8)
        data = [(sku, max(min_s - stock, 0)) for sku, stock, min_s in rows]
        self._draw_bar_chart(self.stock_canvas, "Stock crítico (faltante vs mínimo)", data, color="#d64545")

    def _draw_cumulative_profit(self):
        data = self.app.reporting.cumulative_profit_series()
        self._draw_line_chart(self.profit_canvas, "Profit acumulado", data)

    def _draw_bar_chart(self, canvas: tk.Canvas, title: str, data: list[tuple[str, float]], color: str = "#2b78c2"):
        canvas.delete("all")
        w, h = int(canvas.winfo_width() or 560), int(canvas.winfo_height() or 200)
        canvas.create_text(12, 16, text=title, anchor="w", font=("Segoe UI", 10, "bold"), fill="#0f172a")
        if not data:
            canvas.create_text(w // 2, h // 2, text="Sin datos", fill="#64748b")
            return
        maxv = max(v for _, v in data) or 1
        bw = max(24, (w - 40) // len(data))
        for i, (label, val) in enumerate(data):
            x0 = 24 + i * bw
            x1 = x0 + bw - 8
            y1 = h - 30
            y0 = y1 - int((val / maxv) * (h - 70))
            canvas.create_rectangle(x0, y0, x1, y1, fill=color, outline="")
            canvas.create_text((x0 + x1) // 2, y1 + 12, text=label[-5:], font=("Segoe UI", 8), fill="#475569")
            canvas.create_text((x0 + x1) // 2, y0 - 8, text=f"{val:.0f}", font=("Segoe UI", 8), fill="#0f172a")

    def _draw_line_chart(self, canvas: tk.Canvas, title: str, data: list[tuple[str, float]]):
        canvas.delete("all")
        w, h = int(canvas.winfo_width() or 1100), int(canvas.winfo_height() or 200)
        canvas.create_text(12, 16, text=title, anchor="w", font=("Segoe UI", 10, "bold"), fill="#0f172a")
        if not data:
            canvas.create_text(w // 2, h // 2, text="Sin datos", fill="#64748b")
            return
        vals = [v for _, v in data]
        minv, maxv = min(vals), max(vals)
        span = (maxv - minv) or 1
        points = []
        for i, (d, v) in enumerate(data):
            x = 40 + int(i * (w - 80) / max(len(data) - 1, 1))
            y = h - 30 - int((v - minv) * (h - 70) / span)
            points.extend([x, y])
            if i % max(len(data)//6, 1) == 0:
                canvas.create_text(x, h - 14, text=d[5:], font=("Segoe UI", 8), fill="#475569")
        canvas.create_line(*points, fill="#16a34a", width=3, smooth=True)

    def import_excel(self):
        path = filedialog.askopenfilename(title="Select Excel file", filetypes=[("Excel files", "*.xlsx")])
        if not path:
            return
        try:
            ok, skipped = self.app.excel.import_restock_excel(path)
            self.app.toast(f"Excel import: {ok} ok, {skipped} skipped.", kind="success")
            self.app.refresh_all(silent_fx=True)
        except Exception as e:
            self.app.handle_error("Import error", e, "Excel import failed.")

    def export_report(self):
        today = datetime.now().replace(microsecond=0)
        start = today - timedelta(days=7 if self.period.get() == "weekly" else 30)
        start_iso = start.isoformat(sep=" ")
        end_iso = today.isoformat(sep=" ")

        path = filedialog.asksaveasfilename(
            title="Save report as",
            defaultextension=".xlsx",
            filetypes=[("Excel files", "*.xlsx")],
            initialfile=f"report_{self.period.get()}_{date.today().isoformat()}.xlsx",
        )
        if not path:
            return
        try:
            self.app.reporting.export_sales_report_excel(path, start_iso, end_iso)
            self.app.toast("Excel report exported.", kind="success")
        except Exception as e:
            self.app.handle_error("Export error", e, "Excel export failed.")
