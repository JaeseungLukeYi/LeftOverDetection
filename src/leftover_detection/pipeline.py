from __future__ import annotations

from collections import defaultdict
from difflib import get_close_matches
import os
from datetime import date
from pathlib import Path

from openai import OpenAI

from .categorization import FallbackCategorizer
from .categorization import FoodCategorizer
from .categorization import OpenAIFoodCategorizer
from .llm import LLMReportClient
from .menu import MenuRepository
from .models import DetectedFood, TrayAnalysis
from .models import LLMReportOutput
from .storage import WasteDatabase
from .vlm import VLMClient


class LeftoverDetectionPipeline:
    def __init__(
        self,
        menu_csv_path: Path,
        db_path: Path,
        openai_api_key: str | None = None,
        vlm_model: str = "gpt-4.1",
        llm_model: str = "gpt-4.1",
        category_model: str = "gpt-4.1-mini",
        vlm_client: VLMClient | None = None,
        llm_client: LLMReportClient | None = None,
        categorizer: FoodCategorizer | None = None,
    ):
        self.menu_repo = MenuRepository(menu_csv_path)
        self.db = WasteDatabase(db_path)
        api_key = openai_api_key or os.getenv("OPENAI_API_KEY")
        if not api_key and (vlm_client is None or llm_client is None):
            raise ValueError("OPENAI_API_KEY is required. Set it in .env or pass openai_api_key.")

        openai_client = OpenAI(api_key=api_key) if api_key else None
        self.vlm = vlm_client or VLMClient(client=openai_client, model=vlm_model)
        self.llm = llm_client or LLMReportClient(client=openai_client, model=llm_model)
        if categorizer is not None:
            self.categorizer = categorizer
        elif openai_client is not None:
            self.categorizer = OpenAIFoodCategorizer(client=openai_client, model=category_model)
        else:
            self.categorizer = FallbackCategorizer()

    def analyze_tray(
        self,
        plate_id: str,
        image_path: Path,
        served_date: date,
        reference_image_path: Path | None = None,
    ) -> TrayAnalysis:
        menu = self.menu_repo.get_menu(served_date)
        detections = self.vlm.analyze_image(
            image_path=image_path,
            menu=menu,
            reference_image_path=reference_image_path,
        )

        leftover_by_food: dict[str, int] = {}
        for detection in detections:
            matched_food = self._match_to_menu_item(detection.food_item, menu.dishes)
            if matched_food is not None:
                leftover_by_food[matched_food] = max(0, min(100, detection.leftover_percent))

        # Ensure every served menu item is represented. Missing items are treated as fully eaten.
        for dish in menu.dishes:
            leftover_by_food.setdefault(dish, 0)

        matched_foods = list(leftover_by_food.keys())
        category_map = self.categorizer.classify_many(matched_foods)

        normalized: list[DetectedFood] = []
        for matched_food in menu.dishes:
            normalized.append(
                DetectedFood(
                    food_item=matched_food,
                    leftover_percent=leftover_by_food.get(matched_food, 0),
                    category=category_map.get(matched_food, "Other"),
                )
            )

        analysis = TrayAnalysis(plate_id=plate_id, served_date=served_date, foods=normalized)
        self.db.save_analysis(analysis)
        return analysis

    def generate_report(self, start_date: date, end_date: date) -> str:
        categories = self.db.aggregate_by_category(start_date=start_date, end_date=end_date)
        top_foods = self.db.aggregate_top_foods(start_date=start_date, end_date=end_date)
        return self.llm.generate_report(
            category_rows=categories,
            top_food_rows=top_foods,
            start_date=start_date,
            end_date=end_date,
        )

    def generate_structured_report(self, start_date: date, end_date: date) -> LLMReportOutput:
        categories = self.db.aggregate_by_category(start_date=start_date, end_date=end_date)
        top_foods = self.db.aggregate_top_foods(start_date=start_date, end_date=end_date)
        return self.llm.generate_structured_report(
            category_rows=categories,
            top_food_rows=top_foods,
            start_date=start_date,
            end_date=end_date,
        )

    def generate_structured_report_from_analyses(
        self,
        analyses: list[TrayAnalysis],
        start_date: date,
        end_date: date,
    ) -> LLMReportOutput:
        category_values: dict[str, list[int]] = defaultdict(list)
        food_values: dict[str, list[int]] = defaultdict(list)

        for analysis in analyses:
            for food in analysis.foods:
                category_values[food.category].append(food.leftover_percent)
                food_values[food.food_item].append(food.leftover_percent)

        category_rows = sorted(
            [
                (category, sum(values) / len(values), len(values))
                for category, values in category_values.items()
            ],
            key=lambda x: x[1],
            reverse=True,
        )
        food_rows = sorted(
            [
                (food_item, sum(values) / len(values), len(values))
                for food_item, values in food_values.items()
            ],
            key=lambda x: x[1],
            reverse=True,
        )[:5]

        return self.llm.generate_structured_report(
            category_rows=category_rows,
            top_food_rows=food_rows,
            start_date=start_date,
            end_date=end_date,
        )

    @staticmethod
    def _match_to_menu_item(predicted_food: str, menu_items: list[str]) -> str | None:
        predicted = predicted_food.strip().lower()
        if not predicted:
            return None

        exact = {item.lower(): item for item in menu_items}
        if predicted in exact:
            return exact[predicted]

        close = get_close_matches(predicted, exact.keys(), n=1, cutoff=0.72)
        if close:
            return exact[close[0]]
        return None
