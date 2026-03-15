from __future__ import annotations

import json
from datetime import date

from openai import OpenAI

from .models import LLMReportOutput


class LLMReportClient:
    def __init__(self, client: OpenAI, model: str = "gpt-4.1"):
        self.client = client
        self.model = model

    def generate_structured_report(
        self,
        category_rows: list[tuple[str, float, int]],
        top_food_rows: list[tuple[str, float, int]],
        start_date: date,
        end_date: date,
    ) -> LLMReportOutput:
        if not category_rows:
            return LLMReportOutput(
                overview=f"No tray records were found for {start_date.isoformat()} to {end_date.isoformat()}.",
                key_findings=[],
                recommendations=["Collect more tray images for this date range before drawing conclusions."],
            )

        payload = {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "category_stats": [
                {"category": c, "avg_leftover_percent": a, "sample_count": n}
                for c, a, n in category_rows
            ],
            "top_food_stats": [
                {"food_item": f, "avg_leftover_percent": a, "sample_count": n}
                for f, a, n in top_food_rows
            ],
        }

        overview = self._build_overview(category_rows, start_date, end_date)
        key_findings = self._build_key_findings(category_rows, top_food_rows)
        recommendations = self._generate_recommendations(payload)

        return LLMReportOutput(
            overview=overview,
            key_findings=key_findings,
            recommendations=recommendations,
        )

    def _generate_recommendations(self, payload: dict) -> list[str]:
        response = self.client.responses.create(
            model=self.model,
            input=[
                {
                    "role": "system",
                    "content": (
                        "You are a school cafeteria food-waste analyst. "
                        "Provide concise, practical recommendations only."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        "Return JSON only using this schema:\n"
                        '{"recommendations": ["string"]}\n'
                        "Rules:\n"
                        "- Return exactly 3 recommendations.\n"
                        "- Do not include any numeric claims unless explicitly present in the input data.\n"
                        "- Focus on actionable cafeteria interventions.\n"
                        f"Data:\n{json.dumps(payload)}"
                    ),
                },
            ],
        )
        parsed = self._parse_json(response.output_text)
        recommendations = parsed.get("recommendations", [])
        if not isinstance(recommendations, list):
            return ["Review menu design and serving strategy using observed waste patterns."]
        cleaned = [str(item).strip() for item in recommendations if str(item).strip()]
        return cleaned[:3] or ["Review menu design and serving strategy using observed waste patterns."]

    def generate_report(
        self,
        category_rows: list[tuple[str, float, int]],
        top_food_rows: list[tuple[str, float, int]],
        start_date: date,
        end_date: date,
    ) -> str:
        report = self.generate_structured_report(
            category_rows=category_rows,
            top_food_rows=top_food_rows,
            start_date=start_date,
            end_date=end_date,
        )
        lines = [f"Food waste analysis for {start_date.isoformat()} to {end_date.isoformat()}", ""]
        lines.append(f"Overview: {report.overview}")
        lines.append("")
        lines.append("Key Findings:")
        if report.key_findings:
            lines.extend(f"- {line}" for line in report.key_findings)
        else:
            lines.append("- No findings yet.")
        lines.append("")
        lines.append("Recommendations:")
        lines.extend(f"- {line}" for line in report.recommendations)
        return "\n".join(lines)

    @staticmethod
    def _build_overview(
        category_rows: list[tuple[str, float, int]],
        start_date: date,
        end_date: date,
    ) -> str:
        highest = category_rows[0]
        lowest = category_rows[-1]
        return (
            f"For {start_date.isoformat()} to {end_date.isoformat()}, highest average waste was in "
            f"{highest[0]} ({highest[1]:.1f}% across {highest[2]} records), while lowest was "
            f"{lowest[0]} ({lowest[1]:.1f}% across {lowest[2]} records)."
        )

    @staticmethod
    def _build_key_findings(
        category_rows: list[tuple[str, float, int]],
        top_food_rows: list[tuple[str, float, int]],
    ) -> list[str]:
        findings = [
            f"{category}: {avg:.1f}% average leftover across {count} records."
            for category, avg, count in category_rows[:3]
        ]
        findings.extend(
            f"{food}: {avg:.1f}% average leftover across {count} records."
            for food, avg, count in top_food_rows[:2]
        )
        return findings

    @staticmethod
    def _parse_json(text: str) -> dict:
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            start = text.find("{")
            end = text.rfind("}")
            if start == -1 or end == -1 or end <= start:
                raise ValueError(f"LLM did not return JSON. Raw output: {text}") from None
            return json.loads(text[start : end + 1])
