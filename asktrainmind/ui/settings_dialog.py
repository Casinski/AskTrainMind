from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

from asktrainmind.app.config import AIConfig


class SettingsDialog(QDialog):
    def __init__(self, config: AIConfig, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings AI")
        self._config = config

        self.provider = QComboBox()
        self.provider.addItems(["null", "openai", "azure"])
        self.provider.setCurrentText(config.provider or "null")

        self.endpoint = QLineEdit(config.endpoint)
        self.model = QLineEdit(config.model)
        self.deployment = QLineEdit(config.deployment)
        self.api_key = QLineEdit(config.api_key)
        self.api_key.setEchoMode(QLineEdit.Password)
        self.vision_enabled = QCheckBox("Abilita Vision (modelli compatibili)")
        self.vision_enabled.setChecked(config.vision_enabled)

        form = QFormLayout()
        form.addRow("Provider", self.provider)
        form.addRow("Endpoint", self.endpoint)
        form.addRow("Model", self.model)
        form.addRow("Deployment", self.deployment)
        form.addRow("API Key", self.api_key)
        form.addRow("", self.vision_enabled)

        save_btn = QPushButton("Save")
        cancel_btn = QPushButton("Cancel")
        save_btn.clicked.connect(self.accept)
        cancel_btn.clicked.connect(self.reject)

        row = QHBoxLayout()
        row.addWidget(save_btn)
        row.addWidget(cancel_btn)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addLayout(row)

    def config(self) -> AIConfig:
        return AIConfig(
            provider=self.provider.currentText(),
            endpoint=self.endpoint.text().strip(),
            model=self.model.text().strip(),
            deployment=self.deployment.text().strip(),
            api_key=self.api_key.text().strip(),
            vision_enabled=self.vision_enabled.isChecked(),
        )
