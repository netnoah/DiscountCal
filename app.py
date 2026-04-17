# app.py
import logging
import time
from datetime import date, datetime, time as dt_time

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from calculator import calculate_basis_table, calculate_annualized_basis
from data_fetcher import (
    fetch_active_contracts,
    fetch_futures_quotes,
)
from storage import BasisStorage
from position import load_positions, compute_position_returns, save_captured_basis

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

DB_PATH = "data/basis_history.db"
DEFAULT_REFRESH_SECONDS = 30
POSITIONS_FILE = "data/positions.xlsx"


def is_trading_hours() -> bool:
    now = datetime.now()
    if now.weekday() >= 5:
        return False
    t = now.time()
    return (dt_time(9, 0) <= t <= dt_time(15, 0)) or (dt_time(21, 0) <= t <= dt_time(23, 0))


@st.cache_resource
def get_storage() -> BasisStorage:
    return BasisStorage(DB_PATH)


def _find_near_contract_price(futures_df: pd.DataFrame) -> float | None:
    """Find the nearest delivery contract's price to use as base price."""
    if futures_df.empty:
        return None
    today = date.today()
    days = futures_df["delivery_date"].apply(lambda d: (d - today).days)
    nearest_idx = days.idxmin()
    price = futures_df.loc[nearest_idx, "current_price"]
    return float(price) if pd.notna(price) and price > 0 else None


def save_today_data(storage: BasisStorage) -> float | None:
    """Fetch today's futures data, calculate basis using near contract as base, save.

    Returns the near contract price, or None if unavailable.
    """
    today_str = date.today().isoformat()
    if storage.date_exists(today_str):
        for contract in storage.get_all_contracts():
            history = storage.get_history(contract, start_date=today_str)
            if not history.empty:
                return float(history.iloc[0]["spot_price"])
        return None

    contracts = fetch_active_contracts()
    if not contracts:
        return None

    futures_df = fetch_futures_quotes(contracts)
    if futures_df.empty:
        return None

    near_price = _find_near_contract_price(futures_df)
    if near_price is None:
        return None

    for _, row in futures_df.iterrows():
        days = (row["delivery_date"] - date.today()).days
        if days <= 0:
            continue
        fp = row["current_price"]
        if pd.isna(fp) or fp == 0:
            continue
        rate = calculate_annualized_basis(near_price, fp, days)
        if rate is not None:
            storage.save_record(
                date=today_str,
                contract=row["symbol"],
                spot_price=near_price,
                futures_price=fp,
                days_to_delivery=days,
                spread=near_price - fp,
                annualized_basis_rate=round(rate, 2),
            )

    return near_price


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


def render_trend_chart(storage: BasisStorage) -> None:
    contracts = storage.get_all_contracts()
    if not contracts:
        st.info("暂无历史数据。数据会在每个交易日自动累积。")
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
        title="年化贴水率走势",
        xaxis_title="日期",
        yaxis_title="年化贴水率 (%)",
        hovermode="x unified",
        height=500,
    )
    st.plotly_chart(fig, use_container_width=True)


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

    # Skip sold positions entirely
    active_positions = [p for p in positions if not p["sold"]]

    # Compute returns for active positions
    returns = compute_position_returns(active_positions, price_map, near_price)

    # Write back captured_basis to Excel
    for r in returns:
        pos = next(
            (p for p in active_positions if p["contract"] == r["contract"]), None
        )
        if pos is None:
            continue
        save_captured_basis(POSITIONS_FILE, pos["row_index"], r["captured_basis"])

    # Display unsold positions only
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


def main():
    st.set_page_config(
        page_title="铁矿石贴水计算器",
        page_icon="📈",
        layout="wide",
    )

    st.title("铁矿石期货贴水计算器")
    st.caption("以最近交割月合约价格作为基准价，计算各合约的年化贴水率。交割日近似为合约月15日。")

    storage = get_storage()

    # Refresh control
    col1, col2, col3 = st.columns([2, 1, 1])
    refresh_interval = col2.number_input(
        "刷新间隔（秒）", min_value=5, max_value=300,
        value=DEFAULT_REFRESH_SECONDS, step=5,
    )

    # Fetch and save today's data
    with st.spinner("正在获取数据..."):
        near_price = save_today_data(storage)

    # Fetch real-time data (single fetch for basis table + position table)
    futures_df, realtime_near_price = get_realtime_data()
    if realtime_near_price is not None:
        near_price = realtime_near_price

    basis_table = calculate_basis_table(
        futures_df=futures_df,
        spot_price=near_price,
        reference_date=date.today(),
    ) if near_price else pd.DataFrame()

    # Display near contract price
    if near_price is not None:
        col1.metric("近月合约基准价（元/吨）", f"{near_price:.1f}")
    else:
        col1.warning("数据获取失败。")

    update_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    col3.text(f"更新时间: {update_time}")

    # Basis table
    if not basis_table.empty:
        st.subheader("贴水表")
        display_df = basis_table.copy()
        display_df = display_df.rename(columns={
            "contract": "合约",
            "futures_price": "期货价格",
            "spot_price": "基准价",
            "days_to_delivery": "距交割天数",
            "spread": "价差",
            "annualized_basis_rate": "年化贴水率",
        })
        display_df["年化贴水率"] = display_df[
            "年化贴水率"
        ].apply(lambda x: f"{x:.2f}%" if pd.notna(x) else "N/A")
        display_df["价差"] = display_df["价差"].apply(
            lambda x: f"{x:.1f}" if pd.notna(x) else "N/A"
        )
        display_df["基准价"] = display_df["基准价"].apply(
            lambda x: f"{x:.1f}"
        )
        display_df["期货价格"] = display_df["期货价格"].apply(
            lambda x: f"{x:.1f}"
        )
        st.dataframe(display_df, use_container_width=True, hide_index=True)
    else:
        st.warning("暂无贴水数据，请在交易时段查看。")

    # Trend chart
    st.subheader("贴水率走势")
    render_trend_chart(storage)

    # Position tracking
    if near_price is not None and not futures_df.empty:
        render_position_table(futures_df, near_price)

    # Auto-refresh during trading hours
    if is_trading_hours():
        time.sleep(refresh_interval)
        st.rerun()


if __name__ == "__main__":
    main()
