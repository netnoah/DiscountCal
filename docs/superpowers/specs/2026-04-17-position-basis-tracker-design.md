# Position Basis Tracker Design

## Overview

Add a position tracking feature that calculates how much basis (贴水) a user has captured on futures they hold. Data is managed via an Excel file; results are displayed on the main Streamlit page and included in daily WeChat notifications.

## Data Storage

File: `data/positions.xlsx`

| Column (Chinese) | Key | Type | Description |
|------------------|-----|------|-------------|
| 合约 | contract | str | Contract code, e.g. I2609 |
| 买入日期 | buy_date | date | Purchase date |
| 买入价格 | buy_price | float | Futures price at purchase |
| 买入时基准价 | base_price_at_buy | float | Nearest-contract price on purchase date |
| 是否已卖出 | sold | str | Y or N |
| 吃到贴水 | captured_basis | float | Auto-filled. Empty for unsold; frozen value for sold positions |

## Calculation Logic

For each **unsold** position, calculated in real-time:

```
当前基准价 = nearest delivery contract current price (reuse existing logic)
初始贴水 = base_price_at_buy - buy_price
当前贴水 = 当前基准价 - 当前期货价
已吃贴水 = 初始贴水 - 当前贴水
贴水收敛比 = 已吃贴水 / 初始贴水 * 100%
持有天数 = today - buy_date
贴水年化收益 = 已吃贴水 / buy_price * 365 / 持有天数 * 100%
合约浮盈 = 当前期货价 - buy_price
```

For **sold** positions:
- If `captured_basis` is empty: calculate one last time, write back to Excel, freeze
- If `captured_basis` has a value: skip calculation
- Sold positions are **hidden** from the UI

## New Module

**`position.py`** — reads Excel, calculates position returns.

Functions:
- `load_positions(filepath)` — read positions.xlsx, return list of position dicts
- `calculate_position_return(position, current_futures_price, current_base_price)` — compute all metrics for one position
- `save_captured_basis(filepath, row_index, value)` — write captured_basis back to Excel for sold positions

## UI Integration

Add a **"我的持仓收益"** section at the bottom of `app.py` main page.

Display table (Chinese headers):

| 合约 | 买入价 | 当前价 | 初始贴水 | 当前贴水 | 已吃贴水 | 收敛比例 | 贴水年化 | 合约浮盈 |

Only unsold positions are shown. Sold positions are hidden.

## WeChat Notification

Append position summary to `notify.py` message body:

```
📊 我的持仓收益
────────────
🔹 I2609 | 买入 650.0
  当前价: 665.0 | 已吃贴水: 15.0
  收敛: 85.7% | 年化: 126.4% | 浮盈: 15.0

🔹 I2612 | 买入 620.0
  当前价: 635.0 | 已吃贴水: 10.0
  收敛: 66.7% | 年化: 98.2% | 浮盈: 15.0
────────────
📌 持仓数: 2 | 未平仓: 2
```

Includes total position count and unsold count at the bottom.

## Dependencies

- `openpyxl` for reading/writing Excel files
- Add to `requirements.txt`
