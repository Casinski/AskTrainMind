"""
reasoning.py — Mente locale AskTrainMind

Offline reasoning engine that produces a cohesive Italian-language HTML
narrative from the parsed workbook data, without any cloud API.

Input:  the selected FunctionRecord list and the ComparisonMatrix.
Output: a single unified HTML string ready for the DIFFERENZE panel.
"""
from __future__ import annotations

import difflib
from html import escape

from asktrainmind.app.comparison import ComparisonMatrix, ComparisonRow
from asktrainmind.app.excel_model import FunctionRecord
from asktrainmind.app.keyword_extractor import COMPONENT_RE, DOC_ID_RE

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _extract_codes(text: str) -> frozenset[str]:
    """Extract all component-like and doc-ID-like codes from *text*."""
    codes: set[str] = set()
    for m in COMPONENT_RE.finditer(text):
        codes.add(m.group(0).upper())
    for m in DOC_ID_RE.finditer(text):
        codes.add(m.group(0).upper())
    return frozenset(codes)


def _normalize(text: str) -> str:
    return " ".join(text.split()).casefold()


def _similarity(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, _normalize(a), _normalize(b)).ratio()


def _join_it(items: list[str]) -> str:
    """Italian-style list join."""
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    return ", ".join(items[:-1]) + f" e {items[-1]}"


def _is_component_row(label: str) -> bool:
    return "compon" in label.lower()


def _is_description_row(label: str) -> bool:
    return "descriz" in label.lower()


# ---------------------------------------------------------------------------
# Component-row analysis
# ---------------------------------------------------------------------------

def _analyze_component_row(
    row: ComparisonRow,
    config_names: list[str],
) -> str | None:
    """Return an Italian HTML paragraph for a component row, or None if empty."""
    per_config: dict[str, frozenset[str]] = {}
    missing: list[str] = []

    for cfg in config_names:
        cell = row.cells.get(cfg)
        if not cell or not cell.present or not cell.value:
            missing.append(cfg)
        else:
            per_config[cfg] = _extract_codes(cell.value)

    if not per_config:
        return None

    # Common components = intersection across all present configurations
    common: frozenset[str] = frozenset.intersection(*per_config.values())

    # Extra = each config's codes beyond the common set
    extras: dict[str, frozenset[str]] = {
        cfg: codes - common for cfg, codes in per_config.items()
    }

    label_esc = escape(row.label)
    parts: list[str] = []

    if common:
        parts.append(
            f"componenti comuni a tutte le configurazioni: "
            f"<b>{escape(', '.join(sorted(common)))}</b>"
        )

    for cfg in config_names:
        extra = sorted(extras.get(cfg, frozenset()))
        if extra:
            parts.append(
                f"{escape(cfg)} ha in più: <b>{escape(', '.join(extra))}</b>"
            )

    if missing:
        parts.append(
            f"dato assente per: {_join_it([escape(m) for m in missing])}"
        )

    if not parts:
        return None

    return (
        f"<p>📋 <b>{label_esc}</b>: "
        + "; ".join(parts)
        + ".</p>"
    )


# ---------------------------------------------------------------------------
# Description-row analysis
# ---------------------------------------------------------------------------

def _analyze_description_row(
    row: ComparisonRow,
    config_names: list[str],
) -> str | None:
    """Return an Italian HTML paragraph for a descriptive text row, or None if empty."""
    per_config: dict[str, str] = {}
    missing: list[str] = []

    for cfg in config_names:
        cell = row.cells.get(cfg)
        if not cell or not cell.present or not cell.value:
            missing.append(cfg)
        else:
            per_config[cfg] = cell.value

    if not per_config:
        return None

    label_esc = escape(row.label)
    cfg_list = list(per_config.keys())

    if len(cfg_list) == 1:
        cfg = cfg_list[0]
        snippet = escape(per_config[cfg][:250])
        return (
            f"<p>📝 <b>{label_esc}</b>: solo {escape(cfg)} riporta dati — "
            f"<i>{snippet}</i>.</p>"
        )

    # Compute pairwise similarity to classify the overall status
    pairs = [
        (cfg_list[i], cfg_list[j])
        for i in range(len(cfg_list))
        for j in range(i + 1, len(cfg_list))
    ]
    ratios = [_similarity(per_config[a], per_config[b]) for a, b in pairs]
    avg_ratio = sum(ratios) / len(ratios) if ratios else 1.0

    if avg_ratio >= 0.90:
        status = "uguale"
        verdict = "il testo è sostanzialmente identico tra le configurazioni"
    elif avg_ratio >= 0.60:
        status = "simile"
        verdict = "il testo presenta differenze parziali"
    else:
        status = "diverso"
        verdict = "il testo differisce significativamente tra le configurazioni"

    parts: list[str] = [f"stato <b>{escape(status)}</b> ({verdict})"]

    if status in ("simile", "diverso"):
        for cfg in cfg_list:
            snippet = escape(per_config[cfg][:250])
            parts.append(f"{escape(cfg)}: <i>{snippet}</i>")

    if missing:
        parts.append(f"dato assente per: {_join_it([escape(m) for m in missing])}")

    return (
        f"<p>📝 <b>{label_esc}</b>: "
        + "; ".join(parts)
        + ".</p>"
    )


# ---------------------------------------------------------------------------
# Generic (non-component, non-description) row
# ---------------------------------------------------------------------------

def _generic_row_paragraph(row: ComparisonRow, config_names: list[str]) -> str:
    """Fallback paragraph for rows that differ but have no special analysis."""
    groups: dict[str, tuple[str, list[str]]] = {}
    missing: list[str] = []

    for cfg in config_names:
        cell = row.cells.get(cfg)
        if not cell or not cell.present or not cell.value:
            missing.append(cfg)
            continue
        key = _normalize(cell.value)
        value, cfgs = groups.get(key, (cell.value, []))
        cfgs.append(cfg)
        groups[key] = (value, cfgs)

    label_esc = escape(row.label)
    pieces = [
        f"{_join_it([escape(c) for c in cfgs])}: <i>{escape(value)}</i>"
        for value, cfgs in groups.values()
    ]
    if missing:
        pieces.append(f"assente per {_join_it([escape(m) for m in missing])}")

    status_esc = escape(row.status)
    return (
        f"<p>🔹 <b>{label_esc}</b> [{status_esc}]: "
        + "; ".join(pieces)
        + ".</p>"
    )


# ---------------------------------------------------------------------------
# Cross-ID component references
# ---------------------------------------------------------------------------

def _cross_id_references(records: list[FunctionRecord]) -> dict[str, list[str]]:
    """
    Return a mapping ``{component_code: [record_id, ...]}`` for codes that
    appear in detail rows of two or more distinct records.
    """
    code_to_ids: dict[str, list[str]] = {}
    for record in records:
        record_codes: set[str] = set()
        for doc in record.documents:
            for detail in doc.details:
                for text in detail.values.values():
                    record_codes.update(_extract_codes(text))
        for code in record_codes:
            if code not in code_to_ids:
                code_to_ids[code] = []
            if record.id not in code_to_ids[code]:
                code_to_ids[code].append(record.id)

    return {code: ids for code, ids in code_to_ids.items() if len(ids) >= 2}


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def build_local_narrative(
    records: list[FunctionRecord],
    matrix: ComparisonMatrix,
) -> str:
    """
    Build a cohesive, human-readable Italian HTML narrative for the
    DIFFERENZE panel from the workbook data alone — no network, no API.
    """
    if not records:
        return "<p>Nessun record selezionato.</p>"

    cross_refs = _cross_id_references(records)

    paragraphs: list[str] = []

    # --- Intro ---
    ids_str = escape(", ".join(r.id for r in records))
    if len(records) == 1:
        funz_str = escape(records[0].funzione)
    else:
        funz_str = escape(f"{len(records)} funzioni selezionate")
    configs_str = escape(", ".join(matrix.config_names) or "nessuna")

    paragraphs.append(
        f"<p><b>Analisi locale AskTrainMind</b> — "
        f"ID <b>{ids_str}</b> ({funz_str}). "
        f"Configurazioni a confronto: {configs_str}.</p>"
    )

    # --- Per-record analysis ---
    for record in records:
        record_rows = [r for r in matrix.rows if r.record_id == record.id]

        comp_paras: list[str] = []
        desc_paras: list[str] = []
        other_paras: list[str] = []

        for row in record_rows:
            lbl_lower = row.label.lower()
            if _is_component_row(lbl_lower):
                p = _analyze_component_row(row, matrix.config_names)
                if p:
                    comp_paras.append(p)
            elif _is_description_row(lbl_lower):
                p = _analyze_description_row(row, matrix.config_names)
                if p:
                    desc_paras.append(p)
            else:
                if row.status != "uguale":
                    other_paras.append(
                        _generic_row_paragraph(row, matrix.config_names)
                    )

        if not (comp_paras or desc_paras or other_paras):
            # Nothing interesting — record is uniform across configs
            paragraphs.append(
                f"<p>Per la funzione <b>{escape(record.id)} — {escape(record.funzione)}</b> "
                "le configurazioni risultano equivalenti su tutte le voci analizzate.</p>"
            )
            continue

        paragraphs.append(
            f"<h4>Funzione {escape(record.id)} — {escape(record.funzione)}</h4>"
        )

        if comp_paras:
            paragraphs.append("<p><i>Componenti circuitali:</i></p>")
            paragraphs.extend(comp_paras)

        if desc_paras:
            paragraphs.append("<p><i>Descrizione circuitale:</i></p>")
            paragraphs.extend(desc_paras)

        if other_paras:
            paragraphs.append("<p><i>Altre voci con differenze:</i></p>")
            paragraphs.extend(other_paras)

    # --- Cross-ID references ---
    if cross_refs:
        paragraphs.append(
            "<p><b>Riferimenti incrociati tra funzioni selezionate:</b></p><ul>"
        )
        for code, ids in sorted(cross_refs.items()):
            ids_esc = escape(", ".join(ids))
            paragraphs.append(
                f"<li>Il codice <b>{escape(code)}</b> è presente in più funzioni: {ids_esc}.</li>"
            )
        paragraphs.append("</ul>")

    return "\n".join(paragraphs)
