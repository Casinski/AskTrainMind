"""
Rif. Pagina deep-linking for Phase 3.

Parses the Italian-formatted page references found in DocumentRecord detail rows
(title = "Rif. Pagina") into normalized lists of target page numbers.

Supported formats:
  "12"           → [12]
  "p. 12"        → [12]
  "pag 12"       → [12]
  "pag. 12"      → [12]
  "pag 12-14"    → [12, 13, 14]
  "12-14"        → [12, 13, 14]
  "12,15"        → [12, 15]
  "12, 15"       → [12, 15]
  "p. 12-14, 16" → [12, 13, 14, 16]
  ""             → []
  "n.d."         → []
"""
from __future__ import annotations

import re
from pathlib import Path

from asktrainmind.app.excel_model import DocumentRecord


# ---------------------------------------------------------------------------
# Rif. Pagina string parser
# ---------------------------------------------------------------------------

# Strip Italian prefixes like "p.", "pag.", "pag", "pagina", "p ", etc.
_PREFIX_RE = re.compile(r"^(?:pag(?:ina)?\.?\s*|p\.?\s+)", re.IGNORECASE)
# A single segment: either a range (12-14) or a single number (12)
_SEGMENT_RE = re.compile(r"(\d+)\s*[-–—]\s*(\d+)|(\d+)")


def parse_rif_pagina(value: str) -> list[int]:
    """
    Parse an Italian page-reference string into a sorted, deduplicated list of
    1-based page numbers.  Returns an empty list for empty or unrecognisable input.
    """
    if not value:
        return []

    text = value.strip()
    # Strip Italian page prefix (applies to the whole string or to each fragment)
    text = _PREFIX_RE.sub("", text)

    # Split on commas and semicolons to handle multi-valued entries
    fragments = re.split(r"[,;]", text)
    pages: list[int] = []

    for fragment in fragments:
        fragment = _PREFIX_RE.sub("", fragment.strip())
        for match in _SEGMENT_RE.finditer(fragment):
            if match.group(1) and match.group(2):
                # Range
                start = int(match.group(1))
                end = int(match.group(2))
                pages.extend(range(start, end + 1))
            elif match.group(3):
                pages.append(int(match.group(3)))

    # Deduplicate and sort while preserving order
    seen: set[int] = set()
    result: list[int] = []
    for p in pages:
        if p > 0 and p not in seen:
            seen.add(p)
            result.append(p)
    return sorted(result)


# ---------------------------------------------------------------------------
# Per-configuration document reference lookup
# ---------------------------------------------------------------------------

def get_document_reference(
    doc_record: DocumentRecord, config_name: str
) -> tuple[str | None, list[int]]:
    """
    Return (document_url, target_pages) for a given configuration within a DocumentRecord.

    - *document_url*: the link from doc_record.config_links[config_name], or None.
    - *target_pages*: parsed page numbers from the first "Rif. Pagina" detail row
      that has a value for *config_name*; empty list if absent.
    """
    url = doc_record.config_links.get(config_name) or None

    pages: list[int] = []
    for detail in doc_record.details:
        if detail.title.lower().startswith("rif"):
            raw = detail.values.get(config_name, "")
            if raw:
                pages = parse_rif_pagina(raw)
                break  # use the first matching Rif. Pagina row

    return url, pages


# ---------------------------------------------------------------------------
# Local PDF deep-link URL builder
# ---------------------------------------------------------------------------

def build_pdf_page_url(local_path: Path, page_number: int) -> str:
    """
    Build a file:// URL with a #page=N fragment to open a local PDF at a specific page.

    Most desktop PDF viewers (Acrobat, Okular, Evince via GNOME) honour this fragment.
    Returns a plain file:// URL (no fragment) when page_number <= 0.
    """
    uri = local_path.as_uri()
    if page_number > 0:
        return f"{uri}#page={page_number}"
    return uri
