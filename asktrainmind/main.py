from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QFile
from PySide6.QtWidgets import QApplication

from asktrainmind.app.config import resource_path
from asktrainmind.ui.main_window import MainWindow


def load_stylesheet(app: QApplication) -> None:
    qss_path = resource_path("ui/style.qss")
    file = QFile(str(qss_path))
    if file.open(QFile.ReadOnly | QFile.Text):
        app.setStyleSheet(bytes(file.readAll()).decode("utf-8"))


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("AskTrainMind")
    app.setOrganizationName("AskTrainMind")
    load_stylesheet(app)

    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
