from collections import defaultdict
from datetime import datetime
from openpyxl import Workbook, load_workbook
from openpyxl.utils import get_column_letter
from openpyxl.styles import Font, Alignment
from openpyxl.worksheet.table import Table, TableStyleInfo

from db import (
    upsert_product,
    sales_summary_between,
    list_sales_between,
    sale_items_for_sale
)


# ---------------- IMPORT PRODUCTS ----------------

def import_products_from_excel(path: str) -> tuple[int, int]:
    """
    Headers required:
    sku | name | cost_usd | price_usd | stock | min_stock
    """

    wb = load_workbook(path)
    ws = wb.active

    headers = {}
    for col in range(1, ws.max_column + 1):
        val = ws.cell(row=1, column=col).value
        if isinstance(val, str):
            headers[val.strip().lower()] = col

    required = ["sku", "name", "cost_usd", "price_usd", "stock", "min_stock"]

    for r in required:
        if r not in headers:
            raise ValueError(f"Missing column header: {r}")

    ok = 0
    skipped = 0

    for row in range(2, ws.max_row + 1):
        try:
            sku = ws.cell(row=row, column=headers["sku"]).value
            name = ws.cell(row=row, column=headers["name"]).value
            cost = ws.cell(row=row, column=headers["cost_usd"]).value
            price = ws.cell(row=row, column=headers["price_usd"]).value
            stock = ws.cell(row=row, column=headers["stock"]).value
            min_stock = ws.cell(row=row, column=headers["min_stock"]).value

            if not sku or not name:
                skipped += 1
                continue

            upsert_product(
                str(sku).strip(),
                str(name).strip(),
                float(cost),
                float(price),
                int(stock),
                int(min_stock)
            )

            ok += 1
        except Exception:
            skipped += 1

    return ok, skipped


# ---------------- EXPORT REPORT ----------------

def export_sales_report_excel(path: str, start_iso: str, end_iso: str) -> None:
    wb = Workbook()

    def money_fmt(cell):
        cell.number_format = '#,##0.00'

    def pct_fmt(cell):
        cell.number_format = '0.00%'

    def bold_row(ws, row):
        for c in ws[row]:
            c.font = Font(bold=True)

    def make_table(ws, name, start_row, start_col, end_row, end_col):
        ref = f"{get_column_letter(start_col)}{start_row}:{get_column_letter(end_col)}{end_row}"
        tab = Table(displayName=name, ref=ref)
        tab.tableStyleInfo = TableStyleInfo(
            name="TableStyleMedium9",
            showRowStripes=True
        )
        ws.add_table(tab)

    totals, _ = sales_summary_between(start_iso, end_iso)
    sales_count, total_usd, total_ars, margin_usd = totals

    sales_rows = list_sales_between(start_iso, end_iso)

    lines = []
    prod_agg = defaultdict(lambda: {"units": 0, "revenue": 0, "cogs": 0, "profit": 0})

    for s in sales_rows:
        sale_id = int(s[0])
        items = sale_items_for_sale(sale_id)

        for it in items:
            sku, name, qty, unit, line_usd, cost, margin = it

            qty = int(qty)
            line_usd = float(line_usd)
            cost = float(cost)
            margin = float(margin)

            lines.append([sale_id, sku, name, qty, unit, cost, line_usd, margin])

            prod_agg[sku]["units"] += qty
            prod_agg[sku]["revenue"] += line_usd
            prod_agg[sku]["cogs"] += qty * cost
            prod_agg[sku]["profit"] += margin

    # ---------------- DASHBOARD ----------------
    ws = wb.active
    ws.title = "Dashboard"

    ws["A1"] = "Sales Report"
    ws["A1"].font = Font(bold=True, size=14)

    ws.append([])
    ws.append(["Sales count", sales_count])
    ws.append(["Revenue USD", total_usd])
    ws.append(["Revenue ARS", total_ars])
    ws.append(["Profit USD", margin_usd])

    # ---------------- PRODUCT PROFIT ----------------
    wp = wb.create_sheet("Product Profit")
    wp.append(["SKU", "Units Sold", "Revenue USD", "COGS USD", "Profit USD", "Margin %"])
    bold_row(wp, 1)

    row = 2
    for sku, agg in prod_agg.items():
        revenue = agg["revenue"]
        profit = agg["profit"]
        margin_pct = profit / revenue if revenue else 0

        wp.append([
            sku,
            agg["units"],
            revenue,
            agg["cogs"],
            profit,
            margin_pct
        ])

        money_fmt(wp[f"C{row}"])
        money_fmt(wp[f"D{row}"])
        money_fmt(wp[f"E{row}"])
        pct_fmt(wp[f"F{row}"])
        row += 1

    make_table(wp, "ProductProfit", 1, 1, wp.max_row, 6)

    # ---------------- SALES ----------------
    ws2 = wb.create_sheet("Sales")
    ws2.append(["Sale ID", "Datetime", "Total USD", "FX", "Total ARS", "Notes"])
    bold_row(ws2, 1)

    for s in sales_rows:
        ws2.append(s)

    make_table(ws2, "Sales", 1, 1, ws2.max_row, 6)

    # ---------------- SALE LINES ----------------
    ws3 = wb.create_sheet("Sale Lines")
    ws3.append(["Sale ID", "SKU", "Name", "Qty", "Unit USD", "Cost USD", "Line USD", "Profit USD"])
    bold_row(ws3, 1)

    for line in lines:
        ws3.append(line)

    make_table(ws3, "SaleLines", 1, 1, ws3.max_row, 8)

    wb.save(path)
