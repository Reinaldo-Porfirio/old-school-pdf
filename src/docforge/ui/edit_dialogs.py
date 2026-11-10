"""Prévia de intervalos, seleção de arquivos e formulários compatíveis."""

from os.path import abspath
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
)

from docforge.domain.editing import FormField, parse_intervals
from docforge.domain.errors import DocForgeError


def local_pdf_drops(event) -> list[Path]:
    return [
        Path(url.toLocalFile())
        for url in event.mimeData().urls()
        if url.isLocalFile() and not url.host() and url.path().casefold().endswith(".pdf")
    ]


class RangeDialog(QDialog):
    LABELS = {
        "extract": ("Extrair páginas", "Escolher destino"),
        "split": ("Dividir PDF", "Escolher destino"),
        "delete": ("Excluir páginas", "Excluir da cópia de trabalho"),
        "rotate": ("Girar páginas do PDF", "Aplicar rotação"),
    }

    def __init__(self, mode: str, page: int, count: int, parent) -> None:
        super().__init__(parent)
        self.setObjectName("pdf_range_dialog")
        title, action = self.LABELS[mode]
        self.setWindowTitle(title)
        self.setMinimumWidth(450)
        self.mode, self.count = mode, count
        self.ranges: list[tuple[int, int]] = []
        layout = QVBoxLayout(self)
        form = QFormLayout()
        default = f"1-{count}" if mode == "split" and count > 1 else str(page + 1)
        self.pages = QLineEdit(default)
        self.pages.setMaxLength(1800)
        self.pages.setAccessibleName("Páginas ou intervalos")
        self.pages.setObjectName("pdf_ranges")
        form.addRow("Páginas ou intervalos", self.pages)
        self.angle = QComboBox()
        for label, value in (("90° horário", 90), ("180°", 180), ("90° anti-horário", 270)):
            self.angle.addItem(label, value)
        if mode == "rotate":
            form.addRow("Rotação", self.angle)
        layout.addLayout(form)
        details = {
            "split": "Cada intervalo separado por vírgula gera um PDF, na ordem informada.",
            "extract": "As páginas indicadas compõem uma única saída, na ordem informada.",
            "delete": "As páginas selecionadas saem da cópia de trabalho. Você pode desfazer.",
            "rotate": "A nova rotação aparecerá na prévia e na próxima cópia gravada.",
        }
        explanation = QLabel(details[mode])
        explanation.setWordWrap(True)
        layout.addWidget(explanation)
        self.preview = QLabel()
        self.preview.setWordWrap(True)
        layout.addWidget(self.preview)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.apply = buttons.button(QDialogButtonBox.StandardButton.Ok)
        self.apply.setText(action)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.pages.textChanged.connect(self._preview)
        self.pages.selectAll()
        self._preview()

    def _preview(self) -> None:
        try:
            ranges = parse_intervals(self.pages.text(), self.count)
            count = sum(end - start + 1 for start, end in ranges)
            if self.mode == "delete" and count == self.count:
                raise DocForgeError("Deixe ao menos uma página no documento.")
            self.ranges = ranges
            text = f"{count} página(s) selecionada(s) de {self.count}."
            if self.mode == "split":
                text += f" {len(ranges)} arquivo(s) de saída."
        except DocForgeError as error:
            self.ranges = []
            text = str(error)
        self.preview.setText(text)
        self.apply.setEnabled(bool(self.ranges))


class InputList(QListWidget):
    files_dropped = Signal(object)

    def dragEnterEvent(self, event) -> None:
        if local_pdf_drops(event):
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event) -> None:
        if local_pdf_drops(event):
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event) -> None:
        if paths := local_pdf_drops(event):
            event.setDropAction(Qt.DropAction.CopyAction)
            event.accept()
            self.files_dropped.emit(paths)
        else:
            super().dropEvent(event)


class MergeDialog(QDialog):
    def __init__(self, process_factory, parent) -> None:
        super().__init__(parent)
        self.setObjectName("pdf_merge_dialog")
        self.setWindowTitle("Mesclar PDFs")
        self.resize(610, 420)
        self.process_factory = process_factory
        self.process = self._new_process()
        self.finished.connect(lambda _result: self.process.stop())
        self.inspecting = False
        self._details: dict[str, dict] = {}
        layout = QVBoxLayout(self)
        help_text = QLabel(
            "Adicione ou solte PDFs locais e organize a ordem das entradas. "
            "A mesclagem reúne as páginas, anotações e campos. Os metadados globais, "
            "marcadores e anexos dos arquivos continuam nos respectivos originais."
        )
        help_text.setWordWrap(True)
        layout.addWidget(help_text)
        self.inputs = InputList()
        self.inputs.setAccessibleName("Ordem dos PDFs")
        self.inputs.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.inputs.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.inputs.files_dropped.connect(self.add_paths)
        layout.addWidget(self.inputs, 1)
        row = QHBoxLayout()
        self.add = QPushButton("Adicionar PDFs…")
        self.add.clicked.connect(self._pick)
        self.remove = QPushButton("Remover da lista")
        self.remove.clicked.connect(self._remove)
        self.up = QPushButton("Subir")
        self.up.clicked.connect(lambda: self._move(-1))
        self.down = QPushButton("Descer")
        self.down.clicked.connect(lambda: self._move(1))
        for button in (self.add, self.remove, self.up, self.down):
            row.addWidget(button)
        layout.addLayout(row)
        self.status = QLabel()
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.submit = buttons.button(QDialogButtonBox.StandardButton.Ok)
        self.submit.setText("Escolher destino")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.inputs.currentRowChanged.connect(self._refresh)
        self._refresh()

    def _pick(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(self, "Adicionar PDFs", "", "Arquivos PDF (*.pdf)")
        self.add_paths([Path(path) for path in paths])

    def _new_process(self):
        process = self.process_factory(self)
        process.reply.connect(self._received)
        process.failed.connect(self._restart)
        return process

    def _restart(self, message: str) -> None:
        self.process.deleteLater()
        self.process = self._new_process()
        self._failed(message)

    def records(self) -> list[dict]:
        paths = [
            self.inputs.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.inputs.count())
        ]
        return [{"path": path, **self._details.get(path, {})} for path in paths]

    def add_paths(self, paths: list[Path]) -> None:
        if self.inspecting:
            return
        existing = {item["path"].casefold() for item in self.records()}
        for path in paths:
            absolute = Path(abspath(path))
            if str(absolute).casefold() in existing:
                continue
            existing.add(str(absolute).casefold())
            item = QListWidgetItem(absolute.name, self.inputs)
            item.setData(Qt.ItemDataRole.UserRole, str(absolute))
        if self.inputs.count():
            self.inputs.setCurrentRow(self.inputs.count() - 1)
            self.inspecting = True
            self._refresh()
            self.process.request(
                "inspect_inputs", {"paths": [item["path"] for item in self.records()]}
            )

    def _received(self, reply: dict, _data: bytes) -> None:
        if "error" in reply:
            self._failed(reply["error"])
            return
        for index, info in enumerate(reply["result"]["items"]):
            item = self.inputs.item(index)
            path = item.data(Qt.ItemDataRole.UserRole)
            self._details[path] = info
            suffix = " · assinatura indicada" if info["signed"] else ""
            item.setText(f"{Path(path).name}  ·  {info['pages']} pág.{suffix}")
        self.inspecting = False
        self._refresh()

    def _failed(self, message: str) -> None:
        self.inspecting = False
        self._refresh()
        self.status.setText(message)

    def _remove(self) -> None:
        if self.inputs.currentRow() >= 0:
            item = self.inputs.takeItem(self.inputs.currentRow())
            self._details.pop(item.data(Qt.ItemDataRole.UserRole), None)
            self._refresh()

    def _move(self, delta: int) -> None:
        row = self.inputs.currentRow()
        if 0 <= row + delta < self.inputs.count():
            item = self.inputs.takeItem(row)
            self.inputs.insertItem(row + delta, item)
            self.inputs.setCurrentRow(row + delta)

    def _refresh(self, *_args) -> None:
        entries = self.records()
        row = self.inputs.currentRow()
        ready = not self.inspecting and all("pages" in entry for entry in entries)
        self.inputs.setEnabled(not self.inspecting)
        self.add.setEnabled(not self.inspecting)
        self.remove.setEnabled(not self.inspecting and row >= 0)
        self.up.setEnabled(not self.inspecting and row > 0)
        self.down.setEnabled(not self.inspecting and 0 <= row < len(entries) - 1)
        self.submit.setEnabled(ready and len(entries) >= 2)
        if self.inspecting:
            message = "Conferindo as páginas de entrada…"
        elif ready:
            count = sum(entry["pages"] for entry in entries)
            message = f"{len(entries)} PDF(s) · {count} página(s) na saída."
        else:
            message = "Remova a entrada inválida ou escolha outros PDFs."
        self.status.setText(message)


class FormDialog(QDialog):
    def __init__(self, fields: tuple[FormField, ...], parent) -> None:
        super().__init__(parent)
        self.setObjectName("pdf_form_dialog")
        self.setWindowTitle("Preencher campo do PDF")
        self.setMinimumWidth(430)
        self.fields = fields
        layout = QFormLayout(self)
        self.selector = QComboBox()
        for field in fields:
            self.selector.addItem(field.name + ("" if field.editable else " · leitura"))
        layout.addRow("Campo", self.selector)
        self.editors = QStackedWidget()
        self.line = QLineEdit()
        self.line.setObjectName("pdf_form_text")
        self.paragraph = QPlainTextEdit()
        self.choice = QComboBox()
        for editor in (self.line, self.paragraph, self.choice):
            self.editors.addWidget(editor)
        layout.addRow("Valor", self.editors)
        self.details = QLabel()
        self.details.setWordWrap(True)
        layout.addRow(self.details)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.apply = buttons.button(QDialogButtonBox.StandardButton.Ok)
        self.apply.setText("Aplicar valor")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)
        self.selector.currentIndexChanged.connect(self._switch)
        self._switch(0)

    def _switch(self, index: int) -> None:
        field = self.fields[index]
        if field.kind == "text" and field.multiline:
            self.paragraph.setPlainText(field.value)
            self.editors.setCurrentWidget(self.paragraph)
        elif field.kind == "text" or not field.choices:
            self.line.setMaxLength(field.max_length)
            self.line.setText(field.value)
            self.editors.setCurrentWidget(self.line)
        else:
            self.choice.clear()
            for option in field.choices:
                label = (
                    ("Desmarcado" if option == "Off" else "Marcado")
                    if field.kind == "checkbox"
                    else option
                )
                self.choice.addItem(label, option)
            selected = self.choice.findData(field.value)
            self.choice.setCurrentIndex(max(0, selected))
            self.editors.setCurrentWidget(self.choice)
        self.editors.setEnabled(field.editable)
        self.apply.setEnabled(field.editable)
        self.details.setText(
            "O valor será atualizado na cópia de trabalho."
            if field.editable
            else "Campo somente para leitura. Pode conter scripts ou usar um formato incompatível."
        )

    def value(self) -> dict:
        field = self.fields[self.selector.currentIndex()]
        if self.editors.currentWidget() is self.line:
            value = self.line.text()
        elif self.editors.currentWidget() is self.paragraph:
            value = self.paragraph.toPlainText()
        else:
            value = self.choice.currentData()
        return {"xref": field.xref, "value": value}
