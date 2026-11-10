"""Configuração explícita dos modelos locais com teste de reconhecimento."""

from os.path import abspath

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

from docforge.domain.media import OCR_LANGUAGES
from docforge.infrastructure.ocr_models import available_models


class OcrSetupDialog(QDialog):
    def __init__(self, process_factory, directory: str, languages: tuple[str, ...], parent) -> None:
        super().__init__(parent)
        self.setObjectName("ocr_setup_dialog")
        self.setWindowTitle("Configurar OCR local")
        self.setMinimumWidth(560)
        self.process_factory = process_factory
        self.process = None
        self.languages = languages
        self.result_settings: tuple[str, tuple[str, ...]] | None = None
        root = QVBoxLayout(self)
        info = QLabel(
            "Escolha uma pasta local com por.traineddata e/ou eng.traineddata. "
            "O teste reconhece uma amostra interna antes de habilitar os idiomas. "
            "Apenas a pasta e os idiomas validados ficam nas preferências."
        )
        info.setWordWrap(True)
        root.addWidget(info)
        form = QFormLayout()
        row = QHBoxLayout()
        self.directory = QLineEdit(directory)
        self.directory.setAccessibleName("Pasta dos modelos Tesseract")
        self.directory.setReadOnly(True)
        self.choose = QPushButton("Escolher pasta…")
        self.choose.clicked.connect(self._choose)
        row.addWidget(self.directory, 1)
        row.addWidget(self.choose)
        form.addRow("Pasta tessdata", row)
        root.addLayout(form)
        self.status = QLabel()
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        self.status.setWordWrap(True)
        root.addWidget(self.status)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.apply_button = buttons.button(QDialogButtonBox.StandardButton.Ok)
        self.apply_button.setText("Usar modelos validados")
        self.validate = buttons.addButton("Testar modelos", QDialogButtonBox.ButtonRole.ActionRole)
        self.validate.clicked.connect(self._validate)
        disable = buttons.addButton("Desativar OCR", QDialogButtonBox.ButtonRole.ActionRole)
        disable.clicked.connect(self._disable)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)
        self.finished.connect(lambda _result: self._stop())
        self._refresh()

    def _choose(self) -> None:
        value = QFileDialog.getExistingDirectory(
            self, "Escolher pasta tessdata", self.directory.text()
        )
        if value:
            self.directory.setText(abspath(value))
            self.languages = ()
            self._refresh()

    def _refresh(self, message: str = "") -> None:
        models = available_models(self.directory.text())
        busy = self.process is not None
        self.validate.setEnabled(bool(models) and not busy)
        self.choose.setEnabled(not busy)
        self.apply_button.setEnabled(bool(self.languages) and not busy)
        names = ", ".join(OCR_LANGUAGES[code] for code in (self.languages or models))
        if self.languages:
            description = "Idiomas validados: " + names
        elif models:
            description = "Modelos encontrados: " + names
        else:
            description = "Nenhum modelo encontrado. Selecione a pasta dos arquivos .traineddata."
        self.status.setText(message or description)

    def _validate(self) -> None:
        self.languages = ()
        self.process = self.process_factory(self)
        self.process.reply.connect(self._reply)
        self.process.failed.connect(self._error)
        self._refresh("Reconhecendo o texto de teste com os modelos locais…")
        self.process.request("probe_ocr", {"tessdata": self.directory.text()})

    def _stop(self) -> None:
        process, self.process = self.process, None
        if process:
            process.stop()
            process.deleteLater()

    def _reply(self, reply: dict, _payload: bytes) -> None:
        if "error" in reply:
            self._error(reply["error"])
            return
        self._stop()
        self.languages = tuple(reply["result"]["languages"])
        self._refresh()

    def _error(self, message: str) -> None:
        self._stop()
        self._refresh(message)

    def _disable(self) -> None:
        self.result_settings = "", ()
        super().accept()

    def accept(self) -> None:
        if self.languages and self.process is None:
            self.result_settings = self.directory.text(), self.languages
            super().accept()
