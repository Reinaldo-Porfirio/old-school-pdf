"""Diálogo para criar um campo de formulário na área desenhada."""

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from oldschoolpdf.domain.editing import (
    FIELD_KINDS,
    MAX_FIELD_CHOICES,
    MAX_FIELD_NAME,
    field_name,
)
from oldschoolpdf.domain.errors import OldSchoolPDFError

FONT_CHOICES = (("Automático", 0), *((f"{size} pt", size) for size in (8, 9, 10, 11, 12, 14)))


class FieldDialog(QDialog):
    def __init__(self, suggestion: str, taken: set[str], parent) -> None:
        super().__init__(parent)
        self.setObjectName("field_dialog")
        self.setWindowTitle("Criar campo de formulário")
        self.setMinimumWidth(440)
        self.taken = {name.casefold() for name in taken}
        form = QFormLayout(self)
        self.kind = QComboBox()
        self.kind.setObjectName("field_kind")
        for key, label in FIELD_KINDS.items():
            self.kind.addItem(label, key)
        form.addRow("Tipo:", self.kind)
        self.name = QLineEdit(suggestion)
        self.name.setObjectName("field_name")
        self.name.setMaxLength(MAX_FIELD_NAME)
        self.name.setToolTip("Nome interno, único no documento. Aparece ao exportar os dados.")
        form.addRow("Nome:", self.name)
        self.label = QLineEdit()
        self.label.setMaxLength(200)
        self.label.setPlaceholderText("Opcional: dica que aparece ao passar o mouse")
        form.addRow("Dica:", self.label)
        # Só o editor do tipo escolhido fica visível; os ocultos não ocupam espaço.
        self.values = QWidget()
        stack = QVBoxLayout(self.values)
        stack.setContentsMargins(0, 0, 0, 0)
        self.line = QLineEdit()
        self.line.setPlaceholderText("Opcional")
        self.paragraph = QPlainTextEdit()
        self.paragraph.setPlaceholderText("Opcional")
        self.paragraph.setFixedHeight(60)
        self.checked = QCheckBox("Começa marcada")
        self.choices = QPlainTextEdit()
        self.choices.setObjectName("field_choices")
        self.choices.setPlaceholderText("Uma opção por linha. A primeira já vem escolhida.")
        self.choices.setFixedHeight(90)
        self.editors = (self.line, self.paragraph, self.checked, self.choices)
        for widget in self.editors:
            stack.addWidget(widget)
        self.value_label = QLabel("Valor inicial:")
        form.addRow(self.value_label, self.values)
        self.limit = QSpinBox()
        self.limit.setRange(0, 4096)
        self.limit.setSpecialValueText("Sem limite")
        form.addRow("Máximo de caracteres:", self.limit)
        self.font_size = QComboBox()
        for label, size in FONT_CHOICES:
            self.font_size.addItem(label, size)
        self.font_size.setCurrentIndex(self.font_size.findData(11))
        form.addRow("Tamanho da letra:", self.font_size)
        self.required = QCheckBox("Preenchimento obrigatório")
        form.addRow(self.required)
        self.status = QLabel()
        self.status.setWordWrap(True)
        form.addRow(self.status)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.create = buttons.button(QDialogButtonBox.StandardButton.Ok)
        self.create.setText("Criar campo")
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)
        self.kind.currentIndexChanged.connect(self._refresh)
        self.name.textChanged.connect(self._refresh)
        self.choices.textChanged.connect(self._refresh)
        self._refresh()

    def _choice_list(self) -> list[str]:
        return [line.strip() for line in self.choices.toPlainText().splitlines() if line.strip()]

    def _problem(self) -> str:
        try:
            name = field_name(self.name.text())
        except OldSchoolPDFError as error:
            return str(error)
        if name.casefold() in self.taken:
            return f"Já existe um campo chamado {name}."
        if self.kind.currentData() == "choice":
            choices = self._choice_list()
            if not 1 <= len(choices) <= MAX_FIELD_CHOICES:
                return "Escreva ao menos uma opção para a lista."
            if len({choice.casefold() for choice in choices}) != len(choices):
                return "A lista tem opções repetidas."
        return ""

    def _refresh(self) -> None:
        kind = self.kind.currentData()
        pages = {"text": self.line, "multiline": self.paragraph, "checkbox": self.checked}
        current = pages.get(kind, self.choices)
        for widget in self.editors:
            widget.setVisible(widget is current)
        self.value_label.setText("Opções:" if kind == "choice" else "Valor inicial:")
        self.limit.setEnabled(kind in {"text", "multiline"})
        self.font_size.setEnabled(kind != "checkbox")
        problem = self._problem()
        self.status.setText(problem or "O campo será criado na área desenhada. Ctrl+Z desfaz.")
        self.create.setEnabled(not problem)

    def _accept(self) -> None:
        if not self._problem():
            self.accept()

    def result_values(self, region) -> dict:
        kind = self.kind.currentData()
        values = {
            "kind": kind,
            "name": self.name.text().strip(),
            "label": self.label.text().strip(),
            "region": region,
            "required": self.required.isChecked(),
            "font_size": self.font_size.currentData(),
        }
        if kind == "text":
            values.update(value=self.line.text(), max_length=self.limit.value())
        elif kind == "multiline":
            values.update(value=self.paragraph.toPlainText(), max_length=self.limit.value())
        elif kind == "checkbox":
            values["value"] = self.checked.isChecked()
        else:
            values["choices"] = self._choice_list()
        return values
