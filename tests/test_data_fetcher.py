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
                            lambda symbol: (_ for _ in ()).throw(Exception("network error")))
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
                            lambda date, vars_list: (_ for _ in ()).throw(Exception("network error")))
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
                            lambda symbol, market, adjust: (_ for _ in ()).throw(Exception("network error")))
        result = fetch_futures_quotes(["I2605"])
        assert result.empty
