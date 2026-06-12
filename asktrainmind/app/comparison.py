from __future__ import annotations

from dataclasses import dataclass
from html import escape

from asktrainmind.app.excel_model import DetailRecord, DocumentRecord, FunctionRecord


@dataclass
class ConfigCell:
    present: bool
    value: str | None


@dataclass
class ComparisonRow:
    label: str
    record_id: str
    doc_id: str | None
    cells: dict[str, ConfigCell]
    all_equal: bool
    status: str


@dataclass
class ComparisonMatrix:
    config_names: list[str]
    rows: list[ComparisonRow]


def _normalize(value: str | None) -> str:
    if not value:
        return ""
    return " ".join(value.split()).casefold()


def _collect_config_names(records: list[FunctionRecord]) -> list[str]:
    names: list[str] = []
    for record in records:
        for config_name in getattr(record, "config_names", []):
            if config_name and config_name not in names:
                names.append(config_name)
        for doc in record.documents:
            for config_name in doc.config_links:
                if config_name and config_name not in names:
                    names.append(config_name)
            for detail in doc.details:
                for config_name in detail.values:
                    if config_name and config_name not in names:
                        names.append(config_name)
    return names


def _row_from_values(
    config_names: list[str],
    *,
    label: str,
    record_id: str,
    doc_id: str | None,
    values: dict[str, str],
) -> ComparisonRow:
    cells: dict[str, ConfigCell] = {}
    present_values: list[str] = []
    missing = False
    for config_name in config_names:
        raw = values.get(config_name, "")
        value = raw.strip() if isinstance(raw, str) else ""
        present = bool(value)
        if present:
            present_values.append(value)
            cells[config_name] = ConfigCell(present=True, value=value)
        else:
            missing = True
            cells[config_name] = ConfigCell(present=False, value=None)

    normalized = {_normalize(value) for value in present_values}
    all_equal = bool(present_values) and len(normalized) <= 1
    if missing:
        status = "parziale"
    elif all_equal:
        status = "uguale"
    else:
        status = "diverso"
    return ComparisonRow(
        label=label,
        record_id=record_id,
        doc_id=doc_id,
        cells=cells,
        all_equal=all_equal,
        status=status,
    )


def build_comparison_matrix(records: list[FunctionRecord]) -> ComparisonMatrix:
    config_names = _collect_config_names(records)
    rows: list[ComparisonRow] = []
    for record in records:
        for doc in record.documents:
            rows.append(
                _row_from_values(
                    config_names,
                    label=f"DOC {doc.doc_id} — link",
                    record_id=record.id,
                    doc_id=doc.doc_id,
                    values=doc.config_links,
                )
            )
            for detail in doc.details:
                rows.append(
                    _row_from_values(
                        config_names,
                        label=f"DOC {doc.doc_id} — {detail.title}",
                        record_id=record.id,
                        doc_id=doc.doc_id,
                        values=detail.values,
                    )
                )
    return ComparisonMatrix(config_names=config_names, rows=rows)


def _fmt_detail(detail: DetailRecord) -> str:
    parts = [f"{cfg}: {value}" for cfg, value in detail.values.items()]
    if not parts:
        return detail.title
    return f"{detail.title}: " + " | ".join(parts)


def matrix_to_plain_text(matrix: ComparisonMatrix) -> str:
    if not matrix.rows:
        return "Nessuna differenza disponibile."
    lines = ["Matrice differenze configurazioni:"]
    lines.append("Configurazioni: " + ", ".join(matrix.config_names))
    for row in matrix.rows:
        values = []
        for config_name in matrix.config_names:
            cell = row.cells.get(config_name)
            if cell and cell.present and cell.value is not None:
                values.append(f"{config_name}={cell.value}")
            else:
                values.append(f"{config_name}=∅")
        lines.append(f"- [{row.status}] {row.record_id} | {row.label} | " + " ; ".join(values))
    return "\n".join(lines)


def matrix_to_html_table(matrix: ComparisonMatrix) -> str:
    if not matrix.rows:
        return "<p class='diff-empty'>Nessuna differenza disponibile.</p>"
    head = ["<th>ID</th>", "<th>Voce</th>", "<th>Stato</th>"] + [
        f"<th>{escape(config_name)}</th>" for config_name in matrix.config_names
    ]
    rows_html = []
    for row in matrix.rows:
        cells_html = []
        for config_name in matrix.config_names:
            cell = row.cells.get(config_name, ConfigCell(present=False, value=None))
            if not cell.present:
                cells_html.append("<td class='cell-missing'>—</td>")
            else:
                cells_html.append(f"<td>{escape(cell.value or '')}</td>")
        rows_html.append(
            "<tr>"
            f"<td>{escape(row.record_id)}</td>"
            f"<td>{escape(row.label)}</td>"
            f"<td class='status status-{row.status}'>{escape(row.status.upper())}</td>"
            + "".join(cells_html)
            + "</tr>"
        )
    return (
        "<table class='diff-table'>"
        "<thead><tr>"
        + "".join(head)
        + "</tr></thead><tbody>"
        + "".join(rows_html)
        + "</tbody></table>"
    )


def _join_configs(configs: list[str]) -> str:
    if not configs:
        return ""
    if len(configs) == 1:
        return configs[0]
    return ", ".join(configs[:-1]) + f" e {configs[-1]}"


def matrix_to_narrative_html(matrix: ComparisonMatrix) -> str:
    if not matrix.rows:
        return "<p>Nessuna differenza disponibile.</p>"

    paragraphs = [
        "<p><b>Analisi comparativa deterministica:</b> confronto tra "
        f"{escape(', '.join(matrix.config_names))}.</p>"
    ]
    for row in matrix.rows:
        groups: dict[str, tuple[str, list[str]]] = {}
        missing: list[str] = []
        for config_name in matrix.config_names:
            cell = row.cells.get(config_name, ConfigCell(present=False, value=None))
            if not cell.present or not cell.value:
                missing.append(config_name)
                continue
            key = _normalize(cell.value)
            value, cfgs = groups.get(key, (cell.value, []))
            cfgs.append(config_name)
            groups[key] = (value, cfgs)

        topic = escape(f"{row.record_id} · {row.label}")
        if row.status == "uguale" and groups:
            value = escape(next(iter(groups.values()))[0])
            paragraphs.append(
                f"<p>Per <b>{topic}</b> lo stato è <b>uguale</b>: "
                f"le configurazioni {_join_configs(next(iter(groups.values()))[1])} riportano lo stesso contenuto "
                f"(<i>{value}</i>).</p>"
            )
            continue

        if row.status == "parziale":
            pieces = []
            for value, cfgs in groups.values():
                pieces.append(f"{_join_configs(cfgs)}: <i>{escape(value)}</i>")
            if missing:
                pieces.append(f"assenza dati per {_join_configs(missing)}")
            paragraphs.append(
                f"<p>Per <b>{topic}</b> lo stato è <b>parziale</b>: " + "; ".join(pieces) + ".</p>"
            )
            continue

        pieces = [f"{_join_configs(cfgs)}: <i>{escape(value)}</i>" for value, cfgs in groups.values()]
        paragraphs.append(
            f"<p>Per <b>{topic}</b> lo stato è <b>diverso</b>: " + "; ".join(pieces) + ".</p>"
        )

    return "\n".join(paragraphs)


def records_info_plain_text(records: list[FunctionRecord]) -> str:
    lines = ["Dettagli funzioni selezionate:"]
    for record in records:
        lines.append(f"ID {record.id} - {record.funzione}")
        for doc in record.documents:
            lines.append(f"  DOC {doc.doc_id}: {doc.info_doc}")
            for detail in doc.details:
                lines.append("    " + _fmt_detail(detail))
    return "\n".join(lines)
