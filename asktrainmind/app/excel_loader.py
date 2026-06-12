from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from asktrainmind.app.excel_model import FunctionRecord, parse_funzioni_sheet
from asktrainmind.app.image_extractor import WorkbookImage, extract_images


@dataclass
class LoadedWorkbook:
    path: Path
    records: list[FunctionRecord]
    images: list[WorkbookImage]


def load_excel_data(path: str | Path) -> LoadedWorkbook:
    path = Path(path)
    records = parse_funzioni_sheet(path)
    images = extract_images(path)
    return LoadedWorkbook(path=path, records=records, images=images)
