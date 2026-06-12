from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QGridLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from asktrainmind.app.ai_engine import AnalysisEngine
from asktrainmind.app.config import load_ai_config, save_ai_config, resource_path
from asktrainmind.app.excel_loader import LoadedWorkbook, load_excel_data
from asktrainmind.app.keyword_extractor import MatchResult, rank_function_records
from asktrainmind.app.image_extractor import select_relevant_images
from asktrainmind.app.excel_model import FunctionRecord
from asktrainmind.app.knowledge_base import add_entry, search, migrate_legacy_notes
from asktrainmind.ui.results_view import ResultsView
from asktrainmind.ui.settings_dialog import SettingsDialog
from asktrainmind.ui.widgets import icon_button

# ---------------------------------------------------------------------------
# Background document fetch worker
# ---------------------------------------------------------------------------

class DocumentFetchWorker(QThread):
    """Fetch and extract linked documents off the UI thread."""

    finished = Signal(list)  # emits list[ExtractedDocument]
    progress = Signal(str)   # progress status messages

    def __init__(self, records: list[FunctionRecord], parent=None):
        super().__init__(parent)
        self._records = records

    def run(self) -> None:
        try:
            from asktrainmind.app.document_fetcher import fetch_document
            from asktrainmind.app.document_extractor import extract_document

            results = []
            urls_seen: set[str] = set()

            for record in self._records:
                # Generale link
                if record.generale_link and record.generale_link not in urls_seen:
                    url = record.generale_link
                    urls_seen.add(url)
                    self.progress.emit(f"Scaricando: {url[:60]}…")
                    fetch_result = fetch_document(url)
                    if fetch_result.ok and fetch_result.local_path:
                        extracted = extract_document(url, fetch_result.local_path)
                        results.append(extracted)
                    else:
                        # Return an empty ExtractedDocument with the error
                        from asktrainmind.app.document_extractor import ExtractedDocument
                        from pathlib import Path as _Path
                        results.append(
                            ExtractedDocument(
                                source_url=url,
                                local_path=_Path("."),
                                status=fetch_result.status,
                                message=fetch_result.message,
                            )
                        )

                # Per-configuration document links
                for doc in record.documents:
                    for cfg, link in doc.config_links.items():
                        if not link or link in urls_seen:
                            continue
                        urls_seen.add(link)
                        self.progress.emit(f"Scaricando [{cfg}]: {link[:60]}…")
                        fetch_result = fetch_document(link)
                        if fetch_result.ok and fetch_result.local_path:
                            extracted = extract_document(link, fetch_result.local_path)
                            results.append(extracted)
                        else:
                            from asktrainmind.app.document_extractor import ExtractedDocument
                            from pathlib import Path as _Path
                            results.append(
                                ExtractedDocument(
                                    source_url=link,
                                    local_path=_Path("."),
                                    status=fetch_result.status,
                                    message=fetch_result.message,
                                )
                            )

            self.finished.emit(results)
        except Exception as exc:  # pragma: no cover
            self.progress.emit(f"Errore fetch documenti: {exc}")
            self.finished.emit([])


# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AskTrainMind")
        self.resize(1200, 780)

        self.loaded: LoadedWorkbook | None = None
        self.last_matches: list[MatchResult] = []
        self.selection_is_valid = False
        self._pending_records: list[FunctionRecord] = []
        self._pending_images = []
        self._fetch_worker: DocumentFetchWorker | None = None
        self._current_selected_ids: list[str] = []
        self._results_tab_index: int | None = None

        self._build_ui()
        self._create_menu()

        # Migrate legacy notes on first run (best-effort, non-fatal)
        try:
            migrate_legacy_notes()
        except Exception:
            pass

    def _build_ui(self) -> None:
        root = QWidget()
        self.setCentralWidget(root)
        root_layout = QVBoxLayout(root)

        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(self._on_tab_close_requested)
        root_layout.addWidget(self.tabs)

        main_page = QWidget()
        self.tabs.addTab(main_page, "AskTrainMind")
        layout = QVBoxLayout(main_page)

        self.import_button = icon_button(
            "Import excel file DB fleets",
            resource_path("resources/icons/excel.svg"),
            object_name="importButton",
        )
        self.import_button.setToolTip("Importa manualmente il file Excel DB flotte.")
        self.import_button.clicked.connect(self.on_import_clicked)
        layout.addWidget(self.import_button, alignment=Qt.AlignLeft)

        self.status_label = QLabel("Importa il file Excel DB flotte per iniziare.")
        layout.addWidget(self.status_label)

        top_grid = QGridLayout()
        self.question_box = QTextEdit()
        self.question_box.setPlaceholderText("Come funziona il.......?")
        self.question_box.textChanged.connect(self.on_question_changed)

        self.suggestions = QListWidget()
        self.suggestions.setSelectionMode(QListWidget.MultiSelection)
        self.suggestions.itemSelectionChanged.connect(self.on_selection_changed)

        top_grid.addWidget(self.question_box, 0, 0)
        top_grid.addWidget(self.suggestions, 0, 1)
        top_grid.setColumnStretch(0, 2)
        top_grid.setColumnStretch(1, 1)
        layout.addLayout(top_grid)

        button_column = QVBoxLayout()
        self.find_button = icon_button("Find", resource_path("resources/icons/train.svg"), object_name="findButton")
        self.find_button.setToolTip("Trova gli ID candidati dalla domanda inserita.")
        self.find_button.clicked.connect(self.on_find_clicked)

        self.ask_button = icon_button("Ask", resource_path("resources/icons/train.svg"), object_name="askButton")
        self.ask_button.setToolTip("Genera i risultati per gli ID selezionati.")
        self.ask_button.setEnabled(False)
        self.ask_button.clicked.connect(self.on_ask_clicked)

        button_column.addWidget(self.find_button)
        button_column.addWidget(self.ask_button)
        layout.addLayout(button_column)

        # Document fetch progress label
        self.doc_status_label = QLabel("")
        self.doc_status_label.setObjectName("docStatusLabel")
        self.doc_status_label.setWordWrap(True)
        layout.addWidget(self.doc_status_label)

        self.small_textbox = QTextEdit()
        self.small_textbox.setMaximumHeight(90)
        layout.addWidget(self.small_textbox)

        self.improve_button = QPushButton("Improve Mind")
        self.improve_button.clicked.connect(self.on_improve_clicked)
        layout.addWidget(self.improve_button, alignment=Qt.AlignLeft)

    def _create_menu(self) -> None:
        menu = self.menuBar().addMenu("Settings")
        ai_action = menu.addAction("AI Provider...")
        ai_action.triggered.connect(self.open_settings)

    def _on_tab_close_requested(self, index: int) -> None:
        if index == 0:
            return
        widget = self.tabs.widget(index)
        self.tabs.removeTab(index)
        if widget is not None:
            widget.deleteLater()
        if self._results_tab_index == index:
            self._results_tab_index = None
        elif self._results_tab_index is not None and index < self._results_tab_index:
            self._results_tab_index -= 1

    def on_import_clicked(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Seleziona DB flotte", "", "Excel (*.xlsx)")
        if path:
            self.load_excel(Path(path))

    def load_excel(self, path: Path) -> None:
        try:
            self.loaded = load_excel_data(path)
            self.status_label.setText(f"Workbook caricato: {path}")
        except Exception as exc:
            QMessageBox.critical(self, "Errore Excel", str(exc))

    def on_question_changed(self) -> None:
        self.selection_is_valid = False
        self._update_ask_enabled()

    def on_find_clicked(self) -> None:
        if not self.loaded:
            QMessageBox.information(self, "Workbook", "Importare prima il file Excel.")
            return
        question = self.question_box.toPlainText().strip()
        self.suggestions.clear()
        self.last_matches = rank_function_records(question, self.loaded.records)
        for item in self.last_matches:
            text = f"{item.record.id} — {item.record.funzione} (score {item.score})"
            row = QListWidgetItem(text)
            row.setData(Qt.UserRole, item.record.id)
            self.suggestions.addItem(row)
        self.selection_is_valid = False
        self._update_ask_enabled()

    def on_selection_changed(self) -> None:
        self.selection_is_valid = len(self.suggestions.selectedItems()) > 0
        self._update_ask_enabled()
        self._current_selected_ids = [
            item.data(Qt.UserRole) for item in self.suggestions.selectedItems()
        ]

    def _update_ask_enabled(self) -> None:
        question_ok = bool(self.question_box.toPlainText().strip())
        self.ask_button.setEnabled(self.selection_is_valid and question_ok)

    def _selected_records(self):
        if not self.loaded:
            return []
        selected_ids = {item.data(Qt.UserRole) for item in self.suggestions.selectedItems()}
        return [record for record in self.loaded.records if record.id in selected_ids]

    def on_ask_clicked(self) -> None:
        if not self.ask_button.isEnabled():
            self._update_ask_enabled()
            return
        records = self._selected_records()
        if not records:
            return

        relevant_images, relevance_note = select_relevant_images(records, self.loaded.images if self.loaded else None)
        self._pending_records = records
        self._pending_images = relevant_images
        self._relevance_note = relevance_note

        self._open_results(records, relevant_images, relevance_note, documents=None)

        ai_config = load_ai_config()

        if ai_config.fetch_documents:
            # Fetch documents in background without blocking results rendering.
            self.doc_status_label.setText("⏳ Recupero documenti collegati…")
            self._fetch_worker = DocumentFetchWorker(records, parent=self)
            self._fetch_worker.progress.connect(self.doc_status_label.setText)
            self._fetch_worker.finished.connect(self._on_documents_fetched)
            self._fetch_worker.start()

    def _on_documents_fetched(self, documents: list) -> None:
        self.doc_status_label.setText(
            f"✅ {len(documents)} documento/i processato/i."
            if documents else "ℹ️ Nessun documento scaricato."
        )
        self._update_ask_enabled()

    def _open_results(self, records, relevant_images, relevance_note, documents) -> None:
        # Gather matching KB entries for selected function IDs
        selected_ids = [r.id for r in records]
        kb_entries: list = []
        for fid in selected_ids:
            kb_entries.extend(search(function_id=fid))
        # Also search by question text keywords if no per-ID entries found
        if not kb_entries:
            question = self.question_box.toPlainText().strip()
            if question:
                kb_entries = search(query=question)

        engine = AnalysisEngine(load_ai_config())
        analysis = engine.analyze(
            records,
            images=relevant_images,
            documents=documents or None,
            kb_entries=kb_entries or None,
        )
        if relevance_note:
            analysis.banner = f"{analysis.banner}\n{relevance_note}" if analysis.banner else relevance_note
        results = ResultsView(records, analysis, images=relevant_images, parent=self.tabs)
        if self._results_tab_index is not None and self._results_tab_index < self.tabs.count():
            widget = self.tabs.widget(self._results_tab_index)
            self.tabs.removeTab(self._results_tab_index)
            if widget is not None:
                widget.deleteLater()
        self._results_tab_index = self.tabs.addTab(results, "Risultati")
        self.tabs.setCurrentIndex(self._results_tab_index)
        self._last_results = results

    def on_improve_clicked(self) -> None:
        note = self.small_textbox.toPlainText().strip()
        if not note:
            QMessageBox.information(self, "Improve Mind", "Inserire una nota prima di salvare.")
            return
        question = self.question_box.toPlainText().strip()
        function_ids = list(self._current_selected_ids) if self._current_selected_ids else []
        try:
            add_entry(
                text=note,
                title=question[:80] if question else "Nota utente",
                function_ids=function_ids,
            )
            self.small_textbox.clear()
            QMessageBox.information(self, "Improve Mind", "Nota salvata e indicizzata.")
        except Exception:
            QMessageBox.warning(self, "Improve Mind", "Errore nel salvataggio della nota.")

    def open_settings(self) -> None:
        dialog = SettingsDialog(load_ai_config(), self)
        if dialog.exec():
            save_ai_config(dialog.config())
