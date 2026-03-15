from __future__ import annotations

import csv
from datetime import date, datetime
from pathlib import Path

from .models import MenuForDay


class MenuRepository:
    def __init__(self, menu_csv_path: Path):
        self.menu_csv_path = menu_csv_path

    def get_menu(self, served_date: date) -> MenuForDay:
        if not self.menu_csv_path.exists():
            raise FileNotFoundError(f"Menu file not found: {self.menu_csv_path}")

        with self.menu_csv_path.open("r", encoding="utf-8", newline="") as fp:
            reader = csv.DictReader(fp)
            for row in reader:
                row_date = datetime.strptime(row["Date"], "%Y-%m-%d").date()
                if row_date == served_date:
                    dishes = [value.strip() for key, value in row.items() if key != "Date" and value and value.strip()]
                    return MenuForDay(served_date=served_date, dishes=dishes)

        raise ValueError(f"No menu entry found for {served_date.isoformat()}")
