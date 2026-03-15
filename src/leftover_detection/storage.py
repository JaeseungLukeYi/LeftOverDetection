from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import date
from pathlib import Path

from .models import TrayAnalysis


class WasteDatabase:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    @contextmanager
    def _connection(self):
        conn = self._connect()
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _initialize(self) -> None:
        with self._connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS tray_analyses (
                    plate_id TEXT NOT NULL,
                    served_date TEXT NOT NULL,
                    food_item TEXT NOT NULL,
                    category TEXT NOT NULL,
                    leftover_percent INTEGER NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

    def save_analysis(self, analysis: TrayAnalysis) -> None:
        with self._connection() as conn:
            conn.executemany(
                """
                INSERT INTO tray_analyses
                (plate_id, served_date, food_item, category, leftover_percent)
                VALUES (?, ?, ?, ?, ?)
                """,
                [
                    (
                        analysis.plate_id,
                        analysis.served_date.isoformat(),
                        food.food_item,
                        food.category,
                        food.leftover_percent,
                    )
                    for food in analysis.foods
                ],
            )

    def aggregate_by_category(self, start_date: date, end_date: date) -> list[tuple[str, float, int]]:
        query = """
            SELECT category, AVG(leftover_percent) AS avg_leftover, COUNT(*) AS sample_count
            FROM tray_analyses
            WHERE served_date BETWEEN ? AND ?
            GROUP BY category
            ORDER BY avg_leftover DESC
        """
        with self._connection() as conn:
            rows = conn.execute(query, (start_date.isoformat(), end_date.isoformat())).fetchall()
        return [(str(category), float(avg_leftover), int(sample_count)) for category, avg_leftover, sample_count in rows]

    def aggregate_top_foods(self, start_date: date, end_date: date, limit: int = 5) -> list[tuple[str, float, int]]:
        query = """
            SELECT food_item, AVG(leftover_percent) AS avg_leftover, COUNT(*) AS sample_count
            FROM tray_analyses
            WHERE served_date BETWEEN ? AND ?
            GROUP BY food_item
            ORDER BY avg_leftover DESC
            LIMIT ?
        """
        with self._connection() as conn:
            rows = conn.execute(query, (start_date.isoformat(), end_date.isoformat(), limit)).fetchall()
        return [(str(food_item), float(avg_leftover), int(sample_count)) for food_item, avg_leftover, sample_count in rows]
