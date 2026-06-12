"""
Document fetcher for Phase 3: download linked SharePoint documents.

Downloads files referenced in DocumentRecord.config_links (columns F–L) and
FunctionRecord.generale_link using the Microsoft Graph "shares" API.

Caches files under cache_dir()/documents/ keyed by a stable URL hash.
Never raises to callers — all errors are returned as typed FetchResult.
Interactive auth is blocked in CI (same pattern as sharepoint._acquire_token).
"""
from __future__ import annotations

import base64
import hashlib
import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import requests

from asktrainmind.app.config import cache_dir
from asktrainmind.app.sharepoint import acquire_graph_token, GRAPH_ROOT

# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------

@dataclass
class FetchResult:
    ok: bool
    status: str
    message: str
    local_path: Path | None = None
    content_type: str = ""


# ---------------------------------------------------------------------------
# URL classification
# ---------------------------------------------------------------------------

_SHARE_LINK_PATTERNS = (
    "/:b:/",  # PDF / binary
    "/:w:/",  # Word
    "/:x:/",  # Excel
    "/:p:/",  # PowerPoint
    "/:f:/",  # Folder (may still be downloadable item)
    "/:u:/",  # generic share
    "/:i:/",  # image
    "/:v:/",  # video
)


def classify_sharepoint_url(url: str) -> str:
    """Return the URL type: 'share_link', 'guest_access', 'direct_download', or 'unsupported'."""
    if not url:
        return "unsupported"
    parsed = urlparse(url)
    netloc = parsed.netloc.lower()
    path = parsed.path.lower()
    query = parsed.query.lower()

    if not netloc.endswith(".sharepoint.com") and "sharepoint.com" not in netloc:
        return "unsupported"

    if any(pat in path for pat in _SHARE_LINK_PATTERNS):
        return "share_link"

    if "guestaccess.aspx" in path or "download.aspx" in path:
        return "guest_access"

    if "web=1" in query or "?web=1" in url:
        return "share_link"

    if path.endswith((".pdf", ".docx", ".xlsx", ".pptx", ".doc", ".xls", ".ppt")):
        return "direct_download"

    return "share_link"


# ---------------------------------------------------------------------------
# Share-token encoding (u! + base64url, no padding)
# ---------------------------------------------------------------------------

def encode_share_token(url: str) -> str:
    """Encode a sharing URL to a Graph share token: u! + base64url(url), no padding."""
    encoded = base64.urlsafe_b64encode(url.encode("utf-8")).decode("ascii").rstrip("=")
    return "u!" + encoded


# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------

def _documents_cache_dir() -> Path:
    path = cache_dir() / "documents"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _cache_key(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()[:40]


def _cached_path(url: str) -> Path | None:
    key = _cache_key(url)
    doc_dir = _documents_cache_dir()
    # Look for any file whose name starts with the key
    candidates = list(doc_dir.glob(f"{key}*"))
    if candidates:
        return candidates[0]
    return None


def _cache_write(url: str, data: bytes, extension: str = ".bin") -> Path:
    key = _cache_key(url)
    path = _documents_cache_dir() / (key + extension)
    path.write_bytes(data)
    return path


# ---------------------------------------------------------------------------
# Internal download helpers
# ---------------------------------------------------------------------------

def _extension_from_content_type(content_type: str) -> str:
    ct = content_type.lower().split(";")[0].strip()
    mapping = {
        "application/pdf": ".pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation": ".pptx",
        "application/msword": ".doc",
        "application/vnd.ms-excel": ".xls",
        "application/vnd.ms-powerpoint": ".ppt",
        "text/plain": ".txt",
    }
    return mapping.get(ct, ".bin")


def _download_via_graph_shares(url: str, token: str) -> FetchResult:
    """Use Graph /shares/{token}/driveItem to get the download URL then download."""
    share_token = encode_share_token(url)
    drive_item_url = f"{GRAPH_ROOT}/shares/{share_token}/driveItem"
    headers = {"Authorization": "Bearer " + token}

    try:
        resp = requests.get(drive_item_url, headers=headers, timeout=30)
    except requests.RequestException as exc:
        return FetchResult(False, "network_error", f"Errore rete driveItem: {exc}")

    if resp.status_code == 403:
        return FetchResult(False, "permission_denied", "Accesso negato al documento")
    if resp.status_code == 404:
        return FetchResult(False, "not_found", "Documento non trovato su SharePoint")
    if not resp.ok:
        return FetchResult(False, "graph_error", f"Errore Graph {resp.status_code}: {resp.text[:200]}")

    item = resp.json()
    download_url = item.get("@microsoft.graph.downloadUrl")
    if not download_url:
        return FetchResult(False, "no_download_url", "URL download non disponibile per il documento")

    try:
        content_resp = requests.get(download_url, timeout=60)
        content_resp.raise_for_status()
    except requests.RequestException as exc:
        return FetchResult(False, "network_error", f"Errore download contenuto: {exc}")

    content_type = content_resp.headers.get("content-type", "application/octet-stream")
    ext = _extension_from_content_type(content_type)
    local_path = _cache_write(url, content_resp.content, ext)
    return FetchResult(True, "ok", "Download completato", local_path, content_type)


def _download_direct(url: str) -> FetchResult:
    """Download a direct file URL without auth."""
    try:
        resp = requests.get(url, timeout=60)
        resp.raise_for_status()
    except requests.RequestException as exc:
        return FetchResult(False, "network_error", f"Errore download diretto: {exc}")

    content_type = resp.headers.get("content-type", "application/octet-stream")
    ext = _extension_from_content_type(content_type)
    local_path = _cache_write(url, resp.content, ext)
    return FetchResult(True, "ok", "Download diretto completato", local_path, content_type)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def fetch_document(url: str, force_refresh: bool = False) -> FetchResult:
    """
    Download the document at *url* to the local cache and return a FetchResult.

    Caching: if a cached copy exists and force_refresh is False, returns the
    cached path immediately without any network call.

    Auth: uses the same MS Graph token as sharepoint.download_workbook.
    Never raises — all error conditions are returned as FetchResult(ok=False, ...).

    CI guard: interactive auth is refused in CI (returns an error FetchResult).
    """
    if not url:
        return FetchResult(False, "invalid_url", "URL vuota")

    url = url.strip()
    url_type = classify_sharepoint_url(url)

    if url_type == "unsupported":
        return FetchResult(False, "unsupported_url", f"URL non riconosciuta come SharePoint: {url[:80]}")

    # Return cached copy if present
    if not force_refresh:
        cached = _cached_path(url)
        if cached and cached.exists():
            return FetchResult(True, "cached", "Documento già in cache", cached)

    # CI guard — same as _acquire_token
    if os.environ.get("CI") or os.environ.get("GITHUB_ACTIONS"):
        return FetchResult(False, "ci_guard", "Autenticazione non disponibile in CI")

    # Acquire token
    try:
        token = acquire_graph_token()
    except Exception as exc:
        return FetchResult(False, "auth_error", f"Autenticazione fallita: {exc}")

    # Download
    if url_type == "direct_download":
        return _download_direct(url)
    return _download_via_graph_shares(url, token)
