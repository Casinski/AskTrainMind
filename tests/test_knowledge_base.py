"""Tests for asktrainmind.app.knowledge_base."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

import asktrainmind.app.knowledge_base as kb_module
from asktrainmind.app.knowledge_base import (
    add_entry,
    delete_entry,
    list_entries,
    migrate_legacy_notes,
    search,
    update_entry,
)


@pytest.fixture(autouse=True)
def isolated_kb(tmp_path, monkeypatch):
    """Redirect KB storage to a temp directory for each test."""
    monkeypatch.setattr(kb_module, "_kb_path", lambda: tmp_path / "knowledge.json")
    yield tmp_path


# ---------------------------------------------------------------------------
# CRUD round-trips
# ---------------------------------------------------------------------------

def test_add_and_list_entry():
    entry = add_entry(text="Test note", title="My title")
    entries = list_entries()
    assert len(entries) == 1
    assert entries[0]["id"] == entry["id"]
    assert entries[0]["text"] == "Test note"
    assert entries[0]["title"] == "My title"


def test_add_multiple_and_list_most_recent_first():
    e1 = add_entry(text="First")
    e2 = add_entry(text="Second")
    entries = list_entries()
    # Most recent first: e2 should be first (higher created_at)
    assert entries[0]["id"] == e2["id"]
    assert entries[1]["id"] == e1["id"]


def test_add_entry_with_all_fields():
    entry = add_entry(
        text="Detail note",
        title="A title",
        function_ids=["ID_001", "ID_002"],
        config_name="VZI_IT_Base",
        doc_id="FS_DM1",
        tags=["circuito", "FAM"],
    )
    assert entry["function_ids"] == ["ID_001", "ID_002"]
    assert entry["config_name"] == "VZI_IT_Base"
    assert entry["doc_id"] == "FS_DM1"
    assert "circuito" in entry["tags"]
    assert "id" in entry
    assert "created_at" in entry
    assert "updated_at" in entry


def test_update_entry():
    entry = add_entry(text="Original text", title="T1")
    original_updated = entry["updated_at"]
    result = update_entry(entry["id"], text="Updated text")
    assert result is True
    entries = list_entries()
    assert entries[0]["text"] == "Updated text"
    assert entries[0]["updated_at"] >= original_updated


def test_update_entry_not_found():
    result = update_entry("nonexistent-id", text="x")
    assert result is False


def test_delete_entry():
    e1 = add_entry(text="Keep")
    e2 = add_entry(text="Delete me")
    result = delete_entry(e2["id"])
    assert result is True
    entries = list_entries()
    assert len(entries) == 1
    assert entries[0]["id"] == e1["id"]


def test_delete_entry_not_found():
    result = delete_entry("nonexistent-id")
    assert result is False


def test_list_entries_empty():
    assert list_entries() == []


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------

def test_search_by_text():
    add_entry(text="Circuito elettrico del FAM", title="FAM info")
    add_entry(text="Funzione freno reostatico", title="Freno")
    results = search(query="FAM")
    assert len(results) == 1
    assert "FAM" in results[0]["text"]


def test_search_by_function_id():
    add_entry(text="Note for ID_001", function_ids=["ID_001"])
    add_entry(text="Note for ID_002", function_ids=["ID_002"])
    results = search(function_id="ID_001")
    assert len(results) == 1
    assert "ID_001" in results[0]["function_ids"]


def test_search_by_tags():
    add_entry(text="Note with circuito tag", tags=["circuito"])
    add_entry(text="Note with freno tag", tags=["freno"])
    results = search(tags=["circuito"])
    assert len(results) == 1


def test_search_combined_query_and_function_id():
    add_entry(text="FAM note", function_ids=["ID_001"])
    add_entry(text="FAM note for other", function_ids=["ID_002"])
    results = search(query="FAM", function_id="ID_001")
    assert len(results) == 1
    assert results[0]["function_ids"] == ["ID_001"]


def test_search_no_results():
    add_entry(text="Something")
    results = search(query="zzznomatch")
    assert results == []


def test_search_empty_query_returns_all():
    add_entry(text="A")
    add_entry(text="B")
    assert len(search()) == 2


# ---------------------------------------------------------------------------
# Corrupt-file resilience
# ---------------------------------------------------------------------------

def test_corrupt_file_returns_empty_kb(tmp_path, monkeypatch):
    kb_path = tmp_path / "knowledge.json"
    kb_path.write_text("NOT VALID JSON {{{{", encoding="utf-8")
    monkeypatch.setattr(kb_module, "_kb_path", lambda: kb_path)
    assert list_entries() == []


def test_corrupt_file_add_still_works(tmp_path, monkeypatch):
    kb_path = tmp_path / "knowledge.json"
    kb_path.write_text("NOT VALID JSON", encoding="utf-8")
    monkeypatch.setattr(kb_module, "_kb_path", lambda: kb_path)
    entry = add_entry(text="New note after corrupt")
    assert entry["text"] == "New note after corrupt"
    assert len(list_entries()) == 1


def test_non_list_json_returns_empty(tmp_path, monkeypatch):
    kb_path = tmp_path / "knowledge.json"
    kb_path.write_text('{"key": "value"}', encoding="utf-8")
    monkeypatch.setattr(kb_module, "_kb_path", lambda: kb_path)
    assert list_entries() == []


# ---------------------------------------------------------------------------
# Legacy notes migration
# ---------------------------------------------------------------------------

def test_migrate_legacy_notes(tmp_path, monkeypatch):
    legacy_file = tmp_path / ".asktrainmind_notes.txt"
    legacy_file.write_text("Note uno\nNote due\nNote tre\n", encoding="utf-8")
    monkeypatch.setattr(kb_module, "_LEGACY_FILE", legacy_file)

    count = migrate_legacy_notes()

    assert count == 3
    entries = list_entries()
    # 3 notes + 1 sentinel = 4 entries
    texts = [e["text"] for e in entries]
    assert "Note uno" in texts
    assert "Note due" in texts
    assert "Note tre" in texts


def test_migrate_legacy_notes_idempotent(tmp_path, monkeypatch):
    legacy_file = tmp_path / ".asktrainmind_notes.txt"
    legacy_file.write_text("Note unica\n", encoding="utf-8")
    monkeypatch.setattr(kb_module, "_LEGACY_FILE", legacy_file)

    count1 = migrate_legacy_notes()
    count2 = migrate_legacy_notes()

    assert count1 == 1
    assert count2 == 0  # Already migrated


def test_migrate_legacy_notes_no_file(tmp_path, monkeypatch):
    missing = tmp_path / ".nonexistent_notes.txt"
    monkeypatch.setattr(kb_module, "_LEGACY_FILE", missing)

    count = migrate_legacy_notes()
    assert count == 0
    assert list_entries() == []


def test_migrate_legacy_notes_skips_blank_lines(tmp_path, monkeypatch):
    legacy_file = tmp_path / ".asktrainmind_notes.txt"
    legacy_file.write_text("\nNote valida\n\n   \n", encoding="utf-8")
    monkeypatch.setattr(kb_module, "_LEGACY_FILE", legacy_file)

    count = migrate_legacy_notes()
    assert count == 1
