"""Persistent knowledge base for AskTrainMind user annotations.

Entries are stored in ``appdata_dir()/knowledge.json`` as a JSON list.
The module is dependency-free and never raises on corrupt/missing files.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from asktrainmind.app.config import appdata_dir

_KB_FILE = "knowledge.json"
_LEGACY_FILE = Path.home() / ".asktrainmind_notes.txt"


# ---------------------------------------------------------------------------
# Schema helpers
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _make_entry(
    text: str,
    title: str = "",
    function_ids: list[str] | None = None,
    config_name: str = "",
    doc_id: str = "",
    tags: list[str] | None = None,
) -> dict[str, Any]:
    now = _now_iso()
    return {
        "id": str(uuid.uuid4()),
        "function_ids": list(function_ids or []),
        "config_name": config_name,
        "doc_id": doc_id,
        "title": title,
        "text": text,
        "tags": list(tags or []),
        "created_at": now,
        "updated_at": now,
    }


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def _kb_path() -> Path:
    return appdata_dir() / _KB_FILE


def _load_all() -> list[dict[str, Any]]:
    path = _kb_path()
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return data
    except (json.JSONDecodeError, OSError, ValueError):
        pass
    return []


def _save_all(entries: list[dict[str, Any]]) -> None:
    try:
        _kb_path().write_text(
            json.dumps(entries, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    except OSError:
        pass


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def add_entry(
    text: str,
    title: str = "",
    function_ids: list[str] | None = None,
    config_name: str = "",
    doc_id: str = "",
    tags: list[str] | None = None,
) -> dict[str, Any]:
    """Create and persist a new KB entry. Returns the new entry."""
    entry = _make_entry(
        text=text,
        title=title,
        function_ids=function_ids,
        config_name=config_name,
        doc_id=doc_id,
        tags=tags,
    )
    entries = _load_all()
    entries.append(entry)
    _save_all(entries)
    return entry


def update_entry(entry_id: str, **kwargs: Any) -> bool:
    """Update fields of an existing entry by id. Returns True if found."""
    entries = _load_all()
    for entry in entries:
        if entry.get("id") == entry_id:
            for key, value in kwargs.items():
                if key in entry:
                    entry[key] = value
            entry["updated_at"] = _now_iso()
            _save_all(entries)
            return True
    return False


def delete_entry(entry_id: str) -> bool:
    """Delete an entry by id. Returns True if found and removed."""
    entries = _load_all()
    new_entries = [e for e in entries if e.get("id") != entry_id]
    if len(new_entries) == len(entries):
        return False
    _save_all(new_entries)
    return True


def list_entries() -> list[dict[str, Any]]:
    """Return all KB entries (most recent first)."""
    entries = _load_all()
    return sorted(entries, key=lambda e: e.get("created_at", ""), reverse=True)


def search(
    query: str = "",
    function_id: str = "",
    tags: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Search entries by text query, function_id, or tags. Combines filters with AND logic."""
    entries = list_entries()
    results = []
    query_lower = query.strip().lower()
    tag_set = {t.lower() for t in (tags or [])}

    for entry in entries:
        if query_lower:
            haystack = " ".join([
                entry.get("title", ""),
                entry.get("text", ""),
                " ".join(entry.get("tags", [])),
                " ".join(entry.get("function_ids", [])),
            ]).lower()
            if query_lower not in haystack:
                continue

        if function_id:
            if function_id not in entry.get("function_ids", []):
                continue

        if tag_set:
            entry_tags = {t.lower() for t in entry.get("tags", [])}
            if not tag_set.intersection(entry_tags):
                continue

        results.append(entry)
    return results


# ---------------------------------------------------------------------------
# Legacy migration
# ---------------------------------------------------------------------------

def migrate_legacy_notes() -> int:
    """Import entries from ~/.asktrainmind_notes.txt into the KB (best-effort).

    Returns the number of entries imported. Non-fatal on any error.
    """
    try:
        if not _LEGACY_FILE.exists():
            return 0
        # Check if already migrated (sentinel entry)
        entries = _load_all()
        for e in entries:
            if e.get("doc_id") == "__legacy_migrated__":
                return 0  # already done

        lines = _LEGACY_FILE.read_text(encoding="utf-8").splitlines()
        count = 0
        for line in lines:
            line = line.strip()
            if line:
                add_entry(text=line, title="Nota legacy", tags=["legacy"])
                count += 1

        # Write sentinel so we don't import again
        if count > 0:
            sentinel = _make_entry(
                text="Migrazione note legacy completata.",
                title="Migrazione legacy",
                doc_id="__legacy_migrated__",
                tags=["legacy", "migrazione"],
            )
            all_entries = _load_all()
            all_entries.append(sentinel)
            _save_all(all_entries)

        return count
    except Exception:  # pragma: no cover
        return 0
