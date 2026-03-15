from __future__ import annotations

from datetime import date
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

from .pipeline import LeftoverDetectionPipeline

# Hardcoded runtime configuration.
MENU_CSV_PATH = Path("data/menu.csv")
DB_PATH = Path("data/waste.db")
IMAGE_DIR = Path("data/images")
VLM_MODEL = "gpt-4.1"
LLM_MODEL = "gpt-4.1"
SUPPORTED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}


def _parse_filename_metadata(image_path: Path) -> tuple[date, str] | None:
    """Parse filenames like May-6-2025_3.jpg -> (2025-05-06, May-6-2025_3)."""
    stem = image_path.stem
    if "_" not in stem:
        return None

    date_part, data_id = stem.split("_", 1)
    if not data_id.strip():
        return None

    for fmt in ("%b-%d-%Y", "%B-%d-%Y"):
        try:
            served_date = datetime.strptime(date_part, fmt).date()
            return served_date, f"{date_part}_{data_id}"
        except ValueError:
            continue
    return None


def _list_images(image_dir: Path) -> list[Path]:
    if not image_dir.exists():
        return []
    return sorted(
        [p for p in image_dir.iterdir() if p.is_file() and p.suffix.lower() in SUPPORTED_IMAGE_EXTENSIONS]
    )


def main() -> None:
    load_dotenv()
    pipeline = LeftoverDetectionPipeline(
        menu_csv_path=MENU_CSV_PATH,
        db_path=DB_PATH,
        vlm_model=VLM_MODEL,
        llm_model=LLM_MODEL,
    )

    images = _list_images(IMAGE_DIR)
    if not images:
        print(f"No images found in {IMAGE_DIR}. Add files like May-6-2025_3.jpg")
        return

    processed_dates: list[date] = []
    for image_path in images:
        metadata = _parse_filename_metadata(image_path)
        if metadata is None:
            print(f"Skipped {image_path.name}: expected format like May-6-2025_3.jpg")
            continue

        served_date, plate_id = metadata
        try:
            analysis = pipeline.analyze_tray(
                plate_id=plate_id,
                image_path=image_path,
                served_date=served_date,
            )
            processed_dates.append(served_date)
        except Exception as exc:
            print(f"Failed {image_path.name}: {exc}")
            continue

        print(f"Saved analysis for plate {analysis.plate_id} ({analysis.served_date.isoformat()})")
        for food in analysis.foods:
            print(f"- {food.food_item}: {food.leftover_percent}% ({food.category})")

    if not processed_dates:
        print("No valid tray analyses were saved.")
        return

    print("")
    start_date = min(processed_dates)
    end_date = max(processed_dates)
    print(pipeline.generate_report(start_date=start_date, end_date=end_date))


if __name__ == "__main__":
    main()
