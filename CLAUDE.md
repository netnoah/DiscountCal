# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
streamlit run app.py          # Start the app (runs on port 8501 by default)
pytest tests/ -v              # Run all tests
pytest tests/test_calculator.py -v  # Run a single test file
```

## Architecture

Streamlit app for calculating annualized basis rates on DCE iron ore futures.

**Data flow:** AKShare API → `data_fetcher.py` → `calculator.py` → `app.py` (display) + `storage.py` (SQLite persistence)

- **`data_fetcher.py`** — Fetches live futures quotes and spot prices from AKShare. Contract codes are uppercase (`I2505`, `I2609`). Delivery dates are approximated as the 15th of the contract month. Spot prices are wet-ton; use `spot_to_dry_ton()` for dry-ton conversion.
- **`calculator.py`** — Pure functions. `calculate_annualized_basis()` computes `(spot - futures) / futures * 365 / days * 100`. `calculate_basis_table()` builds a DataFrame sorted by `days_to_delivery` ascending (near to far).
- **`storage.py`** — `BasisStorage` wraps SQLite at `data/basis_history.db`. Upserts by `(date, contract)` primary key. `save_today_data()` in `app.py` skips re-fetch if today's date already exists.
- **`app.py`** — Streamlit entry point. Uses nearest delivery contract price as the base price (基准价). Auto-refreshes during DCE trading hours (9:00–15:00, 21:00–23:00 on weekdays). Trend chart reads from local SQLite, not API.

## Key domain notes

- The basis table uses the **nearest contract price** as base, not an external spot price.
- AKShare column names and APIs can change between versions — `data_fetcher.py` is the isolation layer.
- `fetch_futures_quotes` returns DataFrame columns: `symbol`, `current_price`, `delivery_date` (no `days_to_delivery`).
