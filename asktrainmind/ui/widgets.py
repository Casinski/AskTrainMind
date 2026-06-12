from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QPushButton


def icon_button(text: str, icon_path: Path, object_name: str | None = None) -> QPushButton:
    button = QPushButton(text)
    button.setIcon(QIcon(str(icon_path)))
    if object_name:
        button.setObjectName(object_name)
    return button
