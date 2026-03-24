# storage.py
import sqlite3
from pathlib import Path

import pandas as pd


class BasisStorage:
    def __init__(self, db_path: str = "data/basis_history.db"):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
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
