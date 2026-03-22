# Iron Ore Futures Basis Calculator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Streamlit web app that calculates and displays real-time annualized basis rates between iron ore spot and DCE futures prices, with a historical trend chart.

**Architecture:** Four modules — `calculator.py` (pure math), `storage.py` (SQLite persistence), `data_fetcher.py` (AKShare wrapper), `app.py` (Streamlit UI). Data flows one direction: fetch → calculate → store → display.

**Tech Stack:** Python 3.10+, Streamlit, AKShare, Pandas, Plotly, SQLite

**Spec:** `docs/superpowers/specs/2026-03-22-iron-ore-basis-calculator-design.md`

---

## File Structure

```
DiscountCal/
├── app.py                  # Streamlit main entry point
├── data_fetcher.py         # AKShare data fetching with retry
├── calculator.py           # Basis calculation (pure functions)
├── storage.py              # SQLite persistence
├── tests/
│   ├── __init__.py
│   ├── test_calculator.py  # Tests for calculator
│   ├── test_storage.py     # Tests for storage (in-memory SQLite)
│   └── test_data_fetcher.py # Tests for data_fetcher (mocked AKShare)
├── data/                   # Auto-created, stores SQLite DB
├── requirements.txt
└── docs/
    └── superpowers/
        ├── specs/
        │   └── 2026-03-22-iron-ore-basis-calculator-design.md
        └── plans/
            └── 2026-03-22-iron-ore-basis-calculator.md
```

---

## Task 1: Project Setup

**Files:**
- Create: `requirements.txt`
- Create: `tests/__init__.py`

- [ ] **Step 1: Create requirements.txt**

```
streamlit>=1.30.0
akshare>=1.14.0
pandas>=2.0.0
plotly>=5.18.0
pytest>=8.0.0
```

- [ ] **Step 2: Create tests/__init__.py**

Empty file.

- [ ] **Step 3: Install dependencies**

Run: `cd E:/xujun/CCProject/DiscountCal && pip install -r requirements.txt`

- [ ] **Step 4: Commit**

```bash
git add requirements.txt tests/__init__.py
git commit -m "chore: add project dependencies and test structure"
```

---

## Task 2: Calculator Module (TDD)

**Files:**
- Create: `calculator.py`
- Create: `tests/test_calculator.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_calculator.py
import pytest
from datetime import date
import pandas as pd
from calculator import calculate_annualized_basis, calculate_basis_table


class TestCalculateAnnualizedBasis:
    def test_positive_basis_contango(self):
        """Spot > futures = positive annualized basis (contango/贴水)"""
        result = calculate_annualized_basis(
            spot_price=800, futures_price=780, days_to_delivery=90
        )
        expected = (20 / 780) * (365 / 90) * 100
        assert abs(result - expected) < 0.01

    def test_negative_basis_backwardation(self):
        """Futures > spot = negative annualized basis (backwardation/升水)"""
        result = calculate_annualized_basis(
            spot_price=780, futures_price=800, days_to_delivery=90
        )
        assert result < 0

    def test_zero_futures_price_returns_none(self):
        result = calculate_annualized_basis(
            spot_price=800, futures_price=0, days_to_delivery=90
        )
        assert result is None

    def test_zero_days_to_delivery_returns_none(self):
        result = calculate_annualized_basis(
            spot_price=800, futures_price=780, days_to_delivery=0
        )
        assert result is None

    def test_negative_days_to_delivery_returns_none(self):
        result = calculate_annualized_basis(
            spot_price=800, futures_price=780, days_to_delivery=-5
        )
        assert result is None

    def test_missing_spot_price_returns_none(self):
        result = calculate_annualized_basis(
            spot_price=None, futures_price=780, days_to_delivery=90
        )
        assert result is None

    def test_missing_futures_price_returns_none(self):
        result = calculate_annualized_basis(
            spot_price=800, futures_price=None, days_to_delivery=90
        )
        assert result is None


class TestCalculateBasisTable:
    def _make_futures_df(self):
        return pd.DataFrame({
            "symbol": ["I2605", "I2609", "I2701"],
            "current_price": [780.0, 760.0, 750.0],
            "delivery_date": [
                date(2025, 5, 15),
                date(2025, 9, 15),
                date(2026, 1, 15),
            ],
        })

    def test_returns_correct_columns(self):
        futures_df = self._make_futures_df()
        today = date(2025, 3, 20)
        result = calculate_basis_table(
            futures_df=futures_df,
            spot_price=800.0,
            reference_date=today,
        )
        expected_cols = [
            "contract", "futures_price", "spot_price",
            "days_to_delivery", "spread", "annualized_basis_rate",
        ]
        assert list(result.columns) == expected_cols

    def test_sorts_by_annualized_basis_rate_descending(self):
        futures_df = self._make_futures_df()
        today = date(2025, 3, 20)
        result = calculate_basis_table(
            futures_df=futures_df,
            spot_price=800.0,
            reference_date=today,
        )
        rates = result["annualized_basis_rate"].tolist()
        assert rates == sorted(rates, reverse=True)

    def test_excludes_past_delivery_contracts(self):
        futures_df = pd.DataFrame({
            "symbol": ["I2503"],
            "current_price": [780.0],
            "delivery_date": [date(2025, 3, 1)],
        })
        today = date(2025, 3, 20)
        result = calculate_basis_table(
            futures_df=futures_df,
            spot_price=800.0,
            reference_date=today,
        )
        assert len(result) == 0

    def test_empty_dataframe_returns_empty(self):
        result = calculate_basis_table(
            futures_df=pd.DataFrame(),
            spot_price=800.0,
            reference_date=date.today(),
        )
        assert result.empty
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd E:/xujun/CCProject/DiscountCal && python -m pytest tests/test_calculator.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'calculator'`

- [ ] **Step 3: Write calculator.py implementation**

```python
# calculator.py
from datetime import date

import pandas as pd


def calculate_annualized_basis(
    spot_price: float | None,
    futures_price: float | None,
    days_to_delivery: int,
) -> float | None:
    if spot_price is None or futures_price is None:
        return None
    if futures_price == 0 or days_to_delivery <= 0:
        return None
    spread = spot_price - futures_price
    return spread / futures_price * (365 / days_to_delivery) * 100


def calculate_basis_table(
    futures_df: pd.DataFrame,
    spot_price: float,
    reference_date: date,
) -> pd.DataFrame:
    if futures_df.empty:
        return pd.DataFrame()

    rows = []
    for _, row in futures_df.iterrows():
        delivery_date = row["delivery_date"]
        days_to_delivery = (delivery_date - reference_date).days
        if days_to_delivery <= 0:
            continue

        futures_price = row["current_price"]
        annualized_rate = calculate_annualized_basis(
            spot_price, futures_price, days_to_delivery
        )
        rows.append({
            "contract": row["symbol"],
            "futures_price": futures_price,
            "spot_price": spot_price,
            "days_to_delivery": days_to_delivery,
            "spread": spot_price - futures_price,
            "annualized_basis_rate": annualized_rate,
        })

    result = pd.DataFrame(rows)
    if not result.empty:
        result = result.sort_values(
            "annualized_basis_rate", ascending=False
        ).reset_index(drop=True)
    return result
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd E:/xujun/CCProject/DiscountCal && python -m pytest tests/test_calculator.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add calculator.py tests/test_calculator.py
git commit -m "feat: add basis calculation with tests"
```

---

## Task 3: Storage Module (TDD)

**Files:**
- Create: `storage.py`
- Create: `tests/test_storage.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_storage.py
import pytest
import pandas as pd
from storage import BasisStorage


@pytest.fixture
def db(tmp_path):
    db_path = tmp_path / "test.db"
    storage = BasisStorage(str(db_path))
    yield storage
    storage.close()


class TestBasisStorage:
    def test_init_creates_table(self, db):
        result = db.get_history("I2605")
        assert isinstance(result, pd.DataFrame)
        assert result.empty

    def test_save_and_retrieve_single_row(self, db):
        db.save_record(
            date="2025-03-20",
            contract="I2605",
            spot_price=800.0,
            futures_price=780.0,
            days_to_delivery=56,
            spread=20.0,
            annualized_basis_rate=16.49,
        )
        history = db.get_history("I2605")
        assert len(history) == 1
        assert history.iloc[0]["annualized_basis_rate"] == 16.49

    def test_get_all_contracts_returns_multiple(self, db):
        db.save_record("2025-03-20", "I2605", 800, 780, 56, 20.0, 16.49)
        db.save_record("2025-03-20", "I2609", 800, 760, 179, 40.0, 10.73)
        contracts = db.get_all_contracts()
        assert set(contracts) == {"I2605", "I2609"}

    def test_get_latest_date(self, db):
        db.save_record("2025-03-18", "I2605", 790, 775, 58, 15.0, 12.2)
        db.save_record("2025-03-20", "I2605", 800, 780, 56, 20.0, 16.49)
        latest = db.get_latest_date()
        assert latest == "2025-03-20"

    def test_get_latest_date_empty_db(self, db):
        latest = db.get_latest_date()
        assert latest is None

    def test_date_exists(self, db):
        db.save_record("2025-03-20", "I2605", 800, 780, 56, 20.0, 16.49)
        assert db.date_exists("2025-03-20") is True
        assert db.date_exists("2025-03-21") is False

    def test_get_history_date_range(self, db):
        db.save_record("2025-03-18", "I2605", 790, 775, 58, 15.0, 12.2)
        db.save_record("2025-03-19", "I2605", 795, 778, 57, 17.0, 14.0)
        db.save_record("2025-03-20", "I2605", 800, 780, 56, 20.0, 16.49)
        history = db.get_history("I2605", start_date="2025-03-19")
        assert len(history) == 2

    def test_upsert_does_not_duplicate(self, db):
        db.save_record("2025-03-20", "I2605", 800, 780, 56, 20.0, 16.49)
        db.save_record("2025-03-20", "I2605", 801, 781, 56, 20.0, 16.3)
        history = db.get_history("I2605")
        assert len(history) == 1
        assert history.iloc[0]["spot_price"] == 801
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd E:/xujun/CCProject/DiscountCal && python -m pytest tests/test_storage.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'storage'`

- [ ] **Step 3: Write storage.py implementation**

```python
# storage.py
import sqlite3
from pathlib import Path

import pandas as pd


class BasisStorage:
    def __init__(self, db_path: str = "data/basis_history.db"):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS basis_history (
                date TEXT NOT NULL,
                contract TEXT NOT NULL,
                spot_price REAL,
                futures_price REAL,
                days_to_delivery INTEGER,
                spread REAL,
                annualized_basis_rate REAL,
                PRIMARY KEY (date, contract)
            )
        """)
        self._conn.commit()

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    def save_record(
        self,
        date: str,
        contract: str,
        spot_price: float,
        futures_price: float,
        days_to_delivery: int,
        spread: float,
        annualized_basis_rate: float,
    ) -> None:
        self._conn.execute("""
            INSERT INTO basis_history (date, contract, spot_price, futures_price,
                days_to_delivery, spread, annualized_basis_rate)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(date, contract) DO UPDATE SET
                spot_price=excluded.spot_price,
                futures_price=excluded.futures_price,
                days_to_delivery=excluded.days_to_delivery,
                spread=excluded.spread,
                annualized_basis_rate=excluded.annualized_basis_rate
        """, (date, contract, spot_price, futures_price,
              days_to_delivery, spread, annualized_basis_rate))
        self._conn.commit()

    def get_history(
        self, contract: str, start_date: str | None = None
    ) -> pd.DataFrame:
        query = """
            SELECT date, contract, spot_price, futures_price,
                   days_to_delivery, spread, annualized_basis_rate
            FROM basis_history
            WHERE contract = ?
        """
        params: list = [contract]
        if start_date:
            query += " AND date >= ?"
            params.append(start_date)
        query += " ORDER BY date"
        return pd.read_sql_query(query, self._conn, params=params)

    def get_all_contracts(self) -> list[str]:
        cursor = self._conn.execute(
            "SELECT DISTINCT contract FROM basis_history ORDER BY contract"
        )
        return [row[0] for row in cursor.fetchall()]

    def get_latest_date(self) -> str | None:
        cursor = self._conn.execute(
            "SELECT MAX(date) FROM basis_history"
        )
        row = cursor.fetchone()
        return row[0] if row and row[0] else None

    def date_exists(self, date: str) -> bool:
        cursor = self._conn.execute(
            "SELECT 1 FROM basis_history WHERE date = ? LIMIT 1", (date,)
        )
        return cursor.fetchone() is not None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd E:/xujun/CCProject/DiscountCal && python -m pytest tests/test_storage.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add storage.py tests/test_storage.py
git commit -m "feat: add SQLite storage with upsert and history query"
```

---

## Task 4: Data Fetcher Module

**Files:**
- Create: `data_fetcher.py`
- Create: `tests/test_data_fetcher.py`

**AKShare API reference (verified against installed version):**

| Function | Purpose | Key params | Output columns |
|----------|---------|------------|----------------|
| `futures_zh_realtime(symbol="铁矿石")` | All active contracts | symbol: Chinese name | `symbol` (e.g. "I2605"), `trade` (price) |
| `futures_zh_spot(symbol, market="CF")` | Real-time quotes | symbol: comma-separated uppercase "I2605,I2609" | `symbol` (e.g. "铁矿石2605"), `current_price` |
| `futures_spot_price(date, vars_list)` | Daily spot price (100ppi.com) | date: "YYYYMMDD", vars_list: ["I"] | `spot_price`, `symbol`, ... |

**Important notes (verified by running against live AKShare):**
- `futures_zh_realtime()` returns **uppercase** symbols: `I0, I2605, I2609...`. Filter out `I0` (index).
- `futures_zh_spot()` requires **uppercase** input: `I2605,I2609` (not `i2505`). Returns **Chinese** names: `铁矿石2605`.
- All contract codes in this codebase use **uppercase** format: `I2605`, `I2609`.
- `futures_spot_price()` source (100ppi.com) reports spot price in **wet tons (湿吨)**, while DCE futures are in **dry tons (干吨)**. A moisture conversion factor is needed.
- `futures_spot_price()` returns empty DataFrame on non-trading days — this is expected.

- [ ] **Step 1: Write tests with mocked AKShare**

```python
# tests/test_data_fetcher.py
import pytest
from datetime import date
import pandas as pd

from data_fetcher import (
    fetch_active_contracts,
    fetch_futures_quotes,
    fetch_spot_price,
    _extract_contract_code,
    _parse_delivery_date,
    spot_to_dry_ton,
)


class TestExtractContractCode:
    def test_uppercase_code(self):
        assert _extract_contract_code("I2505") == "I2505"

    def test_lowercase_code(self):
        assert _extract_contract_code("i2505") == "I2505"

    def test_chinese_name(self):
        assert _extract_contract_code("铁矿石2505") == "I2505"

    def test_index_symbol_filtered(self):
        assert _extract_contract_code("I0") is None

    def test_unknown_format_returns_none(self):
        assert _extract_contract_code("unknown123") is None


class TestParseDeliveryDate:
    def test_known_contract(self):
        result = _parse_delivery_date("I2505")
        assert result == date(2025, 5, 15)

    def test_unknown_returns_today(self):
        result = _parse_delivery_date("unknown")
        assert result == date.today()


class TestSpotToDryTon:
    def test_eight_percent_moisture(self):
        result = spot_to_dry_ton(800.0, moisture_pct=8.0)
        assert abs(result - 869.57) < 0.01

    def test_zero_moisture(self):
        assert spot_to_dry_ton(800.0, moisture_pct=0.0) == 800.0

    def test_none_price_returns_none(self):
        assert spot_to_dry_ton(None) is None


class TestFetchActiveContracts:
    def test_returns_empty_on_exception(self, monkeypatch):
        import data_fetcher
        monkeypatch.setattr(data_fetcher.ak, "futures_zh_realtime",
                            side_effect=Exception("network error"))
        result = fetch_active_contracts()
        assert result == []

    def test_returns_uppercase_contracts(self, monkeypatch):
        import data_fetcher
        mock_df = pd.DataFrame({
            "symbol": ["I0", "I2605", "I2609", "I2601"],
            "trade": [0.0, 780.0, 760.0, 750.0],
        })
        monkeypatch.setattr(data_fetcher.ak, "futures_zh_realtime",
                            lambda symbol: mock_df)
        result = fetch_active_contracts()
        assert result == ["I2601", "I2605", "I2609"]

    def test_filters_out_zero_price(self, monkeypatch):
        import data_fetcher
        mock_df = pd.DataFrame({
            "symbol": ["I0", "I2605"],
            "trade": [0.0, 780.0],
        })
        monkeypatch.setattr(data_fetcher.ak, "futures_zh_realtime",
                            lambda symbol: mock_df)
        result = fetch_active_contracts()
        assert result == ["I2605"]


class TestFetchSpotPrice:
    def test_returns_none_on_exception(self, monkeypatch):
        import data_fetcher
        monkeypatch.setattr(data_fetcher.ak, "futures_spot_price",
                            side_effect=Exception("network error"))
        result = fetch_spot_price()
        assert result is None

    def test_returns_none_on_empty(self, monkeypatch):
        import data_fetcher
        monkeypatch.setattr(data_fetcher.ak, "futures_spot_price",
                            lambda date, vars_list: pd.DataFrame())
        result = fetch_spot_price()
        assert result is None

    def test_returns_price(self, monkeypatch):
        import data_fetcher
        mock_df = pd.DataFrame({
            "symbol": ["I"],
            "spot_price": [800.0],
        })
        monkeypatch.setattr(data_fetcher.ak, "futures_spot_price",
                            lambda date, vars_list: mock_df)
        result = fetch_spot_price()
        assert result == 800.0


class TestFetchFuturesQuotes:
    def test_returns_empty_on_empty_input(self):
        result = fetch_futures_quotes([])
        assert result.empty

    def test_returns_dataframe_with_correct_columns(self, monkeypatch):
        import data_fetcher
        mock_df = pd.DataFrame({
            "symbol": ["铁矿石2605", "铁矿石2609"],
            "current_price": [780.0, 760.0],
        })
        monkeypatch.setattr(data_fetcher.ak, "futures_zh_spot",
                            lambda symbol, market, adjust: mock_df)
        result = fetch_futures_quotes(["I2605", "I2609"])
        assert list(result.columns) == ["symbol", "current_price", "delivery_date"]
        assert len(result) == 2

    def test_returns_empty_on_exception(self, monkeypatch):
        import data_fetcher
        monkeypatch.setattr(data_fetcher.ak, "futures_zh_spot",
                            side_effect=Exception("network error"))
        result = fetch_futures_quotes(["I2605"])
        assert result.empty
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd E:/xujun/CCProject/DiscountCal && python -m pytest tests/test_data_fetcher.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'data_fetcher'`

- [ ] **Step 3: Write data_fetcher.py implementation**

```python
# data_fetcher.py
from datetime import date

import akshare as ak
import pandas as pd

# Default moisture content for Australian iron ore (PB fines ~8%)
DEFAULT_MOISTURE_PCT = 8.0


def spot_to_dry_ton(
    wet_price: float | None, moisture_pct: float = DEFAULT_MOISTURE_PCT
) -> float | None:
    """Convert spot price from wet tons to dry tons.

    Iron ore spot prices (100ppi.com) are in wet tons (湿吨).
    DCE futures are in dry tons (干吨). This conversion is needed
    for accurate basis calculation.

    Formula: dry_price = wet_price / (1 - moisture_pct / 100)
    """
    if wet_price is None:
        return None
    return wet_price / (1 - moisture_pct / 100)


def fetch_active_contracts() -> list[str]:
    """Get all active iron ore contract codes from DCE.

    Uses futures_zh_realtime to discover all active contracts.
    Returns uppercase list like ["I2605", "I2609", "I2601"].
    Filters out I0 (index) and contracts with zero price.
    """
    try:
        df = ak.futures_zh_realtime(symbol="铁矿石")
        if df.empty:
            return []
        df = df[df["trade"] > 0]
        contracts = []
        for s in df["symbol"]:
            code = _extract_contract_code(str(s))
            if code:
                contracts.append(code)
        return sorted(contracts)
    except Exception:
        return []


def fetch_futures_quotes(contracts: list[str]) -> pd.DataFrame:
    """Fetch real-time quotes for given contract codes.

    Args:
        contracts: uppercase list like ["I2605", "I2609"]

    Returns:
        DataFrame with columns: symbol, current_price, delivery_date
    """
    if not contracts:
        return pd.DataFrame(columns=["symbol", "current_price", "delivery_date"])

    symbol_str = ",".join(contracts)
    try:
        df = ak.futures_zh_spot(symbol=symbol_str, market="CF", adjust="0")
        if df.empty:
            return pd.DataFrame(columns=["symbol", "current_price", "delivery_date"])

        result = pd.DataFrame({
            "symbol": df["symbol"].apply(_extract_contract_code),
            "current_price": df["current_price"].astype(float),
        })
        result = result[result["symbol"].notna()]
        result["delivery_date"] = result["symbol"].apply(_parse_delivery_date)
        return result
    except Exception:
        return pd.DataFrame(columns=["symbol", "current_price", "delivery_date"])


def fetch_spot_price(target_date: date | None = None) -> float | None:
    """Fetch iron ore spot price (RMB/wet-ton) for a given date.

    Source: 100ppi.com via AKShare futures_spot_price().
    Returns empty on non-trading days.

    Note: Returns wet-ton price. Use spot_to_dry_ton() for conversion.
    """
    if target_date is None:
        target_date = date.today()
    date_str = target_date.strftime("%Y%m%d")
    try:
        df = ak.futures_spot_price(date=date_str, vars_list=["I"])
        if df.empty:
            return None
        row = df[df["symbol"] == "I"]
        if row.empty:
            return None
        price = row.iloc[0]["spot_price"]
        return float(price) if pd.notna(price) else None
    except Exception:
        return None


def _extract_contract_code(symbol: str) -> str | None:
    """Extract uppercase contract code like 'I2605' from various formats.

    Handles: "I2605", "i2605", "铁矿石2605". Returns None for "I0" (index).
    """
    s = symbol.strip()
    # Direct format: "I2605" or "i2605"
    if s.upper().startswith("I") and len(s) == 5 and s[1:].isdigit():
        code = s.upper()
        if code == "I0":
            return None
        return code
    # Chinese name format: "铁矿石2605"
    cn_map = {"铁矿石": "I"}
    for cn, code in cn_map.items():
        if cn in s:
            digits = "".join(c for c in s if c.isdigit())
            if len(digits) == 4:
                return f"{code}{digits}"
    return None


def _parse_delivery_date(symbol: str) -> date:
    """Parse delivery date from contract symbol.

    DCE iron ore delivery is on the 10th business day of the delivery month.
    Approximated as the 15th calendar day (off by 0-5 days depending on
    weekends/holidays). Good enough for annualized rate calculation.
    """
    code = _extract_contract_code(symbol)
    if code is None:
        return date.today()
    month = int(code[1:3])
    year = 2000 + int(code[3:5])
    return date(year, month, 15)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd E:/xujun/CCProject/DiscountCal && python -m pytest tests/test_data_fetcher.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add data_fetcher.py tests/test_data_fetcher.py
git commit -m "feat: add AKShare data fetcher with wet/dry ton conversion"
```

---

## Task 5: Streamlit App — Data Layer

**Files:**
- Create: `app.py` (partial — data update logic only, no UI yet)

- [ ] **Step 1: Write app.py with data update logic**

```python
# app.py
import time
from datetime import date, datetime, timedelta

import pandas as pd
import streamlit as st

from calculator import calculate_basis_table, calculate_annualized_basis
from data_fetcher import (
    fetch_active_contracts,
    fetch_futures_quotes,
    fetch_spot_price,
    spot_to_dry_ton,
)
from storage import BasisStorage

DB_PATH = "data/basis_history.db"
DEFAULT_REFRESH_SECONDS = 30


def is_trading_hours() -> bool:
    now = datetime.now()
    if now.weekday() >= 5:
        return False
    t = now.time()
    return (time(9, 0) <= t <= time(15, 0)) or (time(21, 0) <= t <= time(23, 0))


@st.cache_resource
def get_storage() -> BasisStorage:
    return BasisStorage(DB_PATH)


def save_today_data(storage: BasisStorage) -> float | None:
    """Fetch today's spot and futures data, calculate basis, save to storage.

    Returns the dry-ton spot price, or None if unavailable.
    """
    today_str = date.today().isoformat()
    if storage.date_exists(today_str):
        # Already have today's data, return spot price from storage
        contracts = storage.get_all_contracts()
        if contracts:
            history = storage.get_history(contracts[0], start_date=today_str)
            if not history.empty:
                return float(history.iloc[0]["spot_price"])
        return None

    wet_spot = fetch_spot_price()
    if wet_spot is None:
        return None

    spot = spot_to_dry_ton(wet_spot)
    if spot is None:
        return None

    contracts = fetch_active_contracts()
    if not contracts:
        return spot

    futures_df = fetch_futures_quotes(contracts)
    if futures_df.empty:
        return spot

    for _, row in futures_df.iterrows():
        days = (row["delivery_date"] - date.today()).days
        if days <= 0:
            continue
        fp = row["current_price"]
        if pd.isna(fp) or fp == 0:
            continue
        rate = calculate_annualized_basis(spot, fp, days)
        if rate is not None:
            storage.save_record(
                date=today_str,
                contract=row["symbol"],
                spot_price=spot,
                futures_price=fp,
                days_to_delivery=days,
                spread=spot - fp,
                annualized_basis_rate=round(rate, 2),
            )

    return spot


def get_realtime_basis_table(spot_price: float) -> pd.DataFrame:
    """Build real-time basis table using latest futures quotes."""
    contracts = fetch_active_contracts()
    if not contracts or spot_price is None:
        return pd.DataFrame()

    futures_df = fetch_futures_quotes(contracts)
    if futures_df.empty:
        return pd.DataFrame()

    return calculate_basis_table(
        futures_df=futures_df,
        spot_price=spot_price,
        reference_date=date.today(),
    )
```

- [ ] **Step 2: Verify imports work**

Run: `cd E:/xujun/CCProject/DiscountCal && python -c "from app import save_today_data; print('OK')"`
Expected: "OK"

- [ ] **Step 3: Run all tests**

Run: `cd E:/xujun/CCProject/DiscountCal && python -m pytest tests/ -v`
Expected: All PASS

- [ ] **Step 4: Commit**

```bash
git add app.py
git commit -m "feat: add data update logic with wet/dry ton conversion"
```

---

## Task 6: Streamlit App — UI and Trend Chart

**Files:**
- Modify: `app.py` (add UI rendering)

- [ ] **Step 1: Add UI rendering to app.py**

Append the following to the existing `app.py`:

```python
# --- UI rendering (append to app.py) ---

import plotly.graph_objects as go


def render_trend_chart(storage: BasisStorage) -> None:
    contracts = storage.get_all_contracts()
    if not contracts:
        st.info("No historical data yet. Data accumulates on each trading day.")
        return

    fig = go.Figure()
    colors = [
        "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd",
        "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22", "#17becf",
    ]

    for i, contract in enumerate(contracts):
        history = storage.get_history(contract)
        if history.empty:
            continue
        fig.add_trace(go.Scatter(
            x=history["date"],
            y=history["annualized_basis_rate"],
            mode="lines+markers",
            name=contract,
            line=dict(color=colors[i % len(colors)]),
            marker=dict(size=4),
        ))

    fig.update_layout(
        title="Annualized Basis Rate Trend",
        xaxis_title="Date",
        yaxis_title="Annualized Basis Rate (%)",
        hovermode="x unified",
        height=500,
    )
    st.plotly_chart(fig, use_container_width=True)


def main():
    st.set_page_config(
        page_title="Iron Ore Basis Calculator",
        page_icon="📈",
        layout="wide",
    )

    st.title("Iron Ore Futures Basis Calculator (铁矿石贴水计算器)")
    st.caption("Spot price converted from wet tons to dry tons (moisture ~8%). Delivery date approximated as 15th of contract month.")

    storage = get_storage()

    # Refresh control
    col1, col2, col3 = st.columns([2, 1, 1])
    refresh_interval = col2.number_input(
        "Refresh interval (seconds)", min_value=5, max_value=300,
        value=DEFAULT_REFRESH_SECONDS, step=5,
    )

    # Fetch and save today's data
    with st.spinner("Fetching data..."):
        spot_price = save_today_data(storage)

    # Build real-time basis table
    basis_table = get_realtime_basis_table(spot_price) if spot_price else pd.DataFrame()

    # Display spot price
    if spot_price is not None:
        col1.metric("Iron Ore Spot Price (CNY/dry-ton)", f"{spot_price:.1f}")
    else:
        col1.warning("Spot price unavailable. Data may be outside trading hours.")

    update_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    col3.text(f"Updated: {update_time}")

    # Basis table
    if not basis_table.empty:
        st.subheader("Basis Table (贴水表)")
        display_df = basis_table.copy()
        display_df["annualized_basis_rate"] = display_df[
            "annualized_basis_rate"
        ].apply(lambda x: f"{x:.2f}%" if pd.notna(x) else "N/A")
        display_df["spread"] = display_df["spread"].apply(
            lambda x: f"{x:.1f}" if pd.notna(x) else "N/A"
        )
        display_df["spot_price"] = display_df["spot_price"].apply(
            lambda x: f"{x:.1f}"
        )
        display_df["futures_price"] = display_df["futures_price"].apply(
            lambda x: f"{x:.1f}"
        )
        st.dataframe(display_df, use_container_width=True, hide_index=True)
    else:
        st.warning("No basis data available. Check during trading hours.")

    # Trend chart
    st.subheader("Basis Rate Trend (贴水走势)")
    render_trend_chart(storage)

    # Auto-refresh during trading hours
    if is_trading_hours():
        time.sleep(refresh_interval)
        st.rerun()


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run all tests**

Run: `cd E:/xujun/CCProject/DiscountCal && python -m pytest tests/ -v`
Expected: All PASS

- [ ] **Step 3: Verify app starts without import errors**

Run: `cd E:/xujun/CCProject/DiscountCal && python -c "from app import main; print('OK')"`
Expected: "OK"

- [ ] **Step 4: Commit**

```bash
git add app.py
git commit -m "feat: add Streamlit UI with trend chart and auto-refresh"
```

---

## Task 7: Manual Verification

- [ ] **Step 1: Start the app during trading hours**

Run: `cd E:/xujun/CCProject/DiscountCal && streamlit run app.py`
Open: `http://localhost:8501`

- [ ] **Step 2: Verify**

- [ ] Spot price card shows a number (dry-ton converted)
- [ ] Basis table shows multiple iron ore contracts with annualized rates
- [ ] Positive rates (contango/贴水) and negative rates (backwardation/升水) display correctly
- [ ] Trend chart renders (may be empty on first day, accumulates data over time)
- [ ] Page auto-refreshes every 30 seconds during trading hours
- [ ] Refresh interval control works
- [ ] Caption shows wet/dry ton conversion disclaimer

## Design Decisions

### Why no initial 60-day backfill?

`futures_spot_price_daily()` from AKShare scrapes 100ppi.com day-by-day (~80 HTTP requests for 60 trading days), which is slow and risks IP bans. Historical backfill also requires per-contract historical futures prices which need a separate API per contract per day — impractical.

Instead: data accumulates day-by-day. Each trading day the app runs, it saves that day's basis data. The trend chart fills up naturally over ~60 trading days (~3 months).

### Wet ton / Dry ton conversion

Iron ore spot prices from 100ppi.com (via AKShare `futures_spot_price()`) are in wet tons (湿吨), while DCE futures are in dry tons (干吨). We apply a default 8% moisture conversion: `dry_price = wet_price / (1 - 0.08)`. This is an approximation — actual moisture varies by ore grade (PB fines ~8%, Mac fines ~9%, etc.). The UI shows a disclaimer about this.
