# data_fetcher.py
import logging
from datetime import date, timedelta

import akshare as ak
import pandas as pd

logger = logging.getLogger(__name__)

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
    except Exception as e:
        logger.error("fetch_active_contracts failed: %s", e, exc_info=True)
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
    except Exception as e:
        logger.error("fetch_futures_quotes failed: %s", e, exc_info=True)
        return pd.DataFrame(columns=["symbol", "current_price", "delivery_date"])


def fetch_spot_price(target_date: date | None = None) -> float | None:
    """Fetch iron ore spot price (RMB/wet-ton) for a given date.

    Source: 100ppi.com via AKShare futures_spot_price().
    If the target date is a non-trading day, tries the previous 5 calendar
    days to find the last available trading day's price.

    Note: Returns wet-ton price. Use spot_to_dry_ton() for conversion.
    """
    if target_date is None:
        target_date = date.today()
    for offset in range(6):
        check_date = target_date - timedelta(days=offset)
        date_str = check_date.strftime("%Y%m%d")
        try:
            df = ak.futures_spot_price(date=date_str, vars_list=["I"])
            if df.empty:
                continue
            row = df[df["symbol"] == "I"]
            if row.empty:
                continue
            price = row.iloc[0]["spot_price"]
            if pd.notna(price):
                return float(price)
        except Exception:
            continue
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
    year = 2000 + int(code[1:3])
    month = int(code[3:5])
    return date(year, month, 15)
