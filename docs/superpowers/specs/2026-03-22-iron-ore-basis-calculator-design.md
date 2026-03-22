# Iron Ore Futures Basis Annualized Calculator - Design Spec

## Overview

A real-time web-based calculator for iron ore futures basis (contango/backwardation) annualized rate. Starting with iron ore (DCE), designed to be extensible to other commodity futures.

## Core Formula

```
annualized_basis_rate = (spot_price - futures_price) / futures_price * (365 / days_to_delivery) * 100%
```

- Positive value = contango (spot > futures, "贴水")
- Negative value = backwardation (futures > spot, "升水")

## Data Sources

| Data | Source | AKShare Function | Frequency |
|------|--------|-----------------|-----------|
| Iron ore futures quotes (all active contracts) | Sina Finance | `futures_zh_spot_sina()` | Real-time |
| Iron ore spot price (CNY/ton) | East Money | `futures_spot_price()` | Daily |

### Data Selection Rationale

AKShare `futures_spot_price()` provides a representative RMB spot price directly comparable with DCE futures (same currency unit, no conversion needed). This is simpler than using the Platts 62% index (USD) which requires exchange rate conversion.

## Project Structure

```
DiscountCal/
├── app.py                  # Streamlit main entry point
├── data_fetcher.py         # Data fetching layer (AKShare wrapper)
├── calculator.py           # Basis calculation logic
├── storage.py              # Local data persistence (SQLite)
├── data/                   # Auto-created SQLite database directory
├── requirements.txt
└── README.md
```

### Module Responsibilities

- **`data_fetcher.py`** — Fetches futures quotes and spot prices via AKShare. Returns standardized DataFrames. Handles retries on failure.
- **`calculator.py`** — Receives price data, computes annualized basis rates. Pure functions, no side effects.
- **`storage.py`** — Reads/writes historical basis data to local SQLite. Handles first-run backfill.
- **`app.py`** — Streamlit page. Calls the above modules, auto-refreshes display.

## Page Layout (top to bottom)

1. **Header**: Tool name + data update timestamp + refresh interval control
2. **Spot price card**: Current iron ore RMB spot price
3. **Basis table**: Contract code | Latest price | Days to delivery | Spot-futures spread | Annualized basis rate (%)
4. **Basis trend chart**: Multi-contract annualized basis rate over time (last 60 trading days). X-axis: date, Y-axis: annualized basis rate (%). Different colored lines per contract. Interactive Plotly chart (hover for values, zoom, etc.)

## Display Rules

- Sort table by annualized basis rate
- Contracts with days_to_delivery <= 0 (in delivery month): greyed out or excluded
- Missing/zero price values: display "N/A"
- Positive basis (contango/贴水): red
- Negative basis (backwardation/升水): green

## Refresh Strategy

- Trading hours: auto-refresh every 30 seconds
  - Day session: 09:00-15:00
  - Night session: 21:00-23:00
- Non-trading hours (weekends, holidays): pause refresh, show last available data with date label
- User can manually adjust refresh interval

## Historical Data for Trend Chart

### Caching Strategy

Historical basis data is persisted locally in SQLite. No unnecessary recalculation.

- **First run**: Backfill the last 60 trading days of historical data from AKShare (futures + spot prices), calculate basis, store all results.
- **Subsequent runs**: Only fetch today's new data, calculate basis, and append to local storage if the date doesn't already exist.
- **Trend chart**: Reads directly from local SQLite, no API calls needed for historical display.

### Storage Schema (SQLite)

```sql
CREATE TABLE basis_history (
    date TEXT NOT NULL,              -- trading date (YYYY-MM-DD)
    contract TEXT NOT NULL,          -- e.g. "i2505"
    spot_price REAL,                 -- RMB/ton
    futures_price REAL,              -- RMB/ton
    days_to_delivery INTEGER,        -- days until contract delivery
    spread REAL,                     -- spot_price - futures_price
    annualized_basis_rate REAL,      -- annualized percentage
    PRIMARY KEY (date, contract)
);
```

### Display Range

- Default: last 60 trading days
- User can adjust the time range

## Error Handling

- AKShare API failure: display last successful data with "update failed" label, do not break the page
- Non-trading day: show most recent trading day data with date annotation

## Tech Stack

- Python 3.10+
- Streamlit (web framework)
- AKShare (data source)
- Pandas (data processing)
- Plotly (charts)
- SQLite (local data persistence, built-in with Python)

## Run

```bash
pip install -r requirements.txt
streamlit run app.py
```

Opens `http://localhost:8501` in browser.
