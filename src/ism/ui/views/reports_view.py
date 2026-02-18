from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
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
        ttk.Radiobutton(row, text="Weekly (last 7 days)", value="weekly", variable=self.period)\
            .pack(side="left", padx=10)
        ttk.Radiobutton(row, text="Monthly (last 30 days)", value="monthly", variable=self.period)\
            .pack(side="left", padx=10)

        ttk.Button(box2, text="Export report", style="Big.TButton", command=self.export_report)\
            .pack(anchor="w", padx=10, pady=(0, 10))

        box3 = ttk.LabelFrame(tab, text="Quick notes")
        box3.pack(fill="x", padx=10, pady=10)
        ttk.Label(
            box3,
            text="Excel import adds stock (restock delta). It does NOT overwrite stock.\n"
                 "All restocks are recorded as Purchases so history stays consistent.",
            wraplength=1100
        ).pack(anchor="w", padx=10, pady=10)

    def import_excel(self):
        path = filedialog.askopenfilename(title="Select Excel file", filetypes=[("Excel files", "*.xlsx")])
        if not path:
            return
        try:
            ok, skipped = self.app.excel.import_restock_excel(path)
            messagebox.showinfo("Import done", f"Imported/updated: {ok}\nSkipped: {skipped}")
            self.app.toast(f"Excel import: {ok} ok, {skipped} skipped.", kind="success")
            self.app.refresh_all(silent_fx=True)
        except Exception as e:
            messagebox.showerror("Import error", str(e))
            self.app.toast("Excel import failed.", kind="error")

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
            self.app.reporting.export_sales_report_excel(path, start_iso, end_iso)
            messagebox.showinfo("Export done", f"Report saved:\n{path}")
            self.app.toast("Excel report exported.", kind="success")
        except Exception as e:
            messagebox.showerror("Export error", str(e))
            self.app.toast("Excel export failed.", kind="error")
