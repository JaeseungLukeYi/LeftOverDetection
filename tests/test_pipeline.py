import unittest
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory

from leftover_detection.pipeline import LeftoverDetectionPipeline
from leftover_detection.models import DetectedFood


class PipelineTests(unittest.TestCase):
    def test_pipeline_end_to_end(self):
        class FakeVLMClient:
            def analyze_image(self, image_path, menu, reference_image_path=None):
                return [
                    DetectedFood(food_item=menu.dishes[0], leftover_percent=80, category=""),
                    DetectedFood(food_item=menu.dishes[1], leftover_percent=10, category=""),
                ]

        class FakeLLMClient:
            def generate_report(self, category_rows, top_food_rows, start_date, end_date):
                return (
                    f"Food waste analysis for {start_date.isoformat()} to {end_date.isoformat()}\n"
                    f"Rows: {len(category_rows)} categories, {len(top_food_rows)} foods"
                )

        with TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            menu = tmp_path / "menu.csv"
            menu.write_text(
                "Date,Dish 1,Dish 2\n"
                "2026-03-08,Spaghetti,Broccoli\n",
                encoding="utf-8",
            )

            image = tmp_path / "tray.jpg"
            image.write_bytes(b"fake")

            db_path = tmp_path / "waste.db"
            pipeline = LeftoverDetectionPipeline(
                menu_csv_path=menu,
                db_path=db_path,
                vlm_client=FakeVLMClient(),
                llm_client=FakeLLMClient(),
            )

            analysis = pipeline.analyze_tray(
                plate_id="P1",
                image_path=image,
                served_date=date(2026, 3, 8),
            )
            self.assertEqual(analysis.plate_id, "P1")
            self.assertGreaterEqual(len(analysis.foods), 1)

            report = pipeline.generate_report(start_date=date(2026, 3, 8), end_date=date(2026, 3, 8))
            self.assertIn("Food waste analysis", report)


if __name__ == "__main__":
    unittest.main()
