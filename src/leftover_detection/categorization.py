from __future__ import annotations

import json

from openai import OpenAI

from .models import FoodCategoryOutput

FOOD_CATEGORIES = [
    "Leafy Vegetables",
    "Steamed Vegetables",
    "Raw Vegetables",
    "Root Vegetables",
    "Fried Proteins",
    "Grilled Proteins",
    "Plant Proteins",
    "Rice Dishes",
    "Noodle Dishes",
    "Soups and Stews",
    "Fruits",
    "Dairy",
    "Grain Dishes",
    "Other",
]


class FoodCategorizer:
    def classify_many(self, food_items: list[str]) -> dict[str, str]:
        raise NotImplementedError


class FallbackCategorizer(FoodCategorizer):
    def classify_many(self, food_items: list[str]) -> dict[str, str]:
        return {food: "Other" for food in food_items}


class OpenAIFoodCategorizer(FoodCategorizer):
    def __init__(self, client: OpenAI, model: str = "gpt-4.1-mini"):
        self.client = client
        self.model = model

    def classify_many(self, food_items: list[str]) -> dict[str, str]:
        unique_items = sorted({food.strip() for food in food_items if food.strip()})
        if not unique_items:
            return {}

        prompt = (
            "Classify each food into exactly one category from this list:\n"
            f"{', '.join(FOOD_CATEGORIES)}\n"
            "Return JSON only with schema:\n"
            '{"items":[{"food_item":"string","category":"string"}]}\n'
            "Rules:\n"
            "- Use only the provided category names.\n"
            "- If unsure, use Other.\n"
            f"Foods:\n{json.dumps(unique_items)}"
        )
        response = self.client.responses.create(
            model=self.model,
            input=[{"role": "user", "content": prompt}],
        )
        parsed = self._parse_json(response.output_text)
        output = FoodCategoryOutput.model_validate(parsed)

        mapping: dict[str, str] = {food: "Other" for food in unique_items}
        allowed = set(FOOD_CATEGORIES)
        for item in output.items:
            food_key = item.food_item.strip()
            if not food_key:
                continue
            category = item.category.strip()
            if category not in allowed:
                category = "Other"
            mapping[food_key] = category
        return mapping

    @staticmethod
    def _parse_json(text: str) -> dict:
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            start = text.find("{")
            end = text.rfind("}")
            if start == -1 or end == -1 or end <= start:
                raise ValueError(f"Categorizer did not return JSON. Raw output: {text}") from None
            return json.loads(text[start : end + 1])


def categorize_food(food_item: str) -> str:
    # Retained for compatibility in tests and simple local utility usage.
    return FallbackCategorizer().classify_many([food_item]).get(food_item, "Other")
