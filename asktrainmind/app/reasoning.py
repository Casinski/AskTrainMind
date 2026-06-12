"""
reasoning.py — Mente locale AskTrainMind

Offline reasoning engine that produces a cohesive Italian-language HTML
narrative from the parsed workbook data, without any cloud API.

Input:  the selected FunctionRecord list and the ComparisonMatrix.
Output: a single unified HTML string ready for the DIFFERENZE panel.

Public API:
- analyze_records(records, matrix) -> LocalAnalysis  (structured intermediate)
- render_detailed_html(analysis) -> str              (hidden sub-section HTML)
- build_overall_discussion(analysis) -> str          (visible prose HTML)
- build_local_narrative(records, matrix) -> str      (backward-compat, delegates)
"""
from __future__ import annotations

import difflib
from dataclasses import dataclass, field
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
# Structured intermediate model
# ---------------------------------------------------------------------------

@dataclass
class TopicFinding:
    """Analysis findings for one detail row (e.g. 'Componenti circuito elettrico')."""
    label: str
    kind: str  # 'componenti' | 'descrizione' | 'rif_pagina' | 'altro'
    status: str  # 'uguale' | 'parziale' | 'diverso'
    common: list[str] = field(default_factory=list)
    per_config_extra: dict[str, list[str]] = field(default_factory=dict)
    per_config_text: dict[str, str] = field(default_factory=dict)
    missing_configs: list[str] = field(default_factory=list)


@dataclass
class RecordAnalysis:
    """Analysis results for one FunctionRecord."""
    record_id: str
    funzione: str
    doc_ids: list[str]
    topic_findings: list[TopicFinding] = field(default_factory=list)


@dataclass
class LocalAnalysis:
    """Full structured analysis output for the selected records."""
    config_names: list[str]
    record_analyses: list[RecordAnalysis]
    cross_id_refs: dict[str, list[str]]  # code → [record_id, …]


def _build_topic_finding(row: ComparisonRow, config_names: list[str]) -> TopicFinding:
    """Convert a ComparisonRow into a TopicFinding."""
    lbl_lower = row.label.lower()
    if _is_component_row(lbl_lower):
        kind = "componenti"
    elif _is_description_row(lbl_lower):
        kind = "descrizione"
    elif "rif" in lbl_lower and "pag" in lbl_lower:
        kind = "rif_pagina"
    else:
        kind = "altro"

    per_config_text: dict[str, str] = {}
    per_config_codes: dict[str, frozenset[str]] = {}
    missing: list[str] = []

    for cfg in config_names:
        cell = row.cells.get(cfg)
        if not cell or not cell.present or not cell.value:
            missing.append(cfg)
        else:
            per_config_text[cfg] = cell.value
            if kind == "componenti":
                per_config_codes[cfg] = _extract_codes(cell.value)

    common_list: list[str] = []
    per_config_extra: dict[str, list[str]] = {}

    if kind == "componenti" and per_config_codes:
        common = frozenset.intersection(*per_config_codes.values()) if per_config_codes else frozenset()
        common_list = sorted(common)
        for cfg, codes in per_config_codes.items():
            extra = sorted(codes - common)
            if extra:
                per_config_extra[cfg] = extra

    return TopicFinding(
        label=row.label,
        kind=kind,
        status=row.status,
        common=common_list,
        per_config_extra=per_config_extra,
        per_config_text=per_config_text,
        missing_configs=missing,
    )


def analyze_records(
    records: list[FunctionRecord],
    matrix: ComparisonMatrix,
) -> LocalAnalysis:
    """
    Build a structured ``LocalAnalysis`` from the selected records and the
    comparison matrix.  This is the single source of truth for both
    ``render_detailed_html`` and ``build_overall_discussion``.
    """
    record_analyses: list[RecordAnalysis] = []
    for record in records:
        record_rows = [r for r in matrix.rows if r.record_id == record.id]
        findings: list[TopicFinding] = []
        for row in record_rows:
            tf = _build_topic_finding(row, matrix.config_names)
            findings.append(tf)
        ra = RecordAnalysis(
            record_id=record.id,
            funzione=record.funzione,
            doc_ids=[d.doc_id for d in record.documents],
            topic_findings=findings,
        )
        record_analyses.append(ra)

    return LocalAnalysis(
        config_names=matrix.config_names,
        record_analyses=record_analyses,
        cross_id_refs=_cross_id_references(records),
    )


# ---------------------------------------------------------------------------
# Detailed HTML renderer (hidden sub-section)
# ---------------------------------------------------------------------------

def render_detailed_html(analysis: LocalAnalysis) -> str:
    """
    Render the structured analysis as the detailed HTML sub-section
    (equivalent to the former ``build_local_narrative`` output).
    """
    if not analysis.record_analyses:
        return "<p>Nessun record selezionato.</p>"

    config_names = analysis.config_names
    cross_refs = analysis.cross_id_refs
    paragraphs: list[str] = []

    ids_str = escape(", ".join(ra.record_id for ra in analysis.record_analyses))
    if len(analysis.record_analyses) == 1:
        funz_str = escape(analysis.record_analyses[0].funzione)
    else:
        funz_str = escape(f"{len(analysis.record_analyses)} funzioni selezionate")
    configs_str = escape(", ".join(config_names) or "nessuna")

    paragraphs.append(
        f"<p><b>Analisi locale AskTrainMind</b> — "
        f"ID <b>{ids_str}</b> ({funz_str}). "
        f"Configurazioni a confronto: {configs_str}.</p>"
    )

    for ra in analysis.record_analyses:
        comp_paras: list[str] = []
        desc_paras: list[str] = []
        other_paras: list[str] = []

        for tf in ra.topic_findings:
            if tf.kind == "componenti":
                p = _tf_component_html(tf, config_names)
                if p:
                    comp_paras.append(p)
            elif tf.kind == "descrizione":
                p = _tf_description_html(tf, config_names)
                if p:
                    desc_paras.append(p)
            else:
                if tf.status != "uguale":
                    p = _tf_generic_html(tf, config_names)
                    if p:
                        other_paras.append(p)

        if not (comp_paras or desc_paras or other_paras):
            paragraphs.append(
                f"<p>Per la funzione <b>{escape(ra.record_id)} — {escape(ra.funzione)}</b> "
                "le configurazioni risultano equivalenti su tutte le voci analizzate.</p>"
            )
            continue

        paragraphs.append(
            f"<h4>Funzione {escape(ra.record_id)} — {escape(ra.funzione)}</h4>"
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


def _tf_component_html(tf: TopicFinding, config_names: list[str]) -> str | None:
    parts: list[str] = []
    label_esc = escape(tf.label)
    if tf.common:
        parts.append(
            f"componenti comuni a tutte le configurazioni: "
            f"<b>{escape(', '.join(tf.common))}</b>"
        )
    for cfg in config_names:
        extra = tf.per_config_extra.get(cfg, [])
        if extra:
            parts.append(
                f"{escape(cfg)} ha in più: <b>{escape(', '.join(extra))}</b>"
            )
    if tf.missing_configs:
        parts.append(
            f"dato assente per: {_join_it([escape(m) for m in tf.missing_configs])}"
        )
    if not parts:
        return None
    return f"<p>📋 <b>{label_esc}</b>: " + "; ".join(parts) + ".</p>"


def _tf_description_html(tf: TopicFinding, config_names: list[str]) -> str | None:
    if not tf.per_config_text:
        return None
    label_esc = escape(tf.label)
    cfg_list = [c for c in config_names if c in tf.per_config_text]
    if len(cfg_list) == 1:
        cfg = cfg_list[0]
        snippet = escape(tf.per_config_text[cfg][:250])
        return (
            f"<p>📝 <b>{label_esc}</b>: solo {escape(cfg)} riporta dati — "
            f"<i>{snippet}</i>.</p>"
        )
    pairs = [
        (cfg_list[i], cfg_list[j])
        for i in range(len(cfg_list))
        for j in range(i + 1, len(cfg_list))
    ]
    ratios = [
        _similarity(tf.per_config_text[a], tf.per_config_text[b]) for a, b in pairs
    ]
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
            snippet = escape(tf.per_config_text[cfg][:250])
            parts.append(f"{escape(cfg)}: <i>{snippet}</i>")
    if tf.missing_configs:
        parts.append(f"dato assente per: {_join_it([escape(m) for m in tf.missing_configs])}")
    return f"<p>📝 <b>{label_esc}</b>: " + "; ".join(parts) + ".</p>"


def _tf_generic_html(tf: TopicFinding, config_names: list[str]) -> str | None:
    groups: dict[str, tuple[str, list[str]]] = {}
    for cfg in config_names:
        text = tf.per_config_text.get(cfg)
        if not text:
            continue
        key = _normalize(text)
        value, cfgs = groups.get(key, (text, []))
        cfgs.append(cfg)
        groups[key] = (value, cfgs)
    label_esc = escape(tf.label)
    pieces = [
        f"{_join_it([escape(c) for c in cfgs])}: <i>{escape(value)}</i>"
        for value, cfgs in groups.values()
    ]
    if tf.missing_configs:
        pieces.append(f"assente per {_join_it([escape(m) for m in tf.missing_configs])}")
    if not pieces:
        return None
    status_esc = escape(tf.status)
    return f"<p>🔹 <b>{label_esc}</b> [{status_esc}]: " + "; ".join(pieces) + ".</p>"


# ---------------------------------------------------------------------------
# Overall discussion (visible single prose)
# ---------------------------------------------------------------------------

def build_overall_discussion(analysis: LocalAnalysis) -> str:
    """
    Synthesise the structured ``LocalAnalysis`` into a single, cohesive Italian
    HTML discourse for the DIFFERENZE visible section.

    The tone follows the user's example: explain how the selected ID-Funzione
    group behaves AS THE CONFIGURATIONS VARY — clearly stating the *parti comuni*
    and the *parti differenti*, referencing DOC IDs, config names, and cross-ID
    references in flowing prose.
    """
    if not analysis.record_analyses:
        return "<p>Nessun record selezionato.</p>"

    config_names = analysis.config_names
    cross_refs = analysis.cross_id_refs
    paragraphs: list[str] = []

    ids_str = escape(", ".join(ra.record_id for ra in analysis.record_analyses))
    if len(analysis.record_analyses) == 1:
        funz_str = escape(analysis.record_analyses[0].funzione)
    else:
        funz_str = escape(f"{len(analysis.record_analyses)} funzioni selezionate")
    configs_str = escape(_join_it(config_names)) if config_names else "nessuna configurazione"

    # --- Intro ---
    paragraphs.append(
        f"<p><b>Analisi locale AskTrainMind</b> — "
        f"ID <b>{ids_str}</b> ({funz_str}). "
        f"Configurazioni a confronto: {configs_str}.</p>"
    )

    for ra in analysis.record_analyses:
        all_findings_equal = all(
            tf.status == "uguale" for tf in ra.topic_findings
        )

        if all_findings_equal or not ra.topic_findings:
            paragraphs.append(
                f"<p>Per la funzione <b>{escape(ra.record_id)}</b> "
                f"(<i>{escape(ra.funzione)}</i>) "
                "le configurazioni risultano equivalenti su tutte le voci analizzate.</p>"
            )
            continue

        paragraphs.append(
            f"<h4>Funzione {escape(ra.record_id)} — {escape(ra.funzione)}</h4>"
        )

        # --- Component findings ---
        comp_findings = [tf for tf in ra.topic_findings if tf.kind == "componenti"]
        if comp_findings:
            all_comp_equal = all(tf.status == "uguale" for tf in comp_findings)
            # Gather global common codes across all component rows
            all_common: set[str] = set()
            for tf in comp_findings:
                all_common.update(tf.common)

            if all_comp_equal or (not any(tf.per_config_extra for tf in comp_findings)):
                if all_common:
                    paragraphs.append(
                        f"<p>I componenti circuitali sono i medesimi in tutte le configurazioni: "
                        f"<b>{escape(', '.join(sorted(all_common)))}</b>.</p>"
                    )
                else:
                    paragraphs.append(
                        "<p>I componenti circuitali risultano identici in tutte le configurazioni.</p>"
                    )
            else:
                # Build a richer narrative
                cfg_extras: dict[str, list[str]] = {}
                for tf in comp_findings:
                    for cfg, extra in tf.per_config_extra.items():
                        cfg_extras.setdefault(cfg, []).extend(extra)

                if all_common:
                    paragraphs.append(
                        f"<p>I componenti circuitali comuni a tutte le configurazioni sono: "
                        f"<b>{escape(', '.join(sorted(all_common)))}</b>.</p>"
                    )

                if cfg_extras:
                    extra_parts: list[str] = []
                    for cfg, extras in cfg_extras.items():
                        uniq = sorted(set(extras))
                        extra_parts.append(
                            f"la configurazione <b>{escape(cfg)}</b> presenta in aggiunta "
                            f"<b>{escape(', '.join(uniq))}</b>"
                        )
                    joined = "; ".join(extra_parts)
                    paragraphs.append(f"<p>Rispetto alle altre configurazioni, {joined}.</p>")

                # Mention missing configs
                missing_all: list[str] = []
                for tf in comp_findings:
                    missing_all.extend(tf.missing_configs)
                if missing_all:
                    uniq_missing = list(dict.fromkeys(missing_all))
                    paragraphs.append(
                        f"<p>Dati assenti per: "
                        f"{escape(_join_it(uniq_missing))}.</p>"
                    )

        # --- Description findings ---
        desc_findings = [tf for tf in ra.topic_findings if tf.kind == "descrizione"]
        if desc_findings:
            all_desc_equal = all(tf.status == "uguale" for tf in desc_findings)
            if all_desc_equal:
                paragraphs.append(
                    "<p>La descrizione circuitale è sostanzialmente identica in tutte le configurazioni.</p>"
                )
            else:
                paragraphs.append(
                    "<p>La descrizione circuitale varia tra le configurazioni:</p><ul>"
                )
                for tf in desc_findings:
                    for cfg in config_names:
                        text = tf.per_config_text.get(cfg)
                        if text:
                            snippet = escape(text[:300])
                            paragraphs.append(
                                f"<li><b>{escape(cfg)}</b>: <i>{snippet}</i></li>"
                            )
                paragraphs.append("</ul>")

        # --- Other differing findings ---
        other_findings = [
            tf for tf in ra.topic_findings
            if tf.kind not in ("componenti", "descrizione") and tf.status != "uguale"
        ]
        if other_findings:
            paragraphs.append(
                "<p>Altre voci che variano tra le configurazioni:</p><ul>"
            )
            for tf in other_findings:
                label_esc = escape(tf.label)
                for cfg in config_names:
                    text = tf.per_config_text.get(cfg)
                    if text:
                        paragraphs.append(
                            f"<li><b>{label_esc}</b> — {escape(cfg)}: "
                            f"<i>{escape(text[:200])}</i></li>"
                        )
            paragraphs.append("</ul>")

    # --- Cross-ID references ---
    if cross_refs:
        paragraphs.append(
            "<p>Alcuni di questi componenti fanno capo anche ad altri ID selezionati:</p><ul>"
        )
        for code, ids in sorted(cross_refs.items()):
            ids_esc = escape(", ".join(ids))
            paragraphs.append(
                f"<li><b>{escape(code)}</b>: presente nelle funzioni {ids_esc}.</li>"
            )
        paragraphs.append("</ul>")

    return "\n".join(paragraphs)


# ---------------------------------------------------------------------------
# Public entry point (backward-compatible)
# ---------------------------------------------------------------------------

def build_local_narrative(
    records: list[FunctionRecord],
    matrix: ComparisonMatrix,
) -> str:
    """
    Build a cohesive, human-readable Italian HTML narrative for the
    DIFFERENZE panel from the workbook data alone — no network, no API.

    Delegates to ``render_detailed_html(analyze_records(...))`` for backward
    compatibility with existing tests and consumers.
    """
    if not records:
        return "<p>Nessun record selezionato.</p>"
    analysis = analyze_records(records, matrix)
    return render_detailed_html(analysis)
