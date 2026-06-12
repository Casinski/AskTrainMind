"""Tests for asktrainmind.app.page_reference."""
from __future__ import annotations

import pytest

from asktrainmind.app.excel_model import DetailRecord, DocumentRecord
from asktrainmind.app.page_reference import (
    build_pdf_page_url,
    get_document_reference,
    parse_rif_pagina,
)


# ---------------------------------------------------------------------------
# parse_rif_pagina tests
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("value, expected", [
    ("", []),
    ("12", [12]),
    ("p. 12", [12]),
    ("p.12", [12]),
    ("pag 12", [12]),
    ("pag. 12", [12]),
    ("pagina 12", [12]),
    ("pag 12-14", [12, 13, 14]),
    ("12-14", [12, 13, 14]),
    ("12,15", [12, 15]),
    ("12, 15", [12, 15]),
    ("p. 12-14, 16", [12, 13, 14, 16]),
    ("p.12-14,16", [12, 13, 14, 16]),
    ("n.d.", []),
    ("  ", []),
    ("pag 5; pag 7", [5, 7]),
    ("1, 2, 3", [1, 2, 3]),
    ("10–12", [10, 11, 12]),   # en-dash
    ("10—12", [10, 11, 12]),   # em-dash
])
def test_parse_rif_pagina(value: str, expected: list[int]) -> None:
    assert parse_rif_pagina(value) == expected


def test_parse_rif_pagina_deduplicates() -> None:
    result = parse_rif_pagina("12, 12, 14")
    assert result == [12, 14]


def test_parse_rif_pagina_sorted() -> None:
    result = parse_rif_pagina("14, 12")
    assert result == [12, 14]


# ---------------------------------------------------------------------------
# get_document_reference tests
# ---------------------------------------------------------------------------

def _make_doc_record(
    config_links: dict[str, str] | None = None,
    rif_pagina_values: dict[str, str] | None = None,
) -> DocumentRecord:
    details = []
    if rif_pagina_values:
        details.append(DetailRecord(title="Rif. Pagina", values=rif_pagina_values))
    return DocumentRecord(
        doc_id="DOC-1",
        info_doc="Info test",
        config_links=config_links or {},
        details=details,
    )


def test_get_document_reference_returns_url_and_pages() -> None:
    doc = _make_doc_record(
        config_links={"CONF_A": "https://example.sharepoint.com/link"},
        rif_pagina_values={"CONF_A": "pag 5-7"},
    )
    url, pages = get_document_reference(doc, "CONF_A")
    assert url == "https://example.sharepoint.com/link"
    assert pages == [5, 6, 7]


def test_get_document_reference_missing_config() -> None:
    doc = _make_doc_record(
        config_links={"CONF_A": "https://example.sharepoint.com/link"},
        rif_pagina_values={"CONF_A": "12"},
    )
    url, pages = get_document_reference(doc, "CONF_B")
    assert url is None
    assert pages == []


def test_get_document_reference_no_rif_pagina() -> None:
    doc = _make_doc_record(
        config_links={"CONF_A": "https://example.sharepoint.com/link"},
    )
    url, pages = get_document_reference(doc, "CONF_A")
    assert url == "https://example.sharepoint.com/link"
    assert pages == []


def test_get_document_reference_empty_link() -> None:
    doc = _make_doc_record(config_links={})
    url, pages = get_document_reference(doc, "CONF_A")
    assert url is None
    assert pages == []


# ---------------------------------------------------------------------------
# build_pdf_page_url tests
# ---------------------------------------------------------------------------

def test_build_pdf_page_url_contains_fragment(tmp_path) -> None:
    pdf_file = tmp_path / "test.pdf"
    pdf_file.write_bytes(b"")
    url = build_pdf_page_url(pdf_file, 5)
    assert "#page=5" in url
    assert url.startswith("file://")


def test_build_pdf_page_url_zero_page_no_fragment(tmp_path) -> None:
    pdf_file = tmp_path / "test.pdf"
    pdf_file.write_bytes(b"")
    url = build_pdf_page_url(pdf_file, 0)
    assert "#page=" not in url
