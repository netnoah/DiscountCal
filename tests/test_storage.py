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
