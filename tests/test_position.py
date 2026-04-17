# tests/test_position.py
import pytest
from datetime import date
from pathlib import Path

import openpyxl

from position import load_positions, save_captured_basis


class TestLoadPositions:
    def _create_test_excel(self, tmp_path, rows):
        """Helper to create a test positions.xlsx with given rows."""
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(["合约", "买入日期", "买入价格", "买入时基准价", "是否已卖出", "吃到贴水"])
        for row in rows:
            ws.append(row)
        filepath = tmp_path / "positions.xlsx"
        wb.save(filepath)
        return str(filepath)

    def test_loads_unsold_position(self, tmp_path):
        filepath = self._create_test_excel(tmp_path, [
            ["I2609", "2026-04-10", 650.0, 720.0, "N", None],
        ])
        positions = load_positions(filepath)
        assert len(positions) == 1
        pos = positions[0]
        assert pos["contract"] == "I2609"
        assert pos["buy_date"] == date(2026, 4, 10)
        assert pos["buy_price"] == 650.0
        assert pos["base_price_at_buy"] == 720.0
        assert pos["sold"] is False
        assert pos["captured_basis"] is None
        # row_index must match actual Excel row (row 2 = first data row)
        assert pos["row_index"] == 2

    def test_loads_sold_position_with_captured_basis(self, tmp_path):
        filepath = self._create_test_excel(tmp_path, [
            ["I2605", "2026-03-15", 680.0, 710.0, "Y", 25.0],
        ])
        positions = load_positions(filepath)
        assert len(positions) == 1
        assert positions[0]["sold"] is True
        assert positions[0]["captured_basis"] == 25.0

    def test_loads_multiple_positions(self, tmp_path):
        filepath = self._create_test_excel(tmp_path, [
            ["I2609", "2026-04-10", 650.0, 720.0, "N", None],
            ["I2612", "2026-04-12", 630.0, 720.0, "N", None],
        ])
        positions = load_positions(filepath)
        assert len(positions) == 2
        assert positions[0]["row_index"] == 2
        assert positions[1]["row_index"] == 3

    def test_returns_empty_list_when_file_missing(self, tmp_path):
        filepath = str(tmp_path / "nonexistent.xlsx")
        positions = load_positions(filepath)
        assert positions == []

    def test_returns_empty_list_when_file_empty(self, tmp_path):
        filepath = self._create_test_excel(tmp_path, [])
        positions = load_positions(filepath)
        assert positions == []

    def test_skips_rows_with_missing_fields(self, tmp_path):
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(["合约", "买入日期", "买入价格", "买入时基准价", "是否已卖出", "吃到贴水"])
        ws.append(["I2609", "2026-04-10", 650.0, 720.0, "N", None])
        ws.append(["", "", "", "", "", ""])  # empty row — should be skipped
        ws.append(["I2612", "2026-04-12", 630.0, 720.0, "N", None])
        filepath = tmp_path / "positions.xlsx"
        wb.save(filepath)
        positions = load_positions(str(filepath))
        assert len(positions) == 2
        # First valid row is Excel row 2
        assert positions[0]["row_index"] == 2
        # Second valid row is Excel row 4 (row 3 was empty/skipped)
        assert positions[1]["row_index"] == 4


class TestSaveCapturedBasis:
    def _create_test_excel(self, tmp_path, rows):
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(["合约", "买入日期", "买入价格", "买入时基准价", "是否已卖出", "吃到贴水"])
        for row in rows:
            ws.append(row)
        filepath = tmp_path / "positions.xlsx"
        wb.save(filepath)
        return str(filepath)

    def test_writes_value_to_correct_cell(self, tmp_path):
        filepath = self._create_test_excel(tmp_path, [
            ["I2609", "2026-04-10", 650.0, 720.0, "N", None],
            ["I2605", "2026-03-15", 680.0, 710.0, "Y", None],
        ])
        save_captured_basis(filepath, row_index=3, value=25.0)

        # Verify written value
        positions = load_positions(filepath)
        sold_pos = [p for p in positions if p["sold"]][0]
        assert sold_pos["captured_basis"] == 25.0

    def test_does_not_crash_on_missing_file(self, tmp_path):
        filepath = str(tmp_path / "nonexistent.xlsx")
        # Should not raise
        save_captured_basis(filepath, row_index=2, value=10.0)

    def test_overwrites_existing_value(self, tmp_path):
        filepath = self._create_test_excel(tmp_path, [
            ["I2605", "2026-03-15", 680.0, 710.0, "Y", 15.0],
        ])
        save_captured_basis(filepath, row_index=2, value=25.0)

        positions = load_positions(filepath)
        assert positions[0]["captured_basis"] == 25.0
