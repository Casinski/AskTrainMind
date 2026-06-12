"""Tests for asktrainmind.app.reasoning — offline local brain."""
from __future__ import annotations

import pytest

from asktrainmind.app.comparison import build_comparison_matrix
from asktrainmind.app.excel_model import DetailRecord, DocumentRecord, FunctionRecord
from asktrainmind.app.reasoning import (
    _cross_id_references,
    _extract_codes,
    _is_component_row,
    _is_description_row,
    _similarity,
    analyze_records,
    build_local_narrative,
    build_overall_discussion,
    render_detailed_html,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _record(
    rid: str = "ID-01",
    funzione: str = "Funzione Test",
    details: list[DetailRecord] | None = None,
    config_links: dict[str, str] | None = None,
) -> FunctionRecord:
    return FunctionRecord(
        id=rid,
        funzione=funzione,
        tipo="TBD",
        generale_link=None,
        config_names=["ETR1000_A", "ETR1000_B"],
        documents=[
            DocumentRecord(
                doc_id="FS-001",
                info_doc="Documento di sistema",
                config_links=config_links or {"ETR1000_A": "http://example.com/doc"},
                details=details or [],
            )
        ],
    )


# ---------------------------------------------------------------------------
# Unit helpers
# ---------------------------------------------------------------------------

def test_extract_codes_dash_pattern():
    codes = _extract_codes("Componente GG-A024 e GH-B100 collegato a XX-Y9")
    assert "GG-A024" in codes
    assert "GH-B100" in codes
    assert "XX-Y9" in codes


def test_extract_codes_underscore_pattern():
    codes = _extract_codes("Documento FS_DM1 e scheda REF_999")
    assert "FS_DM1" in codes
    assert "REF_999" in codes


def test_extract_codes_empty_text():
    assert _extract_codes("") == frozenset()
    assert _extract_codes("parole senza codici speciali") == frozenset()


def test_similarity_identical():
    assert _similarity("testo uguale", "testo uguale") == pytest.approx(1.0)


def test_similarity_empty_strings():
    # Two empty strings are identical
    assert _similarity("", "") == pytest.approx(1.0)


def test_similarity_very_different():
    ratio = _similarity("alfa bravo charlie", "zulu yankee x-ray")
    assert ratio < 0.5


def test_is_component_row_matches_italian_titles():
    assert _is_component_row("doc fs-001 — componenti circuito elettrico")
    assert _is_component_row("Componenti vari")
    assert not _is_component_row("doc fs-001 — descrizione circuitale")
    assert not _is_component_row("doc fs-001 — link")


def test_is_description_row_matches_italian_titles():
    assert _is_description_row("doc fs-001 — descrizione circuitale")
    assert _is_description_row("Descrizione funzionale")
    assert not _is_description_row("doc fs-001 — componenti circuito")
    assert not _is_description_row("doc fs-001 — link")


# ---------------------------------------------------------------------------
# Cross-ID references
# ---------------------------------------------------------------------------

def test_cross_id_references_single_record_no_refs():
    records = [
        _record(
            rid="ID-01",
            details=[DetailRecord(title="Componenti", values={"ETR1000_A": "GG-A024"})],
        )
    ]
    refs = _cross_id_references(records)
    assert refs == {}


def test_cross_id_references_shared_code():
    records = [
        _record(
            rid="ID-01",
            details=[DetailRecord(title="Componenti", values={"ETR1000_A": "GG-A024 GH-B100"})],
        ),
        _record(
            rid="ID-02",
            details=[DetailRecord(title="Componenti", values={"ETR1000_A": "GG-A024 XX-Y001"})],
        ),
    ]
    refs = _cross_id_references(records)
    # GG-A024 appears in both
    assert "GG-A024" in refs
    assert set(refs["GG-A024"]) == {"ID-01", "ID-02"}
    # GH-B100 only in ID-01, XX-Y001 only in ID-02 → not in refs
    assert "GH-B100" not in refs
    assert "XX-Y001" not in refs


# ---------------------------------------------------------------------------
# build_local_narrative
# ---------------------------------------------------------------------------

def test_narrative_empty_records():
    matrix = build_comparison_matrix([])
    result = build_local_narrative([], matrix)
    assert "Nessun record selezionato" in result


def test_narrative_contains_intro():
    records = [_record()]
    matrix = build_comparison_matrix(records)
    html = build_local_narrative(records, matrix)
    assert "Analisi locale AskTrainMind" in html
    assert "ID-01" in html


def test_narrative_component_row_common_and_extra():
    records = [
        _record(
            details=[
                DetailRecord(
                    title="Componenti circuito elettrico",
                    values={
                        "ETR1000_A": "GG-A024 GH-B100",
                        "ETR1000_B": "GG-A024 XX-Y001",
                    },
                )
            ]
        )
    ]
    matrix = build_comparison_matrix(records)
    html = build_local_narrative(records, matrix)
    # Common: GG-A024
    assert "GG-A024" in html
    # Extra for A: GH-B100, extra for B: XX-Y001
    assert "GH-B100" in html
    assert "XX-Y001" in html


def test_narrative_component_row_all_equal():
    records = [
        _record(
            details=[
                DetailRecord(
                    title="Componenti circuito elettrico",
                    values={
                        "ETR1000_A": "GG-A024",
                        "ETR1000_B": "GG-A024",
                    },
                )
            ]
        )
    ]
    matrix = build_comparison_matrix(records)
    html = build_local_narrative(records, matrix)
    assert "GG-A024" in html


def test_narrative_description_row_similar():
    shared = "Testo descrittivo quasi identico con piccola variante"
    records = [
        _record(
            details=[
                DetailRecord(
                    title="Descrizione circuitale",
                    values={
                        "ETR1000_A": shared,
                        "ETR1000_B": shared + " aggiuntivo",
                    },
                )
            ]
        )
    ]
    matrix = build_comparison_matrix(records)
    html = build_local_narrative(records, matrix)
    # Should detect description row and include some similarity judgment
    assert "Descrizione" in html or "descriz" in html.lower()


def test_narrative_description_row_very_different():
    records = [
        _record(
            details=[
                DetailRecord(
                    title="Descrizione circuitale",
                    values={
                        "ETR1000_A": "Sistema alfa bravo charlie delta echo",
                        "ETR1000_B": "Circuito zulu yankee xray whiskey victor",
                    },
                )
            ]
        )
    ]
    matrix = build_comparison_matrix(records)
    html = build_local_narrative(records, matrix)
    assert "diverso" in html or "diversamente" in html.lower() or "diverso" in html


def test_narrative_cross_id_references_appear():
    records = [
        _record(
            rid="ID-01",
            funzione="Funzione Alfa",
            details=[DetailRecord(title="Componenti", values={"ETR1000_A": "GG-A024"})],
        ),
        _record(
            rid="ID-02",
            funzione="Funzione Beta",
            details=[DetailRecord(title="Componenti", values={"ETR1000_A": "GG-A024 GH-B100"})],
        ),
    ]
    matrix = build_comparison_matrix(records)
    html = build_local_narrative(records, matrix)
    # GG-A024 shared across two records → should appear in cross-refs section
    assert "Riferimenti incrociati" in html
    assert "GG-A024" in html


def test_narrative_no_cross_refs_when_single_record():
    records = [_record()]
    matrix = build_comparison_matrix(records)
    html = build_local_narrative(records, matrix)
    assert "Riferimenti incrociati" not in html


def test_narrative_uniform_configs_message():
    """When all rows are equal, the narrative says configs are equivalent."""
    records = [
        _record(
            details=[
                DetailRecord(
                    title="Rif. Pagina",
                    values={"ETR1000_A": "10", "ETR1000_B": "10"},
                )
            ],
            # Both configs have the same link so the link row is also 'uguale'
            config_links={"ETR1000_A": "http://example.com/doc", "ETR1000_B": "http://example.com/doc"},
        )
    ]
    matrix = build_comparison_matrix(records)
    html = build_local_narrative(records, matrix)
    # All rows are 'uguale', so the code should say configs are equivalent
    assert "equivalenti" in html or "uguale" in html


def test_narrative_missing_config_noted():
    """A config that is absent from a row should be mentioned."""
    records = [
        _record(
            details=[
                DetailRecord(
                    title="Componenti circuito elettrico",
                    values={"ETR1000_A": "GG-A024"},
                    # ETR1000_B is absent
                )
            ]
        )
    ]
    matrix = build_comparison_matrix(records)
    html = build_local_narrative(records, matrix)
    # ETR1000_B is missing → should be mentioned
    assert "ETR1000_B" in html


def test_narrative_is_valid_html_fragment():
    """Output should be a non-empty string containing HTML tags."""
    records = [_record()]
    matrix = build_comparison_matrix(records)
    html = build_local_narrative(records, matrix)
    assert "<p>" in html
    assert len(html) > 50


# ---------------------------------------------------------------------------
# Integration with NullProvider
# ---------------------------------------------------------------------------

def test_null_provider_uses_local_narrative():
    """NullProvider should produce richer differences_text via build_local_narrative."""
    from asktrainmind.app.ai_engine import AnalysisEngine
    from asktrainmind.app.config import AIConfig

    records = [
        _record(
            details=[
                DetailRecord(
                    title="Componenti circuito elettrico",
                    values={"ETR1000_A": "GG-A024 GH-B100", "ETR1000_B": "GG-A024"},
                )
            ]
        )
    ]
    engine = AnalysisEngine(AIConfig(provider="null"))
    output = engine.analyze(records)

    assert "Analisi locale AskTrainMind" in output.differences_text
    assert "GG-A024" in output.differences_text
    assert "modalità locale/offline" in (output.banner or "").lower()


# ---------------------------------------------------------------------------
# analyze_records structured output
# ---------------------------------------------------------------------------

def test_analyze_records_returns_config_names():
    records = [_record()]
    matrix = build_comparison_matrix(records)
    la = analyze_records(records, matrix)
    assert "ETR1000_A" in la.config_names
    assert "ETR1000_B" in la.config_names


def test_analyze_records_component_common_and_extra():
    records = [
        _record(
            details=[
                DetailRecord(
                    title="Componenti circuito elettrico",
                    values={
                        "ETR1000_A": "GG-A024 GH-B100",
                        "ETR1000_B": "GG-A024 XX-Y001",
                    },
                )
            ]
        )
    ]
    matrix = build_comparison_matrix(records)
    la = analyze_records(records, matrix)
    ra = la.record_analyses[0]
    comp_findings = [tf for tf in ra.topic_findings if tf.kind == "componenti"]
    assert comp_findings, "Expected at least one componenti TopicFinding"
    tf = comp_findings[0]
    assert "GG-A024" in tf.common
    assert "GH-B100" in tf.per_config_extra.get("ETR1000_A", [])
    assert "XX-Y001" in tf.per_config_extra.get("ETR1000_B", [])


def test_analyze_records_missing_config_noted():
    records = [
        _record(
            details=[
                DetailRecord(
                    title="Componenti circuito elettrico",
                    values={"ETR1000_A": "GG-A024"},
                )
            ]
        )
    ]
    matrix = build_comparison_matrix(records)
    la = analyze_records(records, matrix)
    ra = la.record_analyses[0]
    comp_findings = [tf for tf in ra.topic_findings if tf.kind == "componenti"]
    assert comp_findings
    tf = comp_findings[0]
    assert "ETR1000_B" in tf.missing_configs


def test_analyze_records_description_snippet():
    records = [
        _record(
            details=[
                DetailRecord(
                    title="Descrizione circuitale",
                    values={
                        "ETR1000_A": "Il sistema alfa gestisce la frenatura",
                        "ETR1000_B": "Il sistema beta gestisce la trazione",
                    },
                )
            ]
        )
    ]
    matrix = build_comparison_matrix(records)
    la = analyze_records(records, matrix)
    ra = la.record_analyses[0]
    desc_findings = [tf for tf in ra.topic_findings if tf.kind == "descrizione"]
    assert desc_findings
    tf = desc_findings[0]
    assert "ETR1000_A" in tf.per_config_text
    assert "frenatura" in tf.per_config_text["ETR1000_A"]


def test_analyze_records_cross_id_refs():
    records = [
        _record(
            rid="ID-01",
            details=[DetailRecord(title="Componenti", values={"ETR1000_A": "GG-A024"})],
        ),
        _record(
            rid="ID-02",
            details=[DetailRecord(title="Componenti", values={"ETR1000_A": "GG-A024 XX-Y001"})],
        ),
    ]
    matrix = build_comparison_matrix(records)
    la = analyze_records(records, matrix)
    assert "GG-A024" in la.cross_id_refs
    assert set(la.cross_id_refs["GG-A024"]) == {"ID-01", "ID-02"}


# ---------------------------------------------------------------------------
# build_overall_discussion
# ---------------------------------------------------------------------------

def test_build_overall_discussion_single_cohesive_prose():
    """Output is a non-empty HTML string that is a single unified discourse."""
    records = [
        _record(
            details=[
                DetailRecord(
                    title="Componenti circuito elettrico",
                    values={
                        "ETR1000_A": "GG-A024 GH-B100",
                        "ETR1000_B": "GG-A024",
                    },
                )
            ]
        )
    ]
    matrix = build_comparison_matrix(records)
    la = analyze_records(records, matrix)
    html = build_overall_discussion(la)
    assert html
    assert "<p>" in html
    assert "ETR1000_A" in html
    assert "ETR1000_B" in html
    assert "GG-A024" in html
    assert "GH-B100" in html


def test_build_overall_discussion_all_equal_says_so():
    records = [
        _record(
            details=[
                DetailRecord(
                    title="Componenti circuito elettrico",
                    values={"ETR1000_A": "GG-A024", "ETR1000_B": "GG-A024"},
                )
            ],
            config_links={"ETR1000_A": "http://example.com", "ETR1000_B": "http://example.com"},
        )
    ]
    matrix = build_comparison_matrix(records)
    la = analyze_records(records, matrix)
    html = build_overall_discussion(la)
    assert "equivalenti" in html or "medesimi" in html or "identic" in html.lower()


def test_build_overall_discussion_mentions_description_when_differs():
    records = [
        _record(
            details=[
                DetailRecord(
                    title="Descrizione circuitale",
                    values={
                        "ETR1000_A": "Sistema alfa bravo charlie delta echo foxtrot",
                        "ETR1000_B": "Circuito zulu yankee xray whiskey victor uniform",
                    },
                )
            ]
        )
    ]
    matrix = build_comparison_matrix(records)
    la = analyze_records(records, matrix)
    html = build_overall_discussion(la)
    assert "ETR1000_A" in html
    assert "ETR1000_B" in html


def test_build_overall_discussion_empty_records():
    from asktrainmind.app.reasoning import LocalAnalysis
    la = LocalAnalysis(config_names=[], record_analyses=[], cross_id_refs={})
    html = build_overall_discussion(la)
    assert "Nessun record" in html


def test_render_detailed_html_contains_analisi_title():
    records = [_record()]
    matrix = build_comparison_matrix(records)
    la = analyze_records(records, matrix)
    html = render_detailed_html(la)
    assert "Analisi locale AskTrainMind" in html
    assert "ID-01" in html
