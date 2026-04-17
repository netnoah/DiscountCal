# Position Basis Tracker Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add position tracking that calculates captured basis for futures holdings, displayed on the main page and in daily WeChat notifications.

**Architecture:** New `position.py` module reads positions from Excel (`data/positions.xlsx`), calculates metrics against live futures prices, and returns results. `app.py` renders a table at the bottom; `notify.py` appends a summary to the webhook message.

**Tech Stack:** Python, openpyxl (new dependency), Streamlit, existing data_fetcher/calculator modules.

**Spec:** `docs/superpowers/specs/2026-04-17-position-basis-tracker-design.md`

---

## File Structure

| Action | File | Responsibility |
|--------|------|----------------|
| Create | `position.py` | Load positions from Excel, calculate returns, save captured_basis for sold positions |
| Create | `tests/test_position.py` | Tests for position.py |
| Modify | `requirements.txt` | Add `openpyxl>=3.1.0` |
| Modify | `app.py` | Import position module, refactor data fetch, render position table, handle sold write-back |
| Modify | `notify.py` | Import position module, append position summary to message, handle sold write-back |

---

### Task 1: Add openpyxl dependency

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: Add openpyxl to requirements.txt**

Add `openpyxl>=3.1.0` to `requirements.txt`:

```
streamlit>=1.30.0
akshare>=1.14.0
pandas>=2.0.0
plotly>=5.18.0
pytest>=8.0.0
openpyxl>=3.1.0
```

- [ ] **Step 2: Install dependency**

Run: `pip install openpyxl>=3.1.0`
Expected: Successfully installed

- [ ] **Step 3: Commit**

```bash
git add requirements.txt
git commit -m "chore: add openpyxl dependency"
```

---

### Task 2: Create position.py — load_positions + save_captured_basis

**Files:**
- Create: `position.py`
- Create: `tests/test_position.py`

- [ ] **Step 1: Write failing tests for load_positions and save_captured_basis**

Create `tests/test_position.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_position.py -v`
Expected: FAIL (module `position` not found)

- [ ] **Step 3: Implement load_positions and save_captured_basis**

Create `position.py`:

```python
# position.py
"""Position tracking: load from Excel, calculate captured basis returns."""

import logging
from datetime import date
from pathlib import Path

import openpyxl

logger = logging.getLogger(__name__)


def load_positions(filepath: str) -> list[dict]:
    """Load positions from Excel file.

    Expected columns (Chinese): 合约, 买入日期, 买入价格, 买入时基准价, 是否已卖出, 吃到贴水
    Returns list of position dicts. Returns empty list if file missing or empty.
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

    row_index is the 1-based Excel row number (matching the row_index in position dicts).
    """
    if not Path(filepath).exists():
        return
    wb = openpyxl.load_workbook(filepath)
    ws = wb.active
    ws.cell(row=row_index, column=6, value=value)
    wb.save(filepath)
    wb.close()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_position.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add position.py tests/test_position.py
git commit -m "feat: add load_positions and save_captured_basis"
```

---

### Task 3: Create position.py — calculate_position_return

**Files:**
- Modify: `position.py`
- Modify: `tests/test_position.py`

- [ ] **Step 1: Write failing tests for calculate_position_return**

Add to `tests/test_position.py`:

```python
from position import calculate_position_return


class TestCalculatePositionReturn:
    def _make_position(self, **overrides):
        defaults = {
            "row_index": 2,
            "contract": "I2609",
            "buy_date": date(2026, 4, 10),
            "buy_price": 650.0,
            "base_price_at_buy": 720.0,
            "sold": False,
            "captured_basis": None,
        }
        defaults.update(overrides)
        return defaults

    def test_calculates_all_metrics(self):
        pos = self._make_position()
        result = calculate_position_return(
            position=pos,
            current_futures_price=665.0,
            current_base_price=730.0,
            reference_date=date(2026, 4, 25),
        )
        assert result["contract"] == "I2609"
        assert result["buy_price"] == 650.0
        assert result["current_price"] == 665.0
        # 初始贴水 = 720 - 650 = 70
        assert result["initial_basis"] == 70.0
        # 当前贴水 = 730 - 665 = 65
        assert result["current_basis"] == 65.0
        # 已吃贴水 = 70 - 65 = 5
        assert result["captured_basis"] == 5.0
        # 收敛比 = 5 / 70 * 100 = 7.14%
        assert abs(result["convergence_pct"] - (5 / 70 * 100)) < 0.01
        # 持有天数 = 15
        assert result["holding_days"] == 15
        # 贴水年化 = 5 / 650 * 365 / 15 * 100
        expected_annualized = 5 / 650 * 365 / 15 * 100
        assert abs(result["annualized_return"] - expected_annualized) < 0.01
        # 合约浮盈 = 665 - 650 = 15
        assert result["pnl"] == 15.0

    def test_zero_holding_days_returns_none_annualized(self):
        pos = self._make_position(buy_date=date(2026, 4, 25))
        result = calculate_position_return(
            position=pos,
            current_futures_price=665.0,
            current_base_price=730.0,
            reference_date=date(2026, 4, 25),
        )
        assert result["annualized_return"] is None
        assert result["holding_days"] == 0

    def test_zero_initial_basis_returns_none_convergence(self):
        pos = self._make_position(buy_price=720.0, base_price_at_buy=720.0)
        result = calculate_position_return(
            position=pos,
            current_futures_price=720.0,
            current_base_price=720.0,
            reference_date=date(2026, 4, 25),
        )
        assert result["convergence_pct"] is None

    def test_negative_basis_still_calculates(self):
        """Futures > base price means negative basis (升水)."""
        pos = self._make_position(buy_price=750.0, base_price_at_buy=720.0)
        result = calculate_position_return(
            position=pos,
            current_futures_price=740.0,
            current_base_price=730.0,
            reference_date=date(2026, 4, 25),
        )
        # 初始贴水 = 720 - 750 = -30
        assert result["initial_basis"] == -30.0
        # 当前贴水 = 730 - 740 = -10
        assert result["current_basis"] == -10.0
        # 已吃贴水 = -30 - (-10) = -20
        assert result["captured_basis"] == -20.0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_position.py::TestCalculatePositionReturn -v`
Expected: FAIL (ImportError or AttributeError)

- [ ] **Step 3: Implement calculate_position_return**

Add to `position.py`:

```python
def calculate_position_return(
    position: dict,
    current_futures_price: float,
    current_base_price: float,
    reference_date: date | None = None,
) -> dict:
    """Calculate captured basis metrics for a single position.

    Args:
        position: position dict from load_positions()
        current_futures_price: live price for this contract
        current_base_price: current near-contract base price
        reference_date: date to use for holding days calc (default: today)

    Returns dict with all metrics.
    """
    if reference_date is None:
        reference_date = date.today()

    buy_price = position["buy_price"]
    base_at_buy = position["base_price_at_buy"]
    buy_date = position["buy_date"]

    initial_basis = base_at_buy - buy_price
    current_basis = current_base_price - current_futures_price
    captured = initial_basis - current_basis

    holding_days = (reference_date - buy_date).days

    if holding_days > 0:
        annualized_return = captured / buy_price * 365 / holding_days * 100
    else:
        annualized_return = None

    if initial_basis != 0:
        convergence_pct = captured / initial_basis * 100
    else:
        convergence_pct = None

    return {
        "contract": position["contract"],
        "buy_price": buy_price,
        "current_price": current_futures_price,
        "initial_basis": round(initial_basis, 2),
        "current_basis": round(current_basis, 2),
        "captured_basis": round(captured, 2),
        "convergence_pct": round(convergence_pct, 2) if convergence_pct is not None else None,
        "holding_days": holding_days,
        "annualized_return": round(annualized_return, 2) if annualized_return is not None else None,
        "pnl": round(current_futures_price - buy_price, 2),
        "sold": position["sold"],
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_position.py::TestCalculatePositionReturn -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add position.py tests/test_position.py
git commit -m "feat: add calculate_position_return"
```

---

### Task 4: Create position.py — build_position_summary

**Files:**
- Modify: `position.py`
- Modify: `tests/test_position.py`

- [ ] **Step 1: Write failing tests for build_position_summary**

Add to `tests/test_position.py`:

```python
from position import build_position_summary


class TestBuildPositionSummary:
    def test_formats_text_for_wechat(self):
        returns = [
            {
                "contract": "I2609",
                "buy_price": 650.0,
                "current_price": 665.0,
                "captured_basis": 5.0,
                "convergence_pct": 7.14,
                "annualized_return": 18.72,
                "pnl": 15.0,
                "sold": False,
            },
            {
                "contract": "I2612",
                "buy_price": 620.0,
                "current_price": 635.0,
                "captured_basis": 10.0,
                "convergence_pct": 66.67,
                "annualized_return": 98.17,
                "pnl": 15.0,
                "sold": False,
            },
        ]
        result = build_position_summary(returns, total_count=3)
        assert "I2609" in result
        assert "I2612" in result
        assert "650.0" in result
        assert "持仓数: 3" in result
        assert "未平仓: 2" in result

    def test_empty_returns_empty_string(self):
        result = build_position_summary([], total_count=0)
        assert result == ""

    def test_hides_sold_positions_in_detail(self):
        returns = [
            {
                "contract": "I2609",
                "buy_price": 650.0,
                "current_price": 665.0,
                "captured_basis": 5.0,
                "convergence_pct": 7.14,
                "annualized_return": 18.72,
                "pnl": 15.0,
                "sold": False,
            },
            {
                "contract": "I2605",
                "buy_price": 680.0,
                "current_price": 700.0,
                "captured_basis": 20.0,
                "convergence_pct": 100.0,
                "annualized_return": 50.0,
                "pnl": 20.0,
                "sold": True,
            },
        ]
        result = build_position_summary(returns, total_count=2)
        assert "I2609" in result
        assert "I2605" not in result
        assert "持仓数: 2" in result
        assert "未平仓: 1" in result
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_position.py::TestBuildPositionSummary -v`
Expected: FAIL

- [ ] **Step 3: Implement build_position_summary**

Add to `position.py`:

```python
def build_position_summary(
    position_returns: list[dict], total_count: int
) -> str:
    """Format position returns as WeChat notification text.

    Args:
        position_returns: list of calculated return dicts (may include sold)
        total_count: total number of positions (sold + unsold) for the summary line

    Returns empty string if no positions.
    """
    if not position_returns:
        return ""

    lines = [
        "",
        "📊 我的持仓收益",
        "────────────",
    ]

    unsold_count = 0
    for r in position_returns:
        if r.get("sold"):
            continue
        unsold_count += 1
        lines.append(f"🔹 {r['contract']} | 买入 {r['buy_price']:.1f}")

        captured = r["captured_basis"]
        captured_str = f"{captured:.1f}" if captured is not None else "N/A"
        lines.append(f"  当前价: {r['current_price']:.1f} | 已吃贴水: {captured_str}")

        conv = r["convergence_pct"]
        conv_str = f"{conv:.1f}%" if conv is not None else "N/A"
        annual = r["annualized_return"]
        annual_str = f"{annual:.1f}%" if annual is not None else "N/A"
        pnl = r["pnl"]
        pnl_str = f"{pnl:.1f}" if pnl is not None else "N/A"
        lines.append(f"  收敛: {conv_str} | 年化: {annual_str} | 浮盈: {pnl_str}")

    lines.append("────────────")
    lines.append(f"📌 持仓数: {total_count} | 未平仓: {unsold_count}")

    return "\n".join(lines)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_position.py::TestBuildPositionSummary -v`
Expected: all PASS

- [ ] **Step 5: Run all tests**

Run: `pytest tests/ -v`
Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git add position.py tests/test_position.py
git commit -m "feat: add build_position_summary for WeChat notification"
```

---

### Task 5: Refactor app.py — extract get_realtime_data

**Files:**
- Modify: `app.py`

This task refactors the existing `get_realtime_basis_table` to also return `futures_df`, so the position table can reuse the same data without a second API call. The old function is removed.

- [ ] **Step 1: Write failing test**

Add to `tests/test_position.py`:

```python
class TestComputePositionReturns:
    """Integration test for computing position returns from positions + futures data."""

    def test_filters_unsold_and_matches_prices(self, tmp_path):
        """compute_position_returns should skip sold positions and match contract prices."""
        from position import compute_position_returns

        positions = [
            {"row_index": 2, "contract": "I2609", "buy_date": date(2026, 4, 10),
             "buy_price": 650.0, "base_price_at_buy": 720.0, "sold": False, "captured_basis": None},
            {"row_index": 3, "contract": "I2605", "buy_date": date(2026, 3, 15),
             "buy_price": 680.0, "base_price_at_buy": 710.0, "sold": True, "captured_basis": None},
            {"row_index": 4, "contract": "I2612", "buy_date": date(2026, 4, 12),
             "buy_price": 630.0, "base_price_at_buy": 720.0, "sold": False, "captured_basis": None},
        ]
        price_map = {"I2609": 665.0, "I2612": 635.0, "I2605": 700.0}
        near_price = 730.0

        returns = compute_position_returns(positions, price_map, near_price)
        # Only unsold positions with matching prices
        assert len(returns) == 2
        assert all(not r["sold"] for r in returns)
        assert returns[0]["contract"] == "I2609"
        assert returns[1]["contract"] == "I2612"

    def test_skips_positions_with_no_matching_price(self):
        from position import compute_position_returns

        positions = [
            {"row_index": 2, "contract": "I2701", "buy_date": date(2026, 4, 10),
             "buy_price": 600.0, "base_price_at_buy": 700.0, "sold": False, "captured_basis": None},
        ]
        price_map = {"I2609": 665.0}  # I2701 not in price_map
        near_price = 730.0

        returns = compute_position_returns(positions, price_map, near_price)
        assert len(returns) == 0

    def test_handles_sold_writeback(self, tmp_path):
        """compute_position_returns should return sold positions needing write-back."""
        from position import compute_position_returns

        positions = [
            {"row_index": 2, "contract": "I2605", "buy_date": date(2026, 3, 15),
             "buy_price": 680.0, "base_price_at_buy": 710.0, "sold": True, "captured_basis": None},
        ]
        price_map = {"I2605": 700.0}
        near_price = 730.0

        returns = compute_position_returns(positions, price_map, near_price)
        # Sold with no captured_basis → still returns result for write-back
        assert len(returns) == 1
        assert returns[0]["sold"] is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_position.py::TestComputePositionReturns -v`
Expected: FAIL (ImportError)

- [ ] **Step 3: Implement compute_position_returns**

Add to `position.py`:

```python
def compute_position_returns(
    positions: list[dict],
    price_map: dict[str, float],
    near_price: float,
) -> list[dict]:
    """Calculate returns for all positions that have a matching price.

    Returns results for:
    - All unsold positions with a price match
    - Sold positions with no captured_basis (for write-back)

    Skips sold positions that already have captured_basis frozen.
    """
    results = []
    for pos in positions:
        # Skip sold positions that already have a frozen value
        if pos["sold"] and pos["captured_basis"] is not None:
            continue

        current_price = price_map.get(pos["contract"])
        if current_price is None:
            continue

        result = calculate_position_return(
            position=pos,
            current_futures_price=float(current_price),
            current_base_price=near_price,
        )
        results.append(result)
    return results
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_position.py::TestComputePositionReturns -v`
Expected: all PASS

- [ ] **Step 5: Run all tests**

Run: `pytest tests/ -v`
Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git add position.py tests/test_position.py
git commit -m "feat: add compute_position_returns helper"
```

---

### Task 6: Refactor app.py — replace get_realtime_basis_table

**Files:**
- Modify: `app.py`

This step removes `get_realtime_basis_table` and replaces it with `get_realtime_data` that returns both `futures_df` and `near_price`, avoiding a second API fetch for position tracking.

- [ ] **Step 1: Replace get_realtime_basis_table with get_realtime_data**

In `app.py`, replace the `get_realtime_basis_table` function (lines 94-112) with:

```python
def get_realtime_data() -> tuple[pd.DataFrame, float | None]:
    """Fetch real-time futures data. Returns (futures_df, near_price)."""
    contracts = fetch_active_contracts()
    if not contracts:
        return pd.DataFrame(), None

    futures_df = fetch_futures_quotes(contracts)
    if futures_df.empty:
        return futures_df, None

    near_price = _find_near_contract_price(futures_df)
    return futures_df, near_price
```

- [ ] **Step 2: Update main() to use get_realtime_data**

Replace the line in `main()`:

```python
    basis_table = get_realtime_basis_table() if near_price else pd.DataFrame()
```

With:

```python
    # Fetch real-time data (single fetch for basis table + position table)
    futures_df, realtime_near_price = get_realtime_data()
    if realtime_near_price is not None:
        near_price = realtime_near_price

    basis_table = calculate_basis_table(
        futures_df=futures_df,
        spot_price=near_price,
        reference_date=date.today(),
    ) if near_price else pd.DataFrame()
```

Note: `calculate_basis_table` is already imported at line 10.

- [ ] **Step 3: Run all tests**

Run: `pytest tests/ -v`
Expected: all PASS

- [ ] **Step 4: Commit**

```bash
git add app.py
git commit -m "refactor: replace get_realtime_basis_table with get_realtime_data"
```

---

### Task 7: Integrate position table into app.py

**Files:**
- Modify: `app.py`

- [ ] **Step 1: Add imports and constant**

In `app.py`, update the import block (after line 14) to add:

```python
from position import load_positions, calculate_position_return, compute_position_returns, save_captured_basis
```

Add a constant near the top (after `DEFAULT_REFRESH_SECONDS`):

```python
POSITIONS_FILE = "data/positions.xlsx"
```

- [ ] **Step 2: Add render_position_table function**

Add to `app.py` before `main()`:

```python
def render_position_table(futures_df: pd.DataFrame, near_price: float) -> None:
    """Render the position tracking table at the bottom of the page."""
    positions = load_positions(POSITIONS_FILE)
    if not positions:
        return

    # Build a price lookup from futures data
    price_map = {}
    if not futures_df.empty:
        for _, row in futures_df.iterrows():
            price_map[row["symbol"]] = row["current_price"]

    # Handle sold positions: calculate and freeze captured_basis
    for pos in positions:
        if not pos["sold"] or pos["captured_basis"] is not None:
            continue
        current_price = price_map.get(pos["contract"])
        if current_price is None:
            continue
        result = calculate_position_return(
            position=pos,
            current_futures_price=float(current_price),
            current_base_price=near_price,
        )
        save_captured_basis(POSITIONS_FILE, pos["row_index"], result["captured_basis"])
        logger.info(
            "Froze captured_basis for sold position %s: %s",
            pos["contract"], result["captured_basis"],
        )

    # Compute and display unsold position returns
    returns = compute_position_returns(positions, price_map, near_price)
    unsold_returns = [r for r in returns if not r["sold"]]
    if not unsold_returns:
        return

    st.subheader("我的持仓收益")
    display_df = pd.DataFrame(unsold_returns)
    display_df = display_df[[
        "contract", "buy_price", "current_price",
        "initial_basis", "current_basis", "captured_basis",
        "convergence_pct", "annualized_return", "pnl",
    ]]
    display_df = display_df.rename(columns={
        "contract": "合约",
        "buy_price": "买入价",
        "current_price": "当前价",
        "initial_basis": "初始贴水",
        "current_basis": "当前贴水",
        "captured_basis": "已吃贴水",
        "convergence_pct": "收敛比例",
        "annualized_return": "贴水年化",
        "pnl": "合约浮盈",
    })

    for col in ["买入价", "当前价", "初始贴水", "当前贴水", "已吃贴水", "合约浮盈"]:
        display_df[col] = display_df[col].apply(
            lambda x: f"{x:.1f}" if pd.notna(x) else "N/A"
        )
    display_df["收敛比例"] = display_df["收敛比例"].apply(
        lambda x: f"{x:.1f}%" if pd.notna(x) else "N/A"
    )
    display_df["贴水年化"] = display_df["贴水年化"].apply(
        lambda x: f"{x:.2f}%" if pd.notna(x) else "N/A"
    )

    st.dataframe(display_df, use_container_width=True, hide_index=True)
```

- [ ] **Step 3: Call render_position_table in main()**

In `app.py` `main()`, after `render_trend_chart(storage)` and before the auto-refresh block, add:

```python
    # Position tracking
    if near_price is not None and not futures_df.empty:
        render_position_table(futures_df, near_price)
```

- [ ] **Step 4: Run all tests**

Run: `pytest tests/ -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add app.py
git commit -m "feat: integrate position tracking table into main page"
```

---

### Task 8: Integrate position summary into notify.py

**Files:**
- Modify: `notify.py`

- [ ] **Step 1: Add imports and constant**

In `notify.py`, add after the existing imports (line 13):

```python
from position import load_positions, calculate_position_return, compute_position_returns, build_position_summary, save_captured_basis
```

Add a constant near the top (after `WEBHOOK_URL`):

```python
POSITIONS_FILE = "data/positions.xlsx"
```

- [ ] **Step 2: Update build_text_message**

Replace the `build_text_message` function in `notify.py`:

```python
def build_text_message() -> str | None:
    """Fetch data and build WeChat text message (compatible with personal WeChat)."""
    contracts = fetch_active_contracts()
    if not contracts:
        return None

    futures_df = fetch_futures_quotes(contracts)
    if futures_df.empty:
        return None

    near_price = _find_near_contract_price(futures_df)
    if near_price is None:
        return None

    basis_table = calculate_basis_table(
        futures_df=futures_df,
        spot_price=near_price,
        reference_date=date.today(),
    )

    if basis_table.empty:
        return None

    today_str = date.today().strftime("%m-%d")

    lines = [
        f"【铁矿石贴水日报{today_str}】",
        f"基准价 {near_price:.1f}元/吨",
        "",
    ]

    for _, row in basis_table.iterrows():
        contract = row["contract"]
        fp = row["futures_price"]
        days = int(row["days_to_delivery"])
        rate = row["annualized_basis_rate"]
        rate_str = f"{rate:.2f}%" if pd.notna(rate) else "N/A"
        lines.append(f"{contract} {fp:.1f} 贴水{rate_str} {days}天")

    # Position tracking summary
    positions = load_positions(POSITIONS_FILE)
    if positions:
        price_map = {
            row["symbol"]: float(row["current_price"])
            for _, row in futures_df.iterrows()
        }

        # Handle sold positions: freeze captured_basis
        for pos in positions:
            if not pos["sold"] or pos["captured_basis"] is not None:
                continue
            current_price = price_map.get(pos["contract"])
            if current_price is None:
                continue
            result = calculate_position_return(
                position=pos,
                current_futures_price=current_price,
                current_base_price=near_price,
            )
            save_captured_basis(POSITIONS_FILE, pos["row_index"], result["captured_basis"])

        # Build summary from all positions (including sold for total count)
        returns = compute_position_returns(positions, price_map, near_price)
        summary = build_position_summary(returns, total_count=len(positions))
        lines.append(summary)

    return "\n".join(lines)
```

- [ ] **Step 3: Run all tests**

Run: `pytest tests/ -v`
Expected: all PASS

- [ ] **Step 4: Commit**

```bash
git add notify.py
git commit -m "feat: add position summary to WeChat notification"
```

---

### Task 9: Final verification

- [ ] **Step 1: Run full test suite**

Run: `pytest tests/ -v`
Expected: all PASS

- [ ] **Step 2: Verify app starts**

Run: `streamlit run app.py`
Expected: app opens in browser, no errors. Position section shows only if `data/positions.xlsx` exists with unsold position data.

- [ ] **Step 3: Verify notify.py works**

Run: `python -c "from notify import build_text_message; msg = build_text_message(); print(msg)"`
Expected: message printed with basis data, position section included if Excel file has positions.
