# notify.py
"""Fetch iron ore basis data and send to WeChat Work webhook."""

import json
import os
import urllib.request
import urllib.error
from datetime import date

import pandas as pd

from data_fetcher import fetch_active_contracts, fetch_futures_quotes
from calculator import calculate_basis_table
from position import load_positions, calculate_position_return, compute_position_returns, build_position_summary, save_captured_basis


WEBHOOK_URL = os.environ.get("WECHAT_WEBHOOK_URL")
POSITIONS_FILE = "data/positions.xlsx"


def _find_near_contract_price(futures_df: pd.DataFrame) -> float | None:
    """Find the nearest delivery contract's price to use as base price."""
    if futures_df.empty:
        return None
    today = date.today()
    days = futures_df["delivery_date"].apply(lambda d: (d - today).days)
    valid = days[days > 0]
    if valid.empty:
        return None
    nearest_idx = valid.idxmin()
    price = futures_df.loc[nearest_idx, "current_price"]
    return float(price) if pd.notna(price) and price > 0 else None


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


def send_webhook(content: str) -> bool:
    """Send text message to WeChat Work webhook."""
    if not WEBHOOK_URL:
        print("ERROR: WECHAT_WEBHOOK_URL not set")
        return False

    payload = json.dumps({
        "msgtype": "text",
        "text": {"content": content},
    }).encode("utf-8")

    req = urllib.request.Request(
        WEBHOOK_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            if body.get("errcode") != 0:
                print(f"Webhook error: {body}")
                return False
            print("Notification sent successfully")
            return True
    except urllib.error.URLError as e:
        print(f"Webhook request failed: {e}")
        return False


def main():
    message = build_text_message()
    if not message:
        print("No basis data available (possibly non-trading day)")
        return

    print(message)
    send_webhook(message)


if __name__ == "__main__":
    main()
