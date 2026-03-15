from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from pydantic import BaseModel
from pydantic import Field


@dataclass(frozen=True)
class DetectedFood:
    food_item: str
    leftover_percent: int
    category: str


@dataclass(frozen=True)
class TrayAnalysis:
    plate_id: str
    served_date: date
    foods: list[DetectedFood]


@dataclass(frozen=True)
class MenuForDay:
    served_date: date
    dishes: list[str]


class VLMFoodItem(BaseModel):
    food_item: str = Field(min_length=1)
    leftover_percent: int = Field(ge=0, le=100)


class VLMDetectionOutput(BaseModel):
    foods: list[VLMFoodItem]


class LLMReportOutput(BaseModel):
    overview: str = Field(min_length=1)
    key_findings: list[str]
    recommendations: list[str]


class FoodCategoryItem(BaseModel):
    food_item: str = Field(min_length=1)
    category: str = Field(min_length=1)


class FoodCategoryOutput(BaseModel):
    items: list[FoodCategoryItem]
