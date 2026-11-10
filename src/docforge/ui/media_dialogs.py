"""Diálogos de processamento local e relatório de lote."""

from os.path import abspath, normcase
from pathlib import Path

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
)

from docforge.domain.editing import parse_intervals
from docforge.domain.errors import DocForgeError
from docforge.domain.media import (
    IMAGE_EXTENSIONS,
    MAX_BATCH_INPUTS,
    MEDIA_DPI,
    MEDIA_LABELS,
    OCR_LANGUAGES,
    MediaOperation,
    MediaOptions,
    MediaRequest,
)
from docforge.domain.tasks import TaskState
from docforge.ui.docks import STATE_LABELS

RANGE_OPERATIONS = {
    MediaOperation.OCR,
    MediaOperation.RENDER,
    MediaOperation.TEXT,
    MediaOperation.EXTRACT_IMAGES,
}
MUTATING_OPERATIONS = {
    MediaOperation.OCR,
    MediaOperation.OPTIMIZE,
    MediaOperation.SPLIT,
    MediaOperation.MERGE,
}
OPERATION_NOTES = {
    MediaOperation.OCR: (
        "A cópia recebe texto pesquisável com a aparência original. Páginas com texto são puladas."
    ),
    MediaOperation.RENDER: "Cada página selecionada vira uma imagem com as anotações visíveis.",
    MediaOperation.IMAGES_PDF: (
        "As imagens entram na ordem da lista, com dimensões e orientações próprias. "
        "TIFFs podem ter várias páginas."
    ),
    MediaOperation.TEXT: "A saída em texto simples usa UTF-8 e separa o conteúdo por página.",
    MediaOperation.EXTRACT_IMAGES: "Exporta uma imagem por objeto incorporado compartilhado.",
    MediaOperation.OPTIMIZE: "Compara tamanhos e publica uma cópia quando houver redução.",
    MediaOperation.SPLIT: "Cria partes consecutivas. A última pode conter menos páginas.",
    MediaOperation.MERGE: "Os PDFs entram na ordem da lista e produzem um único arquivo.",
}


class BatchDialog(QDialog):
    def __init__(
        self,
        mode: MediaOperation,
        tessdata: str,
        languages: tuple[str, ...],
        suggested: Path | None,
        preview,
        parent,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("media_batch_dialog")
        self.setWindowTitle("Processamento local")
        self.resize(740, 630)
        self.setMinimumWidth(640)
        self.tessdata = tessdata
        self.suggested = suggested
        self.request: MediaRequest | None = None
        root = QVBoxLayout(self)
        self.form = QFormLayout()
        self.operation = QComboBox()
        self.operation.setObjectName("media_operation")
        for choice, label in MEDIA_LABELS.items():
            self.operation.addItem(label, choice.value)
            if choice == MediaOperation.OCR and not languages:
                self.operation.model().item(self.operation.count() - 1).setEnabled(False)
        self.operation.setCurrentIndex(self.operation.findData(mode.value))
        self.form.addRow("Operação", self.operation)
        self.ranges = QLineEdit()
        self.ranges.setObjectName("media_pages")
        self.ranges.setMaxLength(1800)
        self.ranges.setPlaceholderText("Todas as páginas")
        self.ranges.setToolTip("Use páginas e intervalos como 2–4,6–8.")
        self.form.addRow("Páginas", self.ranges)
        self.dpi = QComboBox()
        for dpi in MEDIA_DPI:
            self.dpi.addItem(f"{dpi} DPI", dpi)
        self.dpi.setCurrentIndex(self.dpi.findData(200))
        self.form.addRow("Resolução", self.dpi)
        self.language = QComboBox()
        for language in languages:
            self.language.addItem(OCR_LANGUAGES[language], language)
        if len(languages) == 2:
            self.language.addItem("Português e inglês", "por+eng")
        self.form.addRow("Idioma", self.language)
        self.format = QComboBox()
        self.format.addItem("PNG (sem perda)", "png")
        self.format.addItem("JPEG (qualidade 90)", "jpg")
        self.form.addRow("Formato de imagem", self.format)
        self.reduce = QCheckBox("Recomprimir imagens e tentar reduzir a resolução (com perda)")
        self.reduce.setToolTip("O motor reduz em etapas. A referência de resolução é 150 DPI.")
        self.form.addRow("Imagens", self.reduce)
        self.split_size = QSpinBox()
        self.split_size.setRange(1, 1000)
        self.form.addRow("Páginas por parte", self.split_size)
        self.confirm_signed = QCheckBox(
            "Aceito o risco de invalidar assinaturas digitais nas cópias"
        )
        self.form.addRow("PDFs assinados", self.confirm_signed)
        root.addLayout(self.form)
        self.note = QLabel()
        self.note.setWordWrap(True)
        self.note.setProperty("role", "muted")
        root.addWidget(self.note)

        body = QHBoxLayout()
        self.files = QListWidget()
        self.files.setObjectName("media_files")
        self.files.setAccessibleName("Ordem dos arquivos de entrada")
        self.files.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        self.files.setDefaultDropAction(Qt.DropAction.MoveAction)
        body.addWidget(self.files, 1)
        self.preview = QLabel()
        self.preview.setMinimumSize(110, 120)
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setAccessibleName("Prévia da página aberta")
        self._has_preview = preview is not None and not preview.isNull()
        if self._has_preview:
            self.preview.setPixmap(
                preview.scaled(
                    QSize(106, 138),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
        body.addWidget(self.preview)
        root.addLayout(body, 1)
        row = QHBoxLayout()
        self.add = QPushButton("Adicionar arquivos…")
        self.add.clicked.connect(self._pick_inputs)
        self.remove = QPushButton("Remover da lista")
        self.remove.clicked.connect(self._remove)
        self.up = QPushButton("Subir")
        self.up.clicked.connect(lambda: self._move(-1))
        self.down = QPushButton("Descer")
        self.down.clicked.connect(lambda: self._move(1))
        for button in (self.add, self.remove, self.up, self.down):
            row.addWidget(button)
        row.addStretch()
        root.addLayout(row)

        destination = QHBoxLayout()
        self.destination = QLineEdit()
        self.destination.setObjectName("media_destination")
        self.destination.setAccessibleName("Pasta de saída")
        self.destination.setReadOnly(True)
        self.destination.setPlaceholderText("Selecione uma pasta local para os resultados")
        pick = QPushButton("Escolher pasta…")
        pick.clicked.connect(self._pick_destination)
        destination.addWidget(self.destination, 1)
        destination.addWidget(pick)
        root.addLayout(destination)
        self.status = QLabel()
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        self.status.setWordWrap(True)
        root.addWidget(self.status)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.run_button = buttons.button(QDialogButtonBox.StandardButton.Ok)
        self.run_button.setText("Adicionar à fila")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)
        self.operation.currentIndexChanged.connect(self._mode_changed)
        self.files.currentRowChanged.connect(self._refresh)
        self.destination.textChanged.connect(self._refresh)
        self.ranges.textChanged.connect(self._refresh)
        self._mode_changed()
        if suggested:
            self.add_paths([suggested])

    @property
    def mode(self) -> MediaOperation:
        return MediaOperation(self.operation.currentData())

    def paths(self) -> tuple[Path, ...]:
        return tuple(
            Path(self.files.item(i).data(Qt.ItemDataRole.UserRole))
            for i in range(self.files.count())
        )

    def _extensions(self) -> set[str]:
        return IMAGE_EXTENSIONS if self.mode == MediaOperation.IMAGES_PDF else {".pdf"}

    def add_paths(self, paths) -> None:
        keys = {normcase(path) for path in self.paths()}
        for raw in paths:
            path = Path(abspath(raw))
            if path.suffix.casefold() not in self._extensions() or normcase(path) in keys:
                continue
            if self.files.count() == MAX_BATCH_INPUTS:
                break
            keys.add(normcase(path))
            item = QListWidgetItem(path.name, self.files)
            item.setData(Qt.ItemDataRole.UserRole, str(path))
            item.setToolTip(str(path))
        if self.files.count() and self.files.currentRow() < 0:
            self.files.setCurrentRow(0)
        self._refresh()

    def _pick_inputs(self) -> None:
        file_filter = (
            "Imagens (*.png *.jpg *.jpeg *.tif *.tiff)"
            if self.mode == MediaOperation.IMAGES_PDF
            else "Arquivos PDF (*.pdf)"
        )
        paths, _ = QFileDialog.getOpenFileNames(self, "Adicionar entradas ao lote", "", file_filter)
        self.add_paths(paths)

    def _pick_destination(self) -> None:
        directory = QFileDialog.getExistingDirectory(
            self, "Pasta de saída", self.destination.text()
        )
        if directory:
            self.destination.setText(str(Path(abspath(directory))))

    def _remove(self) -> None:
        if self.files.currentRow() >= 0:
            self.files.takeItem(self.files.currentRow())
            self._refresh()

    def _move(self, offset: int) -> None:
        row = self.files.currentRow()
        if 0 <= row + offset < self.files.count():
            self.files.insertItem(row + offset, self.files.takeItem(row))
            self.files.setCurrentRow(row + offset)

    def _mode_changed(self, *_args) -> None:
        mode = self.mode
        for row in reversed(range(self.files.count())):
            path = Path(self.files.item(row).data(Qt.ItemDataRole.UserRole))
            if path.suffix.casefold() not in self._extensions():
                self.files.takeItem(row)
        self.form.setRowVisible(self.ranges, mode in RANGE_OPERATIONS)
        self.form.setRowVisible(self.dpi, mode in {MediaOperation.OCR, MediaOperation.RENDER})
        self.form.setRowVisible(self.language, mode == MediaOperation.OCR)
        self.form.setRowVisible(self.format, mode == MediaOperation.RENDER)
        self.form.setRowVisible(self.reduce, mode == MediaOperation.OPTIMIZE)
        self.form.setRowVisible(self.split_size, mode == MediaOperation.SPLIT)
        self.form.setRowVisible(self.confirm_signed, mode in MUTATING_OPERATIONS)
        self.note.setText(OPERATION_NOTES[mode])
        self._refresh()

    def _refresh(self, *_args) -> None:
        paths = self.paths()
        row = self.files.currentRow()
        count = len(paths)
        self.remove.setEnabled(row >= 0)
        self.up.setEnabled(row > 0)
        self.down.setEnabled(0 <= row < count - 1)
        self.add.setEnabled(count < MAX_BATCH_INPUTS)
        self.preview.setVisible(
            0 <= row < count and paths[row] == self.suggested and self._has_preview
        )
        message = f"{count} arquivo(s) do disco · novas pastas · originais preservados"
        ready = count >= (2 if self.mode == MediaOperation.MERGE else 1) and bool(
            self.destination.text()
        )
        try:
            if self.mode in RANGE_OPERATIONS and self.ranges.text().strip():
                parse_intervals(self.ranges.text(), 100_000)
        except DocForgeError as error:
            message = str(error)
            ready = False
        if self.mode == MediaOperation.OCR and not self.language.count():
            message = "Valide os modelos em OCR > Configurar OCR local."
            ready = False
        self.status.setText(message)
        self.run_button.setEnabled(ready)

    def accept(self) -> None:
        if not self.run_button.isEnabled():
            return
        try:
            self.request = MediaRequest(
                self.mode,
                self.paths(),
                Path(self.destination.text()),
                MediaOptions(
                    ranges=self.ranges.text().strip() if self.mode in RANGE_OPERATIONS else "",
                    dpi=self.dpi.currentData(),
                    image_format=self.format.currentData(),
                    language=self.language.currentData() or "por",
                    tessdata=self.tessdata,
                    reduce_images=self.reduce.isChecked(),
                    split_size=self.split_size.value(),
                    confirmed=self.confirm_signed.isChecked(),
                ),
            )
        except DocForgeError as error:
            self.status.setText(str(error))
            return
        super().accept()


class BatchReport(QDialog):
    open_pdf = Signal(object)

    def __init__(self, runner, parent) -> None:
        super().__init__(parent)
        self.setObjectName("media_batch_report")
        self.setWindowTitle("Relatório do processamento local")
        self.resize(860, 420)
        self.runner = runner
        root = QVBoxLayout(self)
        self.summary = QLabel()
        root.addWidget(self.summary)
        self.results = QTreeWidget()
        self.results.setRootIsDecorated(False)
        self.results.setAlternatingRowColors(True)
        self.results.setHeaderLabels(["Entrada", "Estado", "Detalhes", "Saída"])
        self.results.header().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.results.setColumnWidth(0, 160)
        self.results.setColumnWidth(3, 230)
        root.addWidget(self.results, 1)
        self.entry_note = QLabel()
        self.entry_note.setTextFormat(Qt.TextFormat.PlainText)
        self.entry_note.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.entry_note.setWordWrap(True)
        self.entry_note.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.entry_note.setMinimumHeight(44)
        root.addWidget(self.entry_note)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        copy = buttons.addButton("Copiar relatório", QDialogButtonBox.ButtonRole.ActionRole)
        copy.clicked.connect(self._copy)
        self.retry = buttons.addButton(
            "Repetir falhas e canceladas", QDialogButtonBox.ButtonRole.ActionRole
        )
        self.retry.clicked.connect(self._retry)
        self.open_button = buttons.addButton("Abrir PDF", QDialogButtonBox.ButtonRole.ActionRole)
        self.open_button.clicked.connect(self._open)
        root.addWidget(buttons)
        self.results.currentItemChanged.connect(self._selection)
        runner.changed.connect(self.refresh)
        self.refresh()

    def refresh(self) -> None:
        current = (
            self.results.indexOfTopLevelItem(self.results.currentItem())
            if self.results.currentItem()
            else 0
        )
        self.results.clear()
        records = self.runner.records()
        for record in records:
            inputs = ", ".join(path.name for path in record.spec.inputs)
            item = QTreeWidgetItem(
                self.results,
                [
                    inputs,
                    STATE_LABELS[record.state],
                    record.error or record.detail,
                    str(record.result or "—"),
                ],
            )
            item.setToolTip(0, "\n".join(str(path) for path in record.spec.inputs))
            item.setToolTip(2, record.error or record.detail)
            item.setToolTip(3, str(record.result or ""))
            if record.result and record.result.suffix == ".pdf":
                item.setData(3, Qt.ItemDataRole.UserRole, str(record.result))
        self.results.setCurrentItem(self.results.topLevelItem(max(0, current)))
        done = sum(record.state.terminal for record in records)
        success = sum(record.state == TaskState.SUCCEEDED for record in records)
        self.summary.setText(
            f"{done}/{len(records)} tarefa(s) finalizada(s) · {success} concluída(s) com sucesso"
        )
        self.retry.setEnabled(self.runner.can_retry())
        self._selection()

    def _selection(self, *_args) -> None:
        item = self.results.currentItem()
        self.open_button.setEnabled(bool(item and item.data(3, Qt.ItemDataRole.UserRole)))
        self.entry_note.setText("\n".join((item.text(2), item.text(3))) if item else "")

    def _copy(self) -> None:
        lines = [self.summary.text(), "Entrada\tEstado\tDetalhes\tSaída"]
        for index in range(self.results.topLevelItemCount()):
            item = self.results.topLevelItem(index)
            lines.append("\t".join(item.text(column) for column in range(4)))
        QApplication.clipboard().setText("\n".join(lines))

    def _open(self) -> None:
        if (item := self.results.currentItem()) and (
            path := item.data(3, Qt.ItemDataRole.UserRole)
        ):
            self.accept()
            self.open_pdf.emit(Path(path))

    def _retry(self) -> None:
        self.accept()
        self.runner.retry()
