"""Editor do texto original do PDF: a página e a cópia editada, lado a lado."""

from collections.abc import Callable
from contextlib import suppress
from dataclasses import asdict

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import (
    QAction,
    QColor,
    QFont,
    QKeySequence,
    QPainter,
    QPen,
    QPixmap,
    QTextBlockFormat,
    QTextCharFormat,
    QTextCursor,
    QTextDocument,
    QTextFormat,
)
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTabWidget,
    QTextEdit,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from oldschoolpdf.application.pdf_viewer import PageFrame, PdfViewer
from oldschoolpdf.domain.errors import OldSchoolPDFError
from oldschoolpdf.domain.text_editing import (
    MAX_BLOCK_CHARS,
    MAX_EDIT_BLOCKS,
    TextBlock,
    TextRun,
    css_color,
    validate_text,
)
from oldschoolpdf.ui.continuous import frame_pixmap

STYLE_PROPERTY = QTextFormat.Property.UserProperty + 1
ALIGN_LABELS = {
    "left": "à esquerda",
    "center": "centralizado",
    "right": "à direita",
    "justify": "justificado",
}
SHRINK_CHOICES = (
    ("none", "Não reduzir a fonte"),
    ("light", "Reduzir até 85% (recomendado)"),
    ("strong", "Reduzir até 70%"),
)


def merge_runs(runs: list[TextRun]) -> list[TextRun]:
    merged: list[TextRun] = []
    for run in runs:
        if not run.text:
            continue
        if merged and (merged[-1].style, merged[-1].bold, merged[-1].italic) == (
            run.style,
            run.bold,
            run.italic,
        ):
            last = merged.pop()
            run = TextRun(last.text + run.text, run.style, run.bold, run.italic)
        merged.append(run)
    return merged


def load_runs(editor: QTextEdit, runs: tuple[TextRun, ...]) -> None:
    editor.clear()
    cursor = QTextCursor(editor.document())
    for run in runs:
        character = QTextCharFormat()
        character.setProperty(STYLE_PROPERTY, run.style)
        character.setFontWeight(QFont.Weight.Bold if run.bold else QFont.Weight.Normal)
        character.setFontItalic(run.italic)
        for index, part in enumerate(run.text.split("\n")):
            if index:
                cursor.insertBlock(QTextBlockFormat(), character)
            if part:
                cursor.insertText(part, character)
    editor.moveCursor(QTextCursor.MoveOperation.Start)
    editor.document().setModified(False)


def runs_from_document(document: QTextDocument, fallback: int) -> list[TextRun]:
    """Lê o texto do editor de volta em trechos com estilo de origem e ênfase."""
    runs: list[TextRun] = []
    block = document.begin()
    first = True
    while block.isValid():
        if not first:
            if runs:
                last = runs[-1]
                runs[-1] = TextRun(last.text + "\n", last.style, last.bold, last.italic)
            else:
                runs.append(TextRun("\n", fallback, False, False))
        first = False
        iterator = block.begin()
        while not iterator.atEnd():
            fragment = iterator.fragment()
            if fragment.isValid() and fragment.text():
                character = fragment.charFormat()
                style = character.property(STYLE_PROPERTY)
                runs.append(
                    TextRun(
                        fragment.text(),
                        int(style) if style is not None else fallback,
                        character.fontWeight() >= QFont.Weight.Bold,
                        character.fontItalic(),
                    )
                )
            iterator += 1
        block = block.next()
    return merge_runs(runs)


def describe_report(report: dict) -> str:
    """Resumo legível do que o motor fez numa edição ou prévia."""
    parts = [f"{report.get('blocks', 0)} bloco(s) de texto alterado(s)."]
    fonts = report.get("fonts", [])
    if fonts:
        labels = [
            entry["label"] + ("" if entry.get("exact") else " (aproximada)") for entry in fonts
        ]
        parts.append("Fontes: " + "; ".join(labels) + ".")
    scale = report.get("scale", 1)
    if scale < 0.999:
        parts.append(f"Texto reduzido para {scale:.0%} para caber no espaço.")
    if report.get("expanded"):
        parts.append(f"{report['expanded']} bloco(s) expandido(s) para baixo.")
    if report.get("links_restored"):
        parts.append(f"{report['links_restored']} link(s) preservado(s).")
    return " ".join(parts)


class PagePreview(QWidget):
    """Página com os blocos de texto marcados; um clique escolhe o bloco."""

    block_clicked = Signal(int)

    def __init__(self, *, clickable: bool) -> None:
        super().__init__()
        self.pixmap: QPixmap | None = None
        self.regions: list[tuple[float, float, float, float]] = []
        self.states: list[str] = []
        self.selected = -1
        self.clickable = clickable
        self.setMinimumSize(320, 420)

    def set_page(self, pixmap: QPixmap | None, regions=(), states=()) -> None:
        self.pixmap = pixmap
        self.regions = list(regions)
        self.states = list(states)
        self.update()

    def _target(self) -> QRectF:
        if self.pixmap is None or self.pixmap.isNull():
            return QRectF()
        area = QRectF(self.rect()).adjusted(10, 10, -10, -10)
        size = self.pixmap.deviceIndependentSize()
        scale = min(area.width() / size.width(), area.height() / size.height())
        width, height = size.width() * scale, size.height() * scale
        return QRectF(
            area.x() + (area.width() - width) / 2,
            area.y() + (area.height() - height) / 2,
            width,
            height,
        )

    def _box(self, target: QRectF, region) -> QRectF:
        x0, y0, x1, y1 = region
        return QRectF(
            target.x() + x0 * target.width(),
            target.y() + y0 * target.height(),
            (x1 - x0) * target.width(),
            (y1 - y0) * target.height(),
        )

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#808080"))
        target = self._target()
        if target.isNull():
            painter.setPen(QColor("#ffffff"))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Carregando a página…")
            return
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.drawPixmap(target, self.pixmap, QRectF(self.pixmap.rect()))
        painter.setPen(QPen(QColor("#000000"), 1))
        painter.drawRect(target.adjusted(-1, -1, 0, 0))
        colors = {
            "normal": QColor("#3a6ea5"),
            "edited": QColor("#e07000"),
            "locked": QColor("#9a9a9a"),
        }
        for index, region in enumerate(self.regions):
            box = self._box(target, region).adjusted(-2, -2, 2, 2)
            state = self.states[index] if index < len(self.states) else "normal"
            selected = index == self.selected
            pen = QPen(QColor("#0a246a") if selected else colors[state], 2.5 if selected else 1.2)
            if state == "locked":
                pen.setStyle(Qt.PenStyle.DashLine)
            painter.setPen(pen)
            fill = QColor(colors["edited"] if state == "edited" else "#0a246a")
            fill.setAlpha(45 if selected or state == "edited" else 0)
            painter.setBrush(fill)
            painter.drawRect(box)
            label = QRectF(box.x() - 1, box.y() - 13, 18, 12)
            painter.fillRect(label, QColor("#0a246a") if selected else pen.color())
            painter.setPen(QColor("#ffffff"))
            font = painter.font()
            font.setPointSize(7)
            font.setBold(True)
            painter.setFont(font)
            painter.drawText(label, Qt.AlignmentFlag.AlignCenter, str(index + 1))
            painter.setBrush(Qt.BrushStyle.NoBrush)

    def mousePressEvent(self, event) -> None:
        if not self.clickable:
            return
        target = self._target()
        point = QPointF(event.position())
        hits = [
            (box.width() * box.height(), index)
            for index, region in enumerate(self.regions)
            if (box := self._box(target, region).adjusted(-3, -3, 3, 3)).contains(point)
        ]
        if hits:
            self.block_clicked.emit(min(hits)[1])


class TextEditDialog(QDialog):
    def __init__(
        self,
        viewer: PdfViewer,
        page: int,
        authorize: Callable[[], bool],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.viewer = viewer
        self.page = page
        self.authorize = authorize
        self.blocks: tuple[TextBlock, ...] = ()
        self.edits: dict[str, list[TextRun]] = {}
        self.current = -1
        self.report: dict | None = None
        self._loading = False
        self.working = False
        self.setWindowTitle(f"Editar texto do PDF — página {page + 1}")
        self.resize(1180, 820)
        self.setSizeGripEnabled(True)
        root = QVBoxLayout(self)
        intro = QLabel(
            "Escolha um bloco na página ou na lista, edite o texto e confira a prévia. "
            "O PDF de origem não muda: a alteração vira uma revisão que pode ser desfeita."
        )
        intro.setWordWrap(True)
        root.addWidget(intro)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        root.addWidget(splitter, 1)

        self.pages = QTabWidget()
        self.original = PagePreview(clickable=True)
        self.original.block_clicked.connect(self._select_block)
        self.preview = PagePreview(clickable=False)
        self.pages.addTab(self.original, "Original")
        self.pages.addTab(self.preview, "Prévia da cópia editada")
        self.pages.setTabEnabled(1, False)
        splitter.addWidget(self.pages)

        side = QWidget()
        column = QVBoxLayout(side)
        column.setContentsMargins(6, 0, 0, 0)
        self.list_label = QLabel("Blocos de texto")
        column.addWidget(self.list_label)
        self.list = QListWidget()
        self.list.setObjectName("text_block_list")
        self.list.currentRowChanged.connect(self._select_block)
        column.addWidget(self.list, 1)

        editor_box = QGroupBox("Texto do bloco")
        editor_layout = QVBoxLayout(editor_box)
        tools = QToolBar()
        self.bold = QAction("Negrito", self)
        self.bold.setCheckable(True)
        self.bold.setShortcut(QKeySequence.StandardKey.Bold)
        bold_font = self.bold.font()
        bold_font.setBold(True)
        self.bold.setFont(bold_font)
        self.bold.toggled.connect(self._toggle_bold)
        self.italic = QAction("Itálico", self)
        self.italic.setCheckable(True)
        self.italic.setShortcut(QKeySequence.StandardKey.Italic)
        italic_font = self.italic.font()
        italic_font.setItalic(True)
        self.italic.setFont(italic_font)
        self.italic.toggled.connect(self._toggle_italic)
        self.restore = QAction("Restaurar bloco", self)
        self.restore.triggered.connect(self._restore_block)
        tools.addAction(self.bold)
        tools.addAction(self.italic)
        tools.addSeparator()
        tools.addAction(self.restore)
        editor_layout.addWidget(tools)
        self.editor = QTextEdit()
        self.editor.setObjectName("text_block_editor")
        self.editor.setAcceptRichText(False)
        self.editor.setTabChangesFocus(True)
        self.editor.textChanged.connect(self._text_changed)
        self.editor.currentCharFormatChanged.connect(self._format_changed)
        editor_layout.addWidget(self.editor, 1)
        self.details = QLabel()
        self.details.setWordWrap(True)
        self.details.setProperty("role", "muted")
        editor_layout.addWidget(self.details)
        column.addWidget(editor_box, 2)

        options = QGroupBox("Se o texto novo não couber no espaço")
        form = QFormLayout(options)
        self.shrink = QComboBox()
        for value, label in SHRINK_CHOICES:
            self.shrink.addItem(label, value)
        self.shrink.setCurrentIndex(1)
        form.addRow("Fonte:", self.shrink)
        self.expand = QCheckBox("Expandir o bloco para baixo, se houver espaço livre")
        form.addRow(self.expand)
        self.system_fonts = QCheckBox("Usar as fontes instaladas no Windows (mais fiéis)")
        self.system_fonts.setChecked(True)
        form.addRow(self.system_fonts)
        column.addWidget(options)

        self.status = QLabel()
        self.status.setWordWrap(True)
        column.addWidget(self.status)
        splitter.addWidget(side)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)

        buttons = QHBoxLayout()
        self.counter = QLabel()
        buttons.addWidget(self.counter, 1)
        self.preview_button = QPushButton("Gerar prévia")
        self.preview_button.clicked.connect(self._request_preview)
        self.apply_button = QPushButton("Aplicar ao PDF")
        self.apply_button.setDefault(True)
        self.apply_button.clicked.connect(self._apply)
        close = QPushButton("Fechar")
        close.clicked.connect(self.reject)
        for button in (self.preview_button, self.apply_button, close):
            buttons.addWidget(button)
        root.addLayout(buttons)

        viewer.text_blocks_ready.connect(self._loaded)
        viewer.text_preview_ready.connect(self._previewed)
        viewer.text_edited.connect(self._applied)
        viewer.text_edit_failed.connect(self._failed)
        self.finished.connect(self._disconnect)
        self._busy("Lendo o texto da página…")
        self._request(lambda size, dpr: viewer.read_text(page, size[0], size[1], dpr))

    # Comunicação com a aba
    def _frame_size(self) -> tuple[tuple[int, int], float]:
        dpr = min(max(self.devicePixelRatioF(), 1.0), 4.0)
        return (700, 900), dpr

    def _request(self, send: Callable) -> None:
        size, dpr = self._frame_size()
        if not send(size, dpr):
            self._busy("")
            self._show_error("A aba está ocupada. Aguarde a operação em andamento e tente de novo.")

    def _disconnect(self) -> None:
        for signal, slot in (
            (self.viewer.text_blocks_ready, self._loaded),
            (self.viewer.text_preview_ready, self._previewed),
            (self.viewer.text_edited, self._applied),
            (self.viewer.text_edit_failed, self._failed),
        ):
            with suppress(RuntimeError, TypeError):
                signal.disconnect(slot)

    def _busy(self, text: str) -> None:
        working = self.working = bool(text)
        for widget in (self.preview_button, self.apply_button, self.list, self.editor):
            widget.setEnabled(not working)
        if working:
            self.status.setStyleSheet("")
            self.status.setText(text)
        self._update_counter()

    def _show_error(self, text: str) -> None:
        self.status.setStyleSheet("color: #a00000;")
        self.status.setText(text)

    def _show_info(self, text: str) -> None:
        self.status.setStyleSheet("")
        self.status.setText(text)

    def _loaded(self, page: int, blocks: tuple[TextBlock, ...], frame: PageFrame) -> None:
        if page != self.page:
            return
        self.blocks = blocks
        self._busy("")
        self.original.set_page(frame_pixmap(frame), [block.region for block in blocks])
        self.list_label.setText(f"Blocos de texto ({len(blocks)})")
        self.list.clear()
        for index, block in enumerate(blocks):
            summary = " ".join(block.text.split())
            if len(summary) > 60:
                summary = summary[:57] + "…"
            item = QListWidgetItem(f"{index + 1}. {summary}")
            if not block.editable:
                item.setForeground(QColor("#808080"))
                item.setToolTip(block.reason)
            self.list.addItem(item)
        self._refresh_states()
        if not blocks:
            self.editor.setEnabled(False)
            self._show_info(
                "Esta página não tem texto editável. Se ela foi digitalizada, o texto é uma "
                "imagem: use o OCR para torná-la pesquisável (o texto do OCR é invisível e "
                "não pode ser editado como texto visível)."
            )
            return
        first = next((index for index, block in enumerate(blocks) if block.editable), 0)
        self.list.setCurrentRow(first)
        self._show_info(
            "Clique num bloco para editá-lo. Blocos tracejados não podem ser editados; "
            "passe o mouse sobre eles na lista para ver o motivo."
        )

    def _previewed(self, report: dict, frame: PageFrame) -> None:
        self._busy("")
        self.preview.set_page(frame_pixmap(frame))
        self.pages.setTabEnabled(1, True)
        self.pages.setCurrentIndex(1)
        self._show_info("Prévia gerada e verificada. " + describe_report(report))

    def _applied(self, report: dict) -> None:
        self.report = report
        self.edits.clear()
        self.accept()

    def _failed(self, error: str) -> None:
        self._busy("")
        self._show_error(error)

    # Edição
    def _select_block(self, index: int) -> None:
        if self._loading or not 0 <= index < len(self.blocks):
            return
        self._store_current()
        self.current = index
        if self.list.currentRow() != index:
            self.list.setCurrentRow(index)
        block = self.blocks[index]
        self._loading = True
        load_runs(self.editor, tuple(self.edits.get(block.key, block.runs)))
        self._loading = False
        self.editor.setReadOnly(not block.editable)
        for action in (self.bold, self.italic, self.restore):
            action.setEnabled(block.editable)
        fonts = "; ".join(
            f"{style.font} {style.size:g} pt, cor {css_color(style.color)}"
            for style in block.styles
        )
        label = "Fontes no PDF" if len(block.styles) > 1 else "Fonte no PDF"
        lines = [f"{label}: {fonts}. Alinhamento {ALIGN_LABELS.get(block.align, block.align)}."]
        if not block.editable:
            lines.append("Não editável: " + block.reason)
        self.details.setText(" ".join(lines))
        self.original.selected = index
        self._refresh_states()

    def _store_current(self) -> None:
        if not 0 <= self.current < len(self.blocks):
            return
        block = self.blocks[self.current]
        if not block.editable:
            return
        fallback = block.runs[0].style if block.runs else 0
        runs = runs_from_document(self.editor.document(), fallback)
        if runs == merge_runs(list(block.runs)):
            self.edits.pop(block.key, None)
        else:
            self.edits[block.key] = runs

    def _text_changed(self) -> None:
        if self._loading:
            return
        self._store_current()
        self._refresh_states()
        self.pages.setTabEnabled(1, False)
        if len(self.editor.toPlainText()) > MAX_BLOCK_CHARS:
            self._show_error(f"Cada bloco aceita até {MAX_BLOCK_CHARS} caracteres.")

    def _format_changed(self, character: QTextCharFormat) -> None:
        for action, value in (
            (self.bold, character.fontWeight() >= QFont.Weight.Bold),
            (self.italic, character.fontItalic()),
        ):
            action.blockSignals(True)
            action.setChecked(value)
            action.blockSignals(False)

    def _merge_format(self, character: QTextCharFormat) -> None:
        self.editor.mergeCurrentCharFormat(character)
        self.editor.setFocus()
        self._text_changed()

    def _toggle_bold(self, checked: bool) -> None:
        character = QTextCharFormat()
        character.setFontWeight(QFont.Weight.Bold if checked else QFont.Weight.Normal)
        self._merge_format(character)

    def _toggle_italic(self, checked: bool) -> None:
        character = QTextCharFormat()
        character.setFontItalic(checked)
        self._merge_format(character)

    def _restore_block(self) -> None:
        if 0 <= self.current < len(self.blocks):
            block = self.blocks[self.current]
            self.edits.pop(block.key, None)
            self._loading = True
            load_runs(self.editor, block.runs)
            self._loading = False
            self._refresh_states()

    def _refresh_states(self) -> None:
        states = [
            "locked" if not block.editable else "edited" if block.key in self.edits else "normal"
            for block in self.blocks
        ]
        self.original.states = states
        self.original.update()
        for index, block in enumerate(self.blocks):
            item = self.list.item(index)
            if item and block.editable:
                item.setForeground(QColor("#c05800") if block.key in self.edits else QColor())
        self._update_counter()

    def _update_counter(self) -> None:
        count = len(self.edits)
        self.counter.setText(
            f"{count} bloco(s) alterado(s)" if count else "Nenhuma alteração ainda"
        )
        idle = not self.viewer.busy and bool(self.blocks)
        self.preview_button.setEnabled(idle and count > 0)
        self.apply_button.setEnabled(idle and count > 0)

    # Prévia e aplicação
    def options(self) -> dict:
        return {
            "shrink": self.shrink.currentData(),
            "expand": self.expand.isChecked(),
            "system_fonts": self.system_fonts.isChecked(),
        }

    def _payload(self) -> list[dict] | None:
        self._store_current()
        if not self.edits:
            self._show_info("Nenhum bloco foi alterado.")
            return None
        if len(self.edits) > MAX_EDIT_BLOCKS:
            self._show_error(f"Aplique até {MAX_EDIT_BLOCKS} blocos alterados por vez.")
            return None
        payload = []
        for block in self.blocks:
            runs = self.edits.get(block.key)
            if runs is None:
                continue
            try:
                validate_text("".join(run.text for run in runs))
            except OldSchoolPDFError as error:
                self._show_error(f"Bloco {self.blocks.index(block) + 1}: {error}")
                return None
            payload.append({"key": block.key, "runs": [asdict(run) for run in runs]})
        return payload

    def _request_preview(self) -> None:
        payload = self._payload()
        if payload is None:
            return
        self._busy("Gerando a prévia e verificando o resultado…")
        options = self.options()
        self._request(
            lambda size, dpr: self.viewer.preview_text(
                self.page, payload, options, size[0], size[1], dpr
            )
        )

    def _apply(self) -> None:
        payload = self._payload()
        if payload is None or not self.authorize():
            return
        self._busy("Aplicando e verificando a edição…")
        if not self.viewer.replace_text(self.page, payload, self.options()):
            self._busy("")
            self._show_error("A aba está ocupada. Aguarde a operação em andamento.")

    def reject(self) -> None:
        self._store_current()
        if self.working and self.viewer.busy:
            self._show_info("Aguarde a operação terminar antes de fechar.")
            return
        if self.edits:
            choice = QMessageBox.question(
                self,
                "Descartar alterações?",
                "Há blocos alterados que ainda não foram aplicados ao PDF. Descartar?",
                QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Cancel,
            )
            if choice != QMessageBox.StandardButton.Discard:
                return
        super().reject()
