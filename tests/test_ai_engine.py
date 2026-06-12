from pathlib import Path

from asktrainmind.app.ai_engine import AnalysisEngine
from asktrainmind.app.config import AIConfig
from asktrainmind.app.document_extractor import ExtractedDocument, PageText
from asktrainmind.app.excel_model import DetailRecord, DocumentRecord, FunctionRecord
from asktrainmind.app.image_extractor import WorkbookImage


class StubProvider:
    def analyze(self, records, matrix, images=None, documents=None, kb_entries=None):
        return "=== INFO ===\nSintesi INFO\n=== DIFFERENZE ===\nSintesi DIFFERENZE"


class StubFailProvider:
    def analyze(self, records, matrix, images=None, documents=None, kb_entries=None):
        raise RuntimeError("boom")


def _records() -> list[FunctionRecord]:
    return [
        FunctionRecord(
            id="ID_TEST",
            funzione="Funzione Test",
            tipo="TBD",
            generale_link=None,
            config_names=["CONF_A", "CONF_B"],
            documents=[
                DocumentRecord(
                    doc_id="DOC-1",
                    info_doc="Info",
                    config_links={"CONF_A": "link-1"},
                    details=[
                        DetailRecord(title="Rif. Pagina", values={"CONF_A": "10", "CONF_B": "20"}),
                    ],
                )
            ],
            start_row=2,
            end_row=6,
        )
    ]


def _make_extracted_doc(url: str = "https://example.com/doc.pdf") -> ExtractedDocument:
    return ExtractedDocument(
        source_url=url,
        local_path=Path("."),
        pages=[
            PageText(page_number=1, text="Testo di riferimento pagina uno"),
            PageText(page_number=2, text="Testo pagina due con dettagli tecnici"),
        ],
        page_count=2,
    )


def test_engine_parses_marked_sections_from_provider(monkeypatch):
    engine = AnalysisEngine(AIConfig(provider="openai", api_key="x", model="gpt-4o-mini"))
    monkeypatch.setattr(engine, "_build_provider", lambda: StubProvider())

    output = engine.analyze(_records())

    assert output.info_text == "Sintesi INFO"
    assert output.differences_text == "Sintesi DIFFERENZE"


def test_engine_offline_mode_populates_diff_table():
    engine = AnalysisEngine(AIConfig(provider="null"))

    output = engine.analyze(_records())

    assert "deterministica" in (output.banner or "").lower()
    assert "diff-table" in output.diff_table_html
    assert output.info_text != output.differences_text


def test_engine_accepts_images_argument_without_crash(monkeypatch):
    engine = AnalysisEngine(AIConfig(provider="openai", api_key="x", model="gpt-4o-mini"))
    monkeypatch.setattr(engine, "_build_provider", lambda: StubProvider())
    images = [WorkbookImage(row=3, column=1, mime_type="image/png", data=b"not-an-image")]

    output = engine.analyze(_records(), images=images)

    assert output.images == images
    assert "diff-table" in output.diff_table_html


def test_engine_falls_back_to_null_provider_on_error(monkeypatch):
    engine = AnalysisEngine(AIConfig(provider="openai", api_key="x", model="gpt-4o-mini"))
    monkeypatch.setattr(engine, "_build_provider", lambda: StubFailProvider())

    output = engine.analyze(_records())

    assert "deterministica" in (output.banner or "").lower()


# ---------------------------------------------------------------------------
# Phase 3: documents parameter tests
# ---------------------------------------------------------------------------

def test_engine_accepts_documents_argument_without_crash(monkeypatch):
    """analyze(records, images=..., documents=...) must not raise."""
    engine = AnalysisEngine(AIConfig(provider="openai", api_key="x", model="gpt-4o-mini"))
    monkeypatch.setattr(engine, "_build_provider", lambda: StubProvider())
    documents = [_make_extracted_doc()]

    output = engine.analyze(_records(), documents=documents)

    assert output.info_text == "Sintesi INFO"
    assert output.differences_text == "Sintesi DIFFERENZE"
    assert "diff-table" in output.diff_table_html


def test_engine_offline_with_documents_includes_page_text():
    """Offline deterministic path includes extracted page text in info/diff output."""
    engine = AnalysisEngine(AIConfig(provider="null"))
    documents = [_make_extracted_doc()]

    output = engine.analyze(_records(), documents=documents)

    assert "deterministica" in (output.banner or "").lower()
    # Extracted page text should appear somewhere in INFO or DIFFERENZE
    combined = output.info_text + output.differences_text
    assert "Testo di riferimento" in combined or "doc-extracts" in combined


def test_engine_old_signature_still_works():
    """analyze(records) and analyze(records, images=...) still work (backward compat)."""
    engine = AnalysisEngine(AIConfig(provider="null"))

    out1 = engine.analyze(_records())
    assert "diff-table" in out1.diff_table_html

    images = [WorkbookImage(row=2, column=1, mime_type="image/png", data=b"x")]
    out2 = engine.analyze(_records(), images=images)
    assert out2.images == images


def test_engine_documents_none_does_not_change_behavior():
    """Passing documents=None is equivalent to not passing it."""
    engine = AnalysisEngine(AIConfig(provider="null"))

    out_no_docs = engine.analyze(_records())
    out_none_docs = engine.analyze(_records(), documents=None)

    assert out_no_docs.info_text == out_none_docs.info_text
    assert out_no_docs.differences_text == out_none_docs.differences_text


def test_engine_falls_back_with_documents_on_provider_error(monkeypatch):
    """If provider raises, fallback NullProvider also receives documents."""
    engine = AnalysisEngine(AIConfig(provider="openai", api_key="x", model="gpt-4o-mini"))
    monkeypatch.setattr(engine, "_build_provider", lambda: StubFailProvider())
    documents = [_make_extracted_doc()]

    output = engine.analyze(_records(), documents=documents)

    # Should fall back to deterministic output (includes doc text)
    assert "deterministica" in (output.banner or "").lower()
    combined = output.info_text + output.differences_text
    assert "Testo di riferimento" in combined or "doc-extracts" in combined



# ---------------------------------------------------------------------------
# Phase 4: knowledge base grounding tests
# ---------------------------------------------------------------------------

def test_engine_offline_with_kb_entries_appears_in_info():
    """KB entries should surface in INFO output for offline/deterministic mode."""
    engine = AnalysisEngine(AIConfig(provider="null"))
    kb_entries = [
        {
            "id": "abc",
            "title": "Nota FAM",
            "text": "Il FAM si aziona tramite il banco di manovra.",
            "function_ids": ["ID_TEST"],
            "tags": [],
            "created_at": "2024-01-01T00:00:00+00:00",
            "updated_at": "2024-01-01T00:00:00+00:00",
        }
    ]

    output = engine.analyze(_records(), kb_entries=kb_entries)

    assert "kb-block" in output.info_text or "Nota FAM" in output.info_text
    assert "FAM si aziona" in output.info_text


def test_engine_offline_no_kb_entries_no_kb_block():
    """Without KB entries, no kb-block should appear."""
    engine = AnalysisEngine(AIConfig(provider="null"))
    output = engine.analyze(_records(), kb_entries=None)
    assert "kb-block" not in output.info_text


def test_engine_kb_entries_empty_list_no_kb_block():
    """Empty KB entries list should not render a kb-block."""
    engine = AnalysisEngine(AIConfig(provider="null"))
    output = engine.analyze(_records(), kb_entries=[])
    assert "kb-block" not in output.info_text


def test_engine_with_provider_and_kb_entries(monkeypatch):
    """KB entries are appended to info_text from provider output."""
    engine = AnalysisEngine(AIConfig(provider="openai", api_key="x", model="gpt-4o-mini"))
    monkeypatch.setattr(engine, "_build_provider", lambda: StubProvider())
    kb_entries = [
        {
            "id": "xyz",
            "title": "Note di test",
            "text": "Testo knowledge base",
            "function_ids": [],
            "tags": [],
            "created_at": "2024-01-01T00:00:00+00:00",
            "updated_at": "2024-01-01T00:00:00+00:00",
        }
    ]

    output = engine.analyze(_records(), kb_entries=kb_entries)

    assert "kb-block" in output.info_text or "Testo knowledge base" in output.info_text


def test_engine_backward_compat_no_kb_entries():
    """analyze(records) without kb_entries still works correctly."""
    engine = AnalysisEngine(AIConfig(provider="null"))
    output = engine.analyze(_records())
    assert "diff-table" in output.diff_table_html
    assert output.info_text != output.differences_text
