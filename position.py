# position.py
"""Position tracking: load from Excel, calculate captured basis returns."""

import logging
from datetime import date
from pathlib import Path

import openpyxl

logger = logging.getLogger(__name__)


def load_positions(filepath: str) -> list[dict]:
    """Load positions from Excel file.

    Expected columns (Chinese):
        合约, 买入日期, 买入价格, 买入时基准价, 是否已卖出, 吃到贴水

    Returns list of position dicts. Returns empty list if file missing or empty.
    Each dict includes row_index matching the actual Excel row number (1-based).
    """
    if not Path(filepath).exists():
        return []

    wb = openpyxl.load_workbook(filepath, data_only=True)
    ws = wb.active

    rows = list(ws.iter_rows(min_row=2, values_only=True))
    if not rows:
        wb.close()
        return []

    positions = []
    for idx, row in enumerate(rows):
        excel_row = idx + 2  # 1-indexed; row 1 is header, first data row is 2
        contract, buy_date_str, buy_price, base_price, sold_str, captured = row
        if not contract or not buy_date_str or not buy_price:
            continue

        buy_date = (
            buy_date_str
            if isinstance(buy_date_str, date)
            else date.fromisoformat(str(buy_date_str))
        )

        positions.append({
            "row_index": excel_row,
            "contract": str(contract).strip().upper(),
            "buy_date": buy_date,
            "buy_price": float(buy_price),
            "base_price_at_buy": float(base_price) if base_price else 0.0,
            "sold": str(sold_str).strip().upper() == "Y",
            "captured_basis": float(captured) if captured is not None else None,
        })

    wb.close()
    return positions


def save_captured_basis(filepath: str, row_index: int, value: float) -> None:
    """Write captured_basis value back to Excel for a sold position.

    row_index is the 1-based Excel row number (matching the row_index
    in position dicts). Column 6 is the "吃到贴水" column.
    """
    if not Path(filepath).exists():
        return
    wb = openpyxl.load_workbook(filepath)
    ws = wb.active
    ws.cell(row=row_index, column=6, value=value)
    wb.save(filepath)
    wb.close()
