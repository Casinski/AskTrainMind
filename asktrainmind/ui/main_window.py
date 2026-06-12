from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from asktrainmind.app.ai_engine import AnalysisEngine
from asktrainmind.app.config import load_ai_config, save_ai_config, resource_path
from asktrainmind.app.excel_loader import LoadedWorkbook, load_excel_data
from asktrainmind.app.keyword_extractor import MatchResult, rank_function_records
from asktrainmind.app.sharepoint import download_workbook
from asktrainmind.app.image_extractor import select_relevant_images
from asktrainmind.ui.results_view import ResultsView
from asktrainmind.ui.settings_dialog import SettingsDialog
from asktrainmind.ui.widgets import icon_button

SHAREPOINT_FOLDER_URL = "https://gruppofsitaliane.sharepoint.com/:f:/r/sites/IngegneriaETReMezziLeggeri-Trenitalia/Shared%20Documents/Prova%20Doc%20ETR1000?csf=1&web=1&e=bmZNVq"
TARGET_FILE = "DB Flotte ETR1000 Ver_0.5_MM.xlsx"


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AskTrainMind")
        self.resize(1200, 780)

        self.loaded: LoadedWorkbook | None = None
        self.last_matches: list[MatchResult] = []
        self.selection_is_valid = False

        self._build_ui()
        self._create_menu()
        self._attempt_sharepoint_load()

    def _build_ui(self) -> None:
        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)

        self.import_button = icon_button(
            "Import excel file DB fleets",
            resource_path("resources/icons/excel.svg"),
            object_name="importButton",
        )
        self.import_button.clicked.connect(self.on_import_clicked)
        layout.addWidget(self.import_button, alignment=Qt.AlignLeft)

        self.status_label = QLabel("Caricare un file Excel per iniziare.")
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

        button_row = QHBoxLayout()
        self.ask_button = icon_button("Ask", resource_path("resources/icons/train.svg"), object_name="askButton")
        self.ask_button.setEnabled(False)
        self.ask_button.clicked.connect(self.on_ask_clicked)

        self.find_button = icon_button("Find", resource_path("resources/icons/train.svg"), object_name="askButton")
        self.find_button.clicked.connect(self.on_find_clicked)

        button_row.addWidget(self.ask_button)
        button_row.addWidget(self.find_button)
        layout.addLayout(button_row)

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

    def _attempt_sharepoint_load(self) -> None:
        result = download_workbook(SHAREPOINT_FOLDER_URL, TARGET_FILE)
        if result.ok and result.local_path:
            self.load_excel(result.local_path)
            self.status_label.setText(f"Caricato automaticamente da SharePoint: {result.local_path}")
        else:
            self.status_label.setText(
                f"SharePoint non disponibile ({result.status}). Usa Import excel file DB fleets."
            )

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
        self.ask_button.setEnabled(False)

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
        self.ask_button.setEnabled(False)

    def on_selection_changed(self) -> None:
        self.selection_is_valid = len(self.suggestions.selectedItems()) > 0
        self.ask_button.setEnabled(self.selection_is_valid)

    def _selected_records(self):
        if not self.loaded:
            return []
        selected_ids = {item.data(Qt.UserRole) for item in self.suggestions.selectedItems()}
        return [record for record in self.loaded.records if record.id in selected_ids]

    def on_ask_clicked(self) -> None:
        if not self.selection_is_valid:
            self.ask_button.setEnabled(False)
            return
        records = self._selected_records()
        if not records:
            return
        relevant_images, relevance_note = select_relevant_images(records, self.loaded.images if self.loaded else None)
        engine = AnalysisEngine(load_ai_config())
        analysis = engine.analyze(records, images=relevant_images)
        if relevance_note:
            analysis.banner = f"{analysis.banner}\n{relevance_note}" if analysis.banner else relevance_note
        results = ResultsView(records, analysis, images=relevant_images, parent=self)
        results.resize(1100, 780)
        results.show()
        self._last_results = results

    def on_improve_clicked(self) -> None:
        note = self.small_textbox.toPlainText().strip()
        target = Path.home() / ".asktrainmind_notes.txt"
        with target.open("a", encoding="utf-8") as handle:
            handle.write(note + "\n")
        QMessageBox.information(self, "Improve Mind", "Nota salvata localmente.")

    def open_settings(self) -> None:
        dialog = SettingsDialog(load_ai_config(), self)
        if dialog.exec():
            save_ai_config(dialog.config())
