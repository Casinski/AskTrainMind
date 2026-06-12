from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from openpyxl import load_workbook
from openpyxl.cell.cell import Cell


@dataclass
class DetailRecord:
    title: str
    values: dict[str, str]


@dataclass
class DocumentRecord:
    doc_id: str
    info_doc: str
    config_links: dict[str, str]
    details: list[DetailRecord] = field(default_factory=list)


@dataclass
class FunctionRecord:
    id: str
    funzione: str
    tipo: str
    generale_link: str | None
    start_row: int = 0
    end_row: int = 0
    config_names: list[str] = field(default_factory=list)
    documents: list[DocumentRecord] = field(default_factory=list)


class WorkbookParseError(RuntimeError):
    pass


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _formula_text(cell: Cell) -> str:
    value = cell.value
    if hasattr(value, "text"):
        return str(getattr(value, "text", "") or "")
    if isinstance(value, str):
        return value
    if cell.data_type == "f" and isinstance(cell._value, str):
        return cell._value
    return ""


def _extract_link(cell: Cell) -> str:
    if cell.hyperlink and cell.hyperlink.target:
        return str(cell.hyperlink.target)

    formula = _formula_text(cell)
    if not formula:
        return _text(cell.value)

    m = re.search(r'HYPERLINK\("([^"]+)"', formula, flags=re.IGNORECASE)
    if m:
        return m.group(1)

    m = re.search(r'CONCATENATE\("([^"]+)"\s*,\s*\$D\d+\)', formula, flags=re.IGNORECASE)
    if m:
        doc_id = _text(cell.parent.cell(row=cell.row, column=4).value)
        return f"{m.group(1)}{doc_id}" if doc_id else m.group(1)

    if formula.startswith("="):
        return formula
    return _text(cell.value)


def parse_funzioni_sheet(workbook_path: Path | str, sheet_name: str = "Funzioni") -> list[FunctionRecord]:
    wb = load_workbook(filename=workbook_path, data_only=False)
    if sheet_name not in wb.sheetnames:
        raise WorkbookParseError(f"Foglio '{sheet_name}' non trovato")

    ws = wb[sheet_name]
    header_map: dict[str, int] = {}
    for col in range(1, ws.max_column + 1):
        header = _text(ws.cell(1, col).value).lower()
        if header:
            header_map[header] = col

    id_col = header_map.get("id", 1)
    funzione_col = header_map.get("funzione", 2)
    tipo_col = next((c for h, c in header_map.items() if h.startswith("tipo")), 3)
    doc_id_col = next((c for h, c in header_map.items() if h.startswith("doc id")), 4)
    info_col = next((c for h, c in header_map.items() if h.startswith("info doc")), 5)
    generale_col = next((c for h, c in header_map.items() if h.startswith("generale")), ws.max_column)

    config_cols = list(range(info_col + 1, generale_col))
    config_names = {
        col: _text(ws.cell(1, col).value).replace("\n", " / ") or f"CONF_{col}"
        for col in config_cols
    }
    ordered_config_names = [config_names[col] for col in config_cols]

    records: list[FunctionRecord] = []
    current_function: FunctionRecord | None = None
    current_document: DocumentRecord | None = None

    for row in range(2, ws.max_row + 1):
        row_id = _text(ws.cell(row, id_col).value)
        row_funzione = _text(ws.cell(row, funzione_col).value)
        row_tipo = _text(ws.cell(row, tipo_col).value)
        row_doc_id = _text(ws.cell(row, doc_id_col).value)
        row_info = _text(ws.cell(row, info_col).value)

        if row_id and row_funzione:
            if current_function:
                current_function.end_row = max(current_function.end_row, row - 1)
            current_document = None
            current_function = FunctionRecord(
                id=row_id,
                funzione=row_funzione,
                tipo=row_tipo,
                generale_link=_extract_link(ws.cell(row, generale_col)) or None,
                start_row=row,
                end_row=row,
                config_names=ordered_config_names.copy(),
            )
            records.append(current_function)
            continue

        if not current_function:
            continue

        current_function.end_row = row

        if row_doc_id and row_info:
            config_links = {
                config_names[col]: _extract_link(ws.cell(row, col))
                for col in config_cols
                if _extract_link(ws.cell(row, col))
            }
            current_document = DocumentRecord(doc_id=row_doc_id, info_doc=row_info, config_links=config_links)
            current_function.documents.append(current_document)
            continue

        if current_document and row_info:
            values = {
                config_names[col]: _text(ws.cell(row, col).value)
                for col in config_cols
                if _text(ws.cell(row, col).value)
            }
            if values:
                current_document.details.append(DetailRecord(title=row_info, values=values))

    return records
