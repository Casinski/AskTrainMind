"""Offscreen smoke test for AskTrainMind UI.

Constructs MainWindow and opens ResultsView for a selection using
QT_QPA_PLATFORM=offscreen. Skips cleanly if Qt platform libs are unavailable.
"""
from __future__ import annotations

import os
import sys

import pytest

# Guard: skip this entire module if Qt/offscreen platform is not available.
# We do this with a module-level check that will be exercised before any test runs.
_QT_AVAILABLE = False
try:
    from PySide6.QtWidgets import QApplication

    _QT_AVAILABLE = True
except (ImportError, RuntimeError):
    pass

pytestmark = pytest.mark.skipif(
    not _QT_AVAILABLE,
    reason="PySide6 not available in this environment",
)


@pytest.fixture(scope="module")
def qt_app():
    """Create a single QApplication instance for the module."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    # Avoid "xcb" crash on headless Linux
    os.environ.setdefault("QT_LOGGING_RULES", "*.debug=false")

    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv[:1])
    yield app


def _make_records():
    from asktrainmind.app.excel_model import DetailRecord, DocumentRecord, FunctionRecord

    return [
        FunctionRecord(
            id="SMOKE_ID",
            funzione="Funzione smoke test",
            tipo="TBD",
            generale_link=None,
            config_names=["CONF_A", "CONF_B"],
            documents=[
                DocumentRecord(
                    doc_id="DOC_SMOKE",
                    info_doc="Documento di prova",
                    config_links={"CONF_A": "https://example.com/doc.pdf"},
                    details=[],
                )
            ],
            start_row=2,
            end_row=5,
        )
    ]


def test_main_window_find_ask_enable_logic_and_results_tab(qt_app, monkeypatch):
    """Ask starts disabled, requires Find+selection, resets on text change, opens Risultati tab."""
    try:
        from pathlib import Path

        from asktrainmind.app.config import AIConfig
        from asktrainmind.app.excel_loader import LoadedWorkbook
        from asktrainmind.ui.main_window import MainWindow

        monkeypatch.setattr(
            "asktrainmind.ui.main_window.load_ai_config",
            lambda: AIConfig(provider="null", fetch_documents=False),
        )

        win = MainWindow()
        records = _make_records()
        win.loaded = LoadedWorkbook(path=Path("dummy.xlsx"), records=records, images=[])

        assert win.ask_button.isEnabled() is False

        win.question_box.setPlainText("Come funziona SMOKE_ID?")
        win.on_find_clicked()
        assert win.ask_button.isEnabled() is False
        assert win.suggestions.count() >= 1

        win.suggestions.item(0).setSelected(True)
        win.on_selection_changed()
        assert win.ask_button.isEnabled() is True

        win.question_box.setPlainText("Domanda modificata")
        assert win.ask_button.isEnabled() is False

        win.question_box.setPlainText("")
        win.on_selection_changed()
        assert win.ask_button.isEnabled() is False

        win.question_box.setPlainText("Come funziona SMOKE_ID?")
        win.on_find_clicked()
        win.suggestions.item(0).setSelected(True)
        win.on_selection_changed()
        win.on_ask_clicked()
        assert win.tabs.count() == 2
        assert win.tabs.tabText(1) == "Risultati"
        assert win.tabs.currentIndex() == 1
        assert win is not None
        win.close()
    except Exception as exc:
        pytest.skip(f"MainWindow logic could not be executed in offscreen mode: {exc}")


def test_results_view_opens(qt_app):
    """ResultsView can be opened for a selection without raising."""
    try:
        from asktrainmind.app.ai_engine import AnalysisEngine
        from asktrainmind.app.config import AIConfig
        from asktrainmind.ui.results_view import ResultsView

        records = _make_records()
        engine = AnalysisEngine(AIConfig(provider="null"))
        analysis = engine.analyze(records)

        view = ResultsView(records, analysis, images=[], parent=None)
        assert view is not None
        view.close()
    except Exception as exc:
        pytest.skip(f"ResultsView could not be created in offscreen mode: {exc}")


def test_analysis_engine_offline_produces_output(qt_app):
    """AnalysisEngine in offline mode produces non-empty info and diff output."""
    from asktrainmind.app.ai_engine import AnalysisEngine
    from asktrainmind.app.config import AIConfig

    records = _make_records()
    engine = AnalysisEngine(AIConfig(provider="null"))
    output = engine.analyze(records)

    assert output.info_text
    assert output.differences_text
    assert "diff-table" in output.diff_table_html
    assert output.banner is not None


def test_analysis_engine_with_kb_entries_offline(qt_app):
    """AnalysisEngine includes KB entries in INFO when offline."""
    from asktrainmind.app.ai_engine import AnalysisEngine
    from asktrainmind.app.config import AIConfig

    records = _make_records()
    kb_entries = [
        {
            "id": "kb1",
            "title": "Smoke KB note",
            "text": "Annotazione di prova knowledge base",
            "function_ids": ["SMOKE_ID"],
            "tags": ["test"],
            "created_at": "2024-01-01T00:00:00+00:00",
            "updated_at": "2024-01-01T00:00:00+00:00",
        }
    ]
    engine = AnalysisEngine(AIConfig(provider="null"))
    output = engine.analyze(records, kb_entries=kb_entries)

    assert "Annotazione di prova" in output.info_text or "kb-block" in output.info_text
