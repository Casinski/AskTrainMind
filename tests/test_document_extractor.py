"""Tests for asktrainmind.app.document_extractor."""
from __future__ import annotations

import io
from pathlib import Path

import pytest

from asktrainmind.app.document_extractor import (
    ExtractedDocument,
    PageText,
    extract_document,
    find_text_snippet,
    get_page_text,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_minimal_pdf() -> bytes:
    """
    Build a tiny but valid 2-page PDF entirely in-memory.
    Page 1 contains "Hello World", page 2 contains "Second page text".
    Uses only standard PDF cross-reference and stream syntax.
    """
    # We use PyMuPDF itself to build a small PDF if available,
    # otherwise fall back to a hand-crafted minimal PDF binary.
    try:
        import fitz
        doc = fitz.open()
        p1 = doc.new_page()
        p1.insert_text((72, 72), "Hello World")
        p2 = doc.new_page()
        p2.insert_text((72, 72), "Second page text")
        buf = io.BytesIO()
        doc.save(buf)
        doc.close()
        return buf.getvalue()
    except ImportError:
        pytest.skip("fitz/PyMuPDF not installed — skip PDF generation")


# ---------------------------------------------------------------------------
# PDF extraction tests (skipped gracefully without fitz)
# ---------------------------------------------------------------------------

def test_extract_pdf_with_fitz(tmp_path) -> None:
    fitz = pytest.importorskip("fitz", reason="PyMuPDF not installed")

    pdf_bytes = _make_minimal_pdf()
    pdf_file = tmp_path / "test.pdf"
    pdf_file.write_bytes(pdf_bytes)

    doc = extract_document("https://example.com/test.pdf", pdf_file)

    assert doc.status == "ok"
    assert doc.page_count == 2
    assert len(doc.pages) == 2
    assert "Hello World" in doc.pages[0].text
    assert "Second page text" in doc.pages[1].text


def test_extract_pdf_page_numbers_are_one_based(tmp_path) -> None:
    pytest.importorskip("fitz", reason="PyMuPDF not installed")

    pdf_bytes = _make_minimal_pdf()
    pdf_file = tmp_path / "test.pdf"
    pdf_file.write_bytes(pdf_bytes)

    doc = extract_document("https://example.com/test.pdf", pdf_file)

    assert doc.pages[0].page_number == 1
    assert doc.pages[1].page_number == 2


def test_get_page_text_helper(tmp_path) -> None:
    pytest.importorskip("fitz", reason="PyMuPDF not installed")

    pdf_bytes = _make_minimal_pdf()
    pdf_file = tmp_path / "test.pdf"
    pdf_file.write_bytes(pdf_bytes)

    doc = extract_document("https://example.com/test.pdf", pdf_file)

    assert "Hello World" in get_page_text(doc, 1)
    assert "Second page text" in get_page_text(doc, 2)
    assert get_page_text(doc, 99) == ""


def test_find_text_snippet_finds_match(tmp_path) -> None:
    pytest.importorskip("fitz", reason="PyMuPDF not installed")

    pdf_bytes = _make_minimal_pdf()
    pdf_file = tmp_path / "test.pdf"
    pdf_file.write_bytes(pdf_bytes)

    doc = extract_document("https://example.com/test.pdf", pdf_file)

    snippet = find_text_snippet(doc, "Second page")
    assert "Second page" in snippet


def test_find_text_snippet_no_match_returns_first_page(tmp_path) -> None:
    pytest.importorskip("fitz", reason="PyMuPDF not installed")

    pdf_bytes = _make_minimal_pdf()
    pdf_file = tmp_path / "test.pdf"
    pdf_file.write_bytes(pdf_bytes)

    doc = extract_document("https://example.com/test.pdf", pdf_file)

    snippet = find_text_snippet(doc, "NOMATCH12345XYZ")
    # Falls back to page 1 content
    assert "Hello World" in snippet


# ---------------------------------------------------------------------------
# Graceful degradation when PyMuPDF is missing
# ---------------------------------------------------------------------------

def test_extract_pdf_graceful_when_fitz_missing(tmp_path, monkeypatch) -> None:
    """extract_document returns an empty ExtractedDocument when fitz is not available."""
    import sys
    import builtins

    real_import = builtins.__import__

    def mock_import(name, *args, **kwargs):
        if name == "fitz":
            raise ImportError("No module named 'fitz'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", mock_import)

    pdf_file = tmp_path / "test.pdf"
    pdf_file.write_bytes(b"%PDF-1.4 fake")

    doc = extract_document("https://example.com/test.pdf", pdf_file)

    assert doc.status == "missing_dependency"
    assert doc.pages == []
    assert "pymupdf" in doc.message.lower() or "fitz" in doc.message.lower() or "pip" in doc.message.lower()


# ---------------------------------------------------------------------------
# Unsupported format
# ---------------------------------------------------------------------------

def test_extract_unsupported_format(tmp_path) -> None:
    pptx_file = tmp_path / "slides.pptx"
    pptx_file.write_bytes(b"PK fake pptx content")

    doc = extract_document("https://example.com/slides.pptx", pptx_file)

    assert doc.status == "unsupported_format"
    assert doc.pages == []


# ---------------------------------------------------------------------------
# Helpers on synthetic ExtractedDocument
# ---------------------------------------------------------------------------

def test_get_page_text_on_synthetic_doc() -> None:
    doc = ExtractedDocument(
        source_url="x",
        local_path=Path("."),
        pages=[
            PageText(page_number=1, text="Prima pagina"),
            PageText(page_number=2, text="Seconda pagina"),
        ],
        page_count=2,
    )
    assert get_page_text(doc, 1) == "Prima pagina"
    assert get_page_text(doc, 2) == "Seconda pagina"
    assert get_page_text(doc, 3) == ""


def test_find_text_snippet_on_synthetic_doc() -> None:
    doc = ExtractedDocument(
        source_url="x",
        local_path=Path("."),
        pages=[
            PageText(page_number=1, text="Testo pagina uno con parola chiave"),
            PageText(page_number=2, text="Altro testo pagina due"),
        ],
        page_count=2,
    )
    snippet = find_text_snippet(doc, "parola chiave")
    assert "parola chiave" in snippet


def test_find_text_snippet_empty_doc() -> None:
    doc = ExtractedDocument(source_url="x", local_path=Path("."))
    assert find_text_snippet(doc, "qualcosa") == ""


def test_find_text_snippet_empty_query_returns_first_page() -> None:
    doc = ExtractedDocument(
        source_url="x",
        local_path=Path("."),
        pages=[PageText(page_number=1, text="Prima pagina")],
        page_count=1,
    )
    snippet = find_text_snippet(doc, "")
    assert "Prima pagina" in snippet


# ---------------------------------------------------------------------------
# ExtractedDocument.ok property convenience
# ---------------------------------------------------------------------------

def test_extracted_document_ok_default() -> None:
    doc = ExtractedDocument(source_url="x", local_path=Path("."))
    # Default status is "ok"
    assert doc.status == "ok"
