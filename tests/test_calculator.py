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

    def test_sorts_by_delivery_date_ascending(self):
        futures_df = self._make_futures_df()
        today = date(2025, 3, 20)
        result = calculate_basis_table(
            futures_df=futures_df,
            spot_price=800.0,
            reference_date=today,
        )
        days = result["days_to_delivery"].tolist()
        assert days == sorted(days)

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
