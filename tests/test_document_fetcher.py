"""Tests for asktrainmind.app.document_fetcher."""
from __future__ import annotations

import os
import base64
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from asktrainmind.app.document_fetcher import (
    FetchResult,
    classify_sharepoint_url,
    encode_share_token,
    fetch_document,
)


# ---------------------------------------------------------------------------
# URL classification
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("url, expected", [
    # Share links (/:b:/, /:w:/, /:x:/, /:p:/)
    ("https://contoso.sharepoint.com/:b:/r/sites/MySite/file.pdf", "share_link"),
    ("https://contoso.sharepoint.com/:w:/r/sites/MySite/doc.docx", "share_link"),
    ("https://contoso.sharepoint.com/:x:/r/sites/MySite/book.xlsx", "share_link"),
    ("https://contoso.sharepoint.com/:p:/r/sites/MySite/pres.pptx", "share_link"),
    ("https://contoso.sharepoint.com/:f:/r/sites/MySite/folder", "share_link"),
    # Guest access
    ("https://contoso.sharepoint.com/_layouts/15/guestaccess.aspx?share=xxx", "guest_access"),
    ("https://contoso.sharepoint.com/_layouts/15/download.aspx?UniqueId=xxx", "guest_access"),
    # web=1 links
    ("https://contoso.sharepoint.com/sites/Site/Docs/file.pdf?web=1", "share_link"),
    # Direct download by extension
    ("https://contoso.sharepoint.com/sites/Site/Docs/file.pdf", "direct_download"),
    ("https://contoso.sharepoint.com/sites/Site/Docs/file.docx", "direct_download"),
    # Unsupported
    ("https://example.com/file.pdf", "unsupported"),
    ("", "unsupported"),
    ("not-a-url", "unsupported"),
])
def test_classify_sharepoint_url(url: str, expected: str) -> None:
    assert classify_sharepoint_url(url) == expected


# ---------------------------------------------------------------------------
# Share token encoding
# ---------------------------------------------------------------------------

def test_encode_share_token_format() -> None:
    url = "https://contoso.sharepoint.com/:b:/r/sites/Site/Shared%20Documents/file.pdf"
    token = encode_share_token(url)
    assert token.startswith("u!")
    # No padding
    assert "=" not in token
    # Decode should round-trip
    encoded_part = token[2:]
    # Add back padding for standard base64 decoding
    padded = encoded_part + "=" * (4 - len(encoded_part) % 4)
    decoded = base64.urlsafe_b64decode(padded).decode("utf-8")
    assert decoded == url


def test_encode_share_token_is_deterministic() -> None:
    url = "https://contoso.sharepoint.com/:b:/r/sites/Site/file.pdf"
    assert encode_share_token(url) == encode_share_token(url)


def test_encode_share_token_different_urls_produce_different_tokens() -> None:
    url1 = "https://contoso.sharepoint.com/:b:/r/sites/A/file.pdf"
    url2 = "https://contoso.sharepoint.com/:b:/r/sites/B/file.pdf"
    assert encode_share_token(url1) != encode_share_token(url2)


# ---------------------------------------------------------------------------
# CI guard
# ---------------------------------------------------------------------------

def test_fetch_document_ci_guard_blocks_auth(monkeypatch) -> None:
    """In CI environment, fetch_document must return an error without attempting auth."""
    monkeypatch.setenv("CI", "true")
    url = "https://contoso.sharepoint.com/:b:/r/sites/Site/file.pdf"
    result = fetch_document(url, force_refresh=True)
    assert result.ok is False
    assert result.status == "ci_guard"
    assert "CI" in result.message or "autenticazione" in result.message.lower()


def test_fetch_document_github_actions_guard(monkeypatch) -> None:
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.delenv("CI", raising=False)
    url = "https://contoso.sharepoint.com/:b:/r/sites/Site/file.pdf"
    result = fetch_document(url, force_refresh=True)
    assert result.ok is False
    assert result.status == "ci_guard"


# ---------------------------------------------------------------------------
# Unsupported URL
# ---------------------------------------------------------------------------

def test_fetch_document_unsupported_url() -> None:
    result = fetch_document("https://example.com/file.pdf")
    assert result.ok is False
    assert result.status == "unsupported_url"


def test_fetch_document_empty_url() -> None:
    result = fetch_document("")
    assert result.ok is False
    assert result.status == "invalid_url"


# ---------------------------------------------------------------------------
# Cache hit — no network needed
# ---------------------------------------------------------------------------

def test_fetch_document_returns_cached_path(tmp_path, monkeypatch) -> None:
    """If a file is already in cache, fetch_document returns it without auth."""
    from asktrainmind.app import document_fetcher

    url = "https://contoso.sharepoint.com/:b:/r/sites/Site/cached.pdf"
    # Compute the cache key and pre-populate a fake cached file
    from asktrainmind.app.document_fetcher import _cache_key, _documents_cache_dir
    monkeypatch.setattr(document_fetcher, "_documents_cache_dir", lambda: tmp_path)

    key = _cache_key(url)
    cached_file = tmp_path / (key + ".pdf")
    cached_file.write_bytes(b"%PDF-1.4 fake")

    result = fetch_document(url, force_refresh=False)
    assert result.ok is True
    assert result.status == "cached"
    assert result.local_path == cached_file


# ---------------------------------------------------------------------------
# Failure paths — monkeypatched network, no real I/O
# ---------------------------------------------------------------------------

def test_fetch_document_auth_error_is_caught(monkeypatch) -> None:
    """If acquire_graph_token raises, fetch_document returns auth_error."""
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)

    import asktrainmind.app.document_fetcher as mod

    monkeypatch.setattr(mod, "acquire_graph_token", lambda: (_ for _ in ()).throw(RuntimeError("no msal")))
    # Ensure cache is empty for this URL
    monkeypatch.setattr(mod, "_cached_path", lambda url: None)

    url = "https://contoso.sharepoint.com/:b:/r/sites/Site/file.pdf"
    result = fetch_document(url, force_refresh=True)
    assert result.ok is False
    assert result.status == "auth_error"


def test_fetch_document_graph_not_found(monkeypatch) -> None:
    """404 from Graph shares API → not_found result."""
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)

    import asktrainmind.app.document_fetcher as mod
    monkeypatch.setattr(mod, "acquire_graph_token", lambda: "fake-token")
    monkeypatch.setattr(mod, "_cached_path", lambda url: None)

    mock_response = MagicMock()
    mock_response.status_code = 404
    mock_response.ok = False

    import requests as req
    monkeypatch.setattr(req, "get", lambda *a, **kw: mock_response)

    url = "https://contoso.sharepoint.com/:b:/r/sites/Site/file.pdf"
    result = fetch_document(url, force_refresh=True)
    assert result.ok is False
    assert result.status == "not_found"


def test_fetch_document_permission_denied(monkeypatch) -> None:
    """403 from Graph → permission_denied result."""
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)

    import asktrainmind.app.document_fetcher as mod
    monkeypatch.setattr(mod, "acquire_graph_token", lambda: "fake-token")
    monkeypatch.setattr(mod, "_cached_path", lambda url: None)

    mock_response = MagicMock()
    mock_response.status_code = 403
    mock_response.ok = False

    import requests as req
    monkeypatch.setattr(req, "get", lambda *a, **kw: mock_response)

    url = "https://contoso.sharepoint.com/:b:/r/sites/Site/file.pdf"
    result = fetch_document(url, force_refresh=True)
    assert result.ok is False
    assert result.status == "permission_denied"
