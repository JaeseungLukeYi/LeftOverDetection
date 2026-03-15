from __future__ import annotations

import base64
import json
import mimetypes
from pathlib import Path

from openai import OpenAI

from .models import DetectedFood, MenuForDay
from .models import VLMDetectionOutput


class VLMClient:
    def __init__(self, client: OpenAI, model: str = "gpt-4.1"):
        self.client = client
        self.model = model

    def analyze_image(
        self,
        image_path: Path,
        menu: MenuForDay,
        reference_image_path: Path | None = None,
    ) -> list[DetectedFood]:
        if not image_path.exists():
            raise FileNotFoundError(f"Image file not found: {image_path}")
        if reference_image_path is not None and not reference_image_path.exists():
            raise FileNotFoundError(f"Reference image file not found: {reference_image_path}")

        image_data_url = self._to_data_url(image_path)
        reference_image_data_url = self._to_data_url(reference_image_path) if reference_image_path else None
        prompt = (
            "Analyze this top-down cafeteria tray image.\n"
            f"Today's menu: {', '.join(menu.dishes)}.\n"
            "Return JSON only with this schema:\n"
            "{"
            '"foods": ['
            '{"food_item": "string", "leftover_percent": "integer 0-100"}'
            "]"
            "}\n"
            "Rules:\n"
            "- Return all foods from today's menu exactly once.\n"
            "- Food names must be chosen only from today's menu list.\n"
            "- Use integer percentages.\n"
            "- If a food appears fully eaten or not visible, set leftover_percent to 0.\n"
        )
        if reference_image_data_url:
            prompt += (
                "You are also given a reference image of a full dish for the same date. "
                "Use it to infer foods that were fully eaten and set them to 0.\n"
            )

        content = [{"type": "input_text", "text": prompt}]
        if reference_image_data_url:
            content.append(
                {
                    "type": "input_text",
                    "text": "Reference image (full dish baseline for comparison):",
                }
            )
            content.append({"type": "input_image", "image_url": reference_image_data_url})
            content.append({"type": "input_text", "text": "Tray image to analyze:"})
        content.append({"type": "input_image", "image_url": image_data_url})

        response = self.client.responses.create(
            model=self.model,
            input=[
                {
                    "role": "user",
                    "content": content,
                }
            ],
        )
        payload = self._parse_json(response.output_text)
        parsed = VLMDetectionOutput.model_validate(payload)
        detections: list[DetectedFood] = []
        for item in parsed.foods:
            food_item = item.food_item.strip()
            if not food_item:
                continue
            detections.append(
                DetectedFood(food_item=food_item, leftover_percent=item.leftover_percent, category="")
            )
        return detections

    @staticmethod
    def _to_data_url(image_path: Path) -> str:
        mime_type, _ = mimetypes.guess_type(image_path.name)
        if mime_type is None:
            mime_type = "image/jpeg"
        encoded = base64.b64encode(image_path.read_bytes()).decode("utf-8")
        return f"data:{mime_type};base64,{encoded}"

    @staticmethod
    def _parse_json(text: str) -> dict:
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            start = text.find("{")
            end = text.rfind("}")
            if start == -1 or end == -1 or end <= start:
                raise ValueError(f"VLM did not return JSON. Raw output: {text}") from None
            return json.loads(text[start : end + 1])
