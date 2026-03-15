from __future__ import annotations

import re
from datetime import date
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi import File
from fastapi import HTTPException
from fastapi import Request
from fastapi import UploadFile
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .pipeline import LeftoverDetectionPipeline

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent.parent
MENU_CSV_PATH = PROJECT_ROOT / "data" / "menu.csv"
DB_PATH = PROJECT_ROOT / "data" / "waste.db"
UPLOAD_DIR = PROJECT_ROOT / "data" / "uploads"
REFERENCE_DIR = PROJECT_ROOT / "data" / "references"
VLM_MODEL = "gpt-4.1"
LLM_MODEL = "gpt-4.1"
SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
FILENAME_PATTERN = re.compile(r"^(?P<month>[A-Za-z]+)-(?P<day>\d{1,2})-(?P<year>\d{4})_(?P<id>.+)$")

load_dotenv(PROJECT_ROOT / ".env")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
REFERENCE_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="AI Food Waste Detection")
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
_pipeline: LeftoverDetectionPipeline | None = None


def _get_pipeline() -> LeftoverDetectionPipeline:
    global _pipeline
    if _pipeline is None:
        _pipeline = LeftoverDetectionPipeline(
            menu_csv_path=MENU_CSV_PATH,
            db_path=DB_PATH,
            vlm_model=VLM_MODEL,
            llm_model=LLM_MODEL,
        )
    return _pipeline


def _parse_filename_metadata(file_name: str) -> tuple[date, str]:
    stem = Path(file_name).stem
    match = FILENAME_PATTERN.match(stem)
    if not match:
        raise ValueError("Expected format Month-Day-Year_id, e.g. May-7-2026_3.jpg")

    month = match.group("month")
    day = match.group("day")
    year = match.group("year")
    plate_suffix = match.group("id").strip()
    if not plate_suffix:
        raise ValueError("Plate id is missing after underscore.")

    served_date = None
    for fmt in ("%b-%d-%Y", "%B-%d-%Y"):
        try:
            served_date = datetime.strptime(f"{month}-{day}-{year}", fmt).date()
            break
        except ValueError:
            continue

    if served_date is None:
        raise ValueError("Invalid date in filename. Use formats like May-7-2026_3.jpg")

    plate_id = f"{month}-{day}-{year}_{plate_suffix}"
    return served_date, plate_id


def _is_reference_file(file_name: str) -> bool:
    stem = Path(file_name).stem
    if "_" not in stem:
        return False
    suffix = stem.split("_", 1)[1].strip().lower()
    return suffix == "reference"


def _load_reference_images_from_folder() -> dict[date, Path]:
    reference_by_date: dict[date, Path] = {}
    for image_path in sorted(REFERENCE_DIR.iterdir()):
        if not image_path.is_file():
            continue
        if image_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            continue
        if not _is_reference_file(image_path.name):
            continue
        try:
            served_date, _ = _parse_filename_metadata(image_path.name)
        except Exception:
            continue
        reference_by_date[served_date] = image_path
    return reference_by_date


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/api/analyze")
async def analyze_trays(files: list[UploadFile] = File(...)):
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded")

    results = []
    processed_dates: list[date] = []
    processed_analyses = []
    pipeline = _get_pipeline()
    reference_by_date: dict[date, Path] = _load_reference_images_from_folder()

    # First pass: persist reference images by date.
    for uploaded in files:
        file_name = uploaded.filename or ""
        suffix = Path(file_name).suffix.lower()
        if suffix not in SUPPORTED_EXTENSIONS:
            continue
        if not _is_reference_file(file_name):
            continue
        try:
            served_date, _ = _parse_filename_metadata(file_name)
            image_path = REFERENCE_DIR / Path(file_name).name
            data = await uploaded.read()
            image_path.write_bytes(data)
            reference_by_date[served_date] = image_path
            results.append(
                {
                    "file": file_name,
                    "status": "ok",
                    "type": "reference",
                    "served_date": served_date.isoformat(),
                    "message": "Reference image registered.",
                }
            )
        except Exception as exc:
            results.append(
                {
                    "file": file_name,
                    "status": "error",
                    "type": "reference",
                    "error": str(exc),
                }
            )

    for uploaded in files:
        suffix = Path(uploaded.filename or "").suffix.lower()
        if suffix not in SUPPORTED_EXTENSIONS:
            results.append(
                {
                    "file": uploaded.filename,
                    "status": "error",
                    "error": f"Unsupported extension: {suffix}",
                }
            )
            continue

        if _is_reference_file(uploaded.filename or ""):
            continue

        try:
            served_date, plate_id = _parse_filename_metadata(uploaded.filename or "")
            image_path = UPLOAD_DIR / Path(uploaded.filename).name
            data = await uploaded.read()
            image_path.write_bytes(data)
            reference_image_path = reference_by_date.get(served_date)

            analysis = pipeline.analyze_tray(
                plate_id=plate_id,
                image_path=image_path,
                served_date=served_date,
                reference_image_path=reference_image_path,
            )
            processed_dates.append(served_date)
            processed_analyses.append(analysis)
            results.append(
                {
                    "file": uploaded.filename,
                    "status": "ok",
                    "type": "tray",
                    "plate_id": analysis.plate_id,
                    "served_date": analysis.served_date.isoformat(),
                    "reference_used": reference_image_path.name if reference_image_path else None,
                    "foods": [
                        {
                            "food_item": f.food_item,
                            "leftover_percent": f.leftover_percent,
                            "category": f.category,
                        }
                        for f in analysis.foods
                    ],
                }
            )
        except Exception as exc:
            results.append(
                {
                    "file": uploaded.filename,
                    "status": "error",
                    "type": "tray",
                    "error": str(exc),
                }
            )

    if not processed_dates:
        return {"results": results, "report": None}

    start_date = min(processed_dates)
    end_date = max(processed_dates)
    report = pipeline.generate_structured_report_from_analyses(
        analyses=processed_analyses,
        start_date=start_date,
        end_date=end_date,
    )

    return {
        "results": results,
        "report_range": {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
        },
        "report": report.model_dump(),
    }


@app.get("/api/report")
def get_report(start_date: str, end_date: str):
    try:
        parsed_start = datetime.strptime(start_date, "%Y-%m-%d").date()
        parsed_end = datetime.strptime(end_date, "%Y-%m-%d").date()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Dates must use YYYY-MM-DD") from exc

    report = _get_pipeline().generate_structured_report(start_date=parsed_start, end_date=parsed_end)
    return {
        "start_date": parsed_start.isoformat(),
        "end_date": parsed_end.isoformat(),
        "report": report.model_dump(),
    }
