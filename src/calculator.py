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
            "days_to_delivery", ascending=True
        ).reset_index(drop=True)
    return result
