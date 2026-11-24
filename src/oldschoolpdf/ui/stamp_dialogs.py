"""Diálogos de numeração, cabeçalho e rodapé, marca d'água e localizar e substituir."""

import math
from contextlib import suppress
from os.path import abspath
from pathlib import Path

from PySide6.QtCore import QDate, QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QImageReader, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
)

from oldschoolpdf.domain.stamps import (
    MAX_MARGIN_MM,
    MAX_STAMP_SIZE,
    MAX_STAMP_TEXT,
    MAX_START,
    MAX_WATERMARK_SIZE,
    MIN_IMAGE_SCALE,
    MIN_MARGIN_MM,
    MIN_OPACITY,
    MIN_STAMP_SIZE,
    MIN_WATERMARK_SIZE,
    NUMBER_FORMATS,
    SLOT_LABELS,
    SLOTS,
    STAMP_COLORS,
    STAMP_FONTS,
    TOKENS,
    WATERMARK_ANGLES,
    WATERMARK_LAYERS,
    WATERMARK_PRESETS,
    expand_tokens,
)
from oldschoolpdf.domain.viewer import MAX_QUERY_LENGTH
from oldschoolpdf.ui.page_dialogs import PagesDialog, note_label

MM = 72 / 25.4
# Fontes do Windows parecidas com as embutidas no PDF, só para a prévia.
PREVIEW_FAMILIES = {"sans": "Arial", "serif": "Times New Roman", "mono": "Courier New"}
COLUMN_NAMES = ("Esquerda", "Centro", "Direita")


def _combo(options: dict, current: str) -> QComboBox:
    combo = QComboBox()
    for key, value in options.items():
        combo.addItem(value[0] if isinstance(value, tuple) else value, key)
    combo.setCurrentIndex(max(0, combo.findData(current)))
    return combo


def _qcolor(key: str) -> QColor:
    red, green, blue = STAMP_COLORS[key][1]
    return QColor.fromRgbF(red, green, blue)


class StampPreview(QFrame):
    """Miniatura da página com o cabeçalho, o rodapé ou a marca d'água aproximados."""

    def __init__(self, page_size: tuple[float, float], *, strips: bool = False) -> None:
        super().__init__()
        self.setObjectName("stamp_preview")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setFrameShadow(QFrame.Shadow.Sunken)
        # Em faixas, mostra só o topo e o pé da página, largos o bastante para ler o texto.
        self.strips = strips
        if strips:
            self.setMinimumSize(420, 190)
        else:
            self.setMinimumSize(190, 250)
        self.setAccessibleName("Prévia da página")
        self.page_size = page_size
        self.texts: dict[str, str] = {}
        self.font_key = "sans"
        self.text_size = 10.0
        self.color = "black"
        self.margin = 12.0
        self.watermark: dict | None = None
        self.image = QPixmap()

    def _font(self, key: str, size: float, *, bold: bool = False) -> QFont:
        font = QFont(PREVIEW_FAMILIES[key])
        # Depois de `scale`, uma unidade vale um ponto da página.
        font.setPointSizeF(max(0.5, size * 72 / max(self.logicalDpiY(), 1)))
        font.setBold(bold)
        return font

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        if self.strips:
            self._paint_strips(painter)
        else:
            width, height = self.page_size
            area = QRectF(self.contentsRect()).adjusted(12, 12, -12, -12)
            scale = min(area.width() / width, area.height() / height)
            left = area.left() + (area.width() - width * scale) / 2
            top = area.top() + (area.height() - height * scale) / 2
            painter.fillRect(
                QRectF(left + 3, top + 3, width * scale, height * scale), QColor("#7d8794")
            )
            painter.translate(left, top)
            painter.scale(scale, scale)
            self._paint_page(painter)
        painter.end()

    def _paint_strips(self, painter: QPainter) -> None:
        """Topo e pé da página na largura toda, com um corte no meio."""
        width, height = self.page_size
        area = QRectF(self.contentsRect()).adjusted(10, 8, -10, -8)
        band = min(height / 2, self.margin * MM + self.text_size * 1.8 + 10)
        gap = 16.0
        scale = min(area.width() / width, (area.height() - gap) / (2 * band))
        left = area.left() + (area.width() - width * scale) / 2
        top = area.top() + (area.height() - 2 * band * scale - gap) / 2
        for origin, shown in (
            (top, QRectF(0, 0, width, band)),
            (
                top + band * scale + gap - (height - band) * scale,
                QRectF(0, height - band, width, band),
            ),
        ):
            painter.save()
            painter.translate(left, origin)
            painter.scale(scale, scale)
            painter.setClipRect(shown)
            self._paint_page(painter)
            painter.restore()
        middle = top + band * scale + gap / 2
        pen = QPen(QColor("#7d8794"), 1, Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.drawLine(QPointF(left, middle), QPointF(left + width * scale, middle))

    def _paint_page(self, painter: QPainter) -> None:
        width, height = self.page_size
        painter.fillRect(QRectF(0, 0, width, height), QColor("white"))
        painter.setPen(QPen(QColor("#5a6b80"), 0))
        painter.drawRect(QRectF(0, 0, width, height))
        # Linhas cinzas imitam o texto do documento.
        body = QColor("#c9d0d8")
        start, end = height * 0.14, height * 0.86
        if self.strips:
            # Nas faixas, o corpo começa logo depois do cabeçalho e vai até o rodapé.
            reserved = self.margin * MM + self.text_size * 1.8 + 4
            start, end = min(start, reserved), max(end, height - reserved)
        step = max(height * 0.028, 12.0) if self.strips else height * 0.028
        y = start
        while y < end:
            line = width * (0.62 if int(y / step) % 4 == 3 else 0.76)
            painter.fillRect(QRectF(width * 0.12, y, line, max(2.0, step * 0.22)), body)
            y += step
        if self.watermark is not None:
            self._paint_watermark(painter, width, height)
        self._paint_texts(painter, width, height)

    def _paint_texts(self, painter: QPainter, width: float, height: float) -> None:
        if not self.texts:
            return
        font = self._font(self.font_key, self.text_size)
        painter.setFont(font)
        painter.setPen(_qcolor(self.color))
        metrics = QFontMetricsF(font)
        margin = self.margin * MM
        for slot, text in self.texts.items():
            if not text:
                continue
            length = metrics.horizontalAdvance(text)
            align = slot.split("_")[1]
            x = (
                margin
                if align == "left"
                else (width - length) / 2
                if align == "center"
                else width - margin - length
            )
            if slot.startswith("header"):
                baseline = margin + metrics.ascent()
            else:
                baseline = height - margin - metrics.descent()
            painter.drawText(QPointF(x, baseline), text)

    def _paint_watermark(self, painter: QPainter, width: float, height: float) -> None:
        mark = self.watermark
        painter.save()
        painter.setOpacity(mark["opacity"] / 100)
        painter.translate(width / 2, height / 2)
        if mark["mode"] == "image":
            if not self.image.isNull():
                target = width * mark["scale"] / 100
                ratio = self.image.height() / max(self.image.width(), 1)
                target = min(target, height * 0.95 / max(ratio, 1e-6))
                box = QRectF(-target / 2, -target * ratio / 2, target, target * ratio)
                painter.drawPixmap(box, self.image, QRectF(self.image.rect()))
            painter.restore()
            return
        text = mark["text"]
        if mark["angle"] == "diagonal":
            angle, room = math.degrees(math.atan2(height, width)), math.hypot(width, height) * 0.72
        elif mark["angle"] == "horizontal":
            angle, room = 0.0, width * 0.8
        else:
            angle, room = 90.0, height * 0.8
        unit = QFontMetricsF(self._font(mark["font"], 100, bold=True)).horizontalAdvance(text)
        size = mark["size"] or min(MAX_WATERMARK_SIZE, room / max(unit / 100, 0.01))
        font = self._font(mark["font"], size, bold=True)
        metrics = QFontMetricsF(font)
        painter.rotate(-angle)
        painter.setFont(font)
        painter.setPen(_qcolor(mark["color"]))
        length = metrics.horizontalAdvance(text)
        painter.drawText(QPointF(-length / 2, (metrics.ascent() - metrics.descent()) / 2), text)
        painter.restore()


class HeaderFooterDialog(PagesDialog):
    """Numeração e textos de cabeçalho e rodapé, numa grade como a dos editores de texto."""

    def __init__(
        self,
        page: int,
        count: int,
        page_size: tuple[float, float],
        filename: str,
        parent,
    ) -> None:
        super().__init__(
            "Numeração, cabeçalho e rodapé", "Aplicar", page, count, f"1-{count}", parent
        )
        self.setObjectName("header_footer_dialog")
        self.setMinimumWidth(880)
        self.filename = filename
        self.date = QDate.currentDate().toString("dd/MM/yyyy")
        self._saved: dict[str, str] = {}
        self._focused: QLineEdit | None = None
        columns = QHBoxLayout()
        options = QVBoxLayout()
        right = QVBoxLayout()

        numbering = QGroupBox("Numeração das páginas")
        numbering_form = QFormLayout(numbering)
        self.number = QCheckBox("Numerar as páginas")
        self.number.setChecked(True)
        numbering_form.addRow(self.number)
        self.number_format = _combo(NUMBER_FORMATS, "page_of")
        numbering_form.addRow("Formato:", self.number_format)
        self.number_slot = QComboBox()
        for slot in SLOTS:
            self.number_slot.addItem(SLOT_LABELS[slot], slot)
        self.number_slot.setCurrentIndex(self.number_slot.findData("footer_center"))
        numbering_form.addRow("Posição:", self.number_slot)
        self.start = QSpinBox()
        self.start.setRange(1, MAX_START)
        self.start.setToolTip(
            "Para não numerar a capa, escolha as páginas 2 em diante e comece em 1."
        )
        numbering_form.addRow("Começar em:", self.start)
        options.addWidget(numbering)

        texts = QGroupBox("Textos (deixe em branco o que não quiser)")
        grid = QGridLayout(texts)
        for column, name in enumerate(COLUMN_NAMES, start=1):
            label = QLabel(name)
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            grid.addWidget(label, 0, column)
        self.slots: dict[str, QLineEdit] = {}
        for row, (prefix, title) in enumerate((("header", "Cabeçalho"), ("footer", "Rodapé")), 1):
            grid.addWidget(QLabel(title + ":"), row, 0)
            for column, align in enumerate(("left", "center", "right"), start=1):
                slot = f"{prefix}_{align}"
                edit = QLineEdit()
                edit.setObjectName(f"slot_{slot}")
                edit.setMaxLength(MAX_STAMP_TEXT)
                edit.setAccessibleName(SLOT_LABELS[slot])
                edit.setPlaceholderText("—")
                edit.textEdited.connect(self._refresh)
                edit.installEventFilter(self)
                self.slots[slot] = edit
                grid.addWidget(edit, row, column)
        tokens = QHBoxLayout()
        tokens.addWidget(QLabel("Inserir:"))
        for token, label in TOKENS.items():
            button = QPushButton(label)
            button.setToolTip(f"Insere [{token}] no campo escolhido")
            button.clicked.connect(lambda _=False, value=token: self._insert(value))
            tokens.addWidget(button)
        tokens.addStretch()
        grid.addLayout(tokens, 3, 0, 1, 4)
        right.addWidget(texts)

        look = QGroupBox("Aparência")
        look_form = QFormLayout(look)
        self.font_choice = _combo(STAMP_FONTS, "sans")
        look_form.addRow("Fonte:", self.font_choice)
        self.size_choice = QSpinBox()
        self.size_choice.setRange(MIN_STAMP_SIZE, MAX_STAMP_SIZE)
        self.size_choice.setValue(10)
        self.size_choice.setSuffix(" pt")
        look_form.addRow("Tamanho:", self.size_choice)
        self.color = _combo(STAMP_COLORS, "black")
        look_form.addRow("Cor:", self.color)
        self.margin = QSpinBox()
        self.margin.setRange(MIN_MARGIN_MM, MAX_MARGIN_MM)
        self.margin.setValue(12)
        self.margin.setSuffix(" mm da borda")
        look_form.addRow("Distância:", self.margin)
        options.addWidget(look)
        self.replace = QCheckBox(
            "Substituir o cabeçalho e o rodapé que o Old School PDF aplicou antes"
        )
        self.replace.setChecked(True)
        right.addWidget(self.replace)
        right.addStretch()
        columns.addLayout(options, 2)
        columns.addLayout(right, 3)
        self.layout_root.addLayout(columns)
        preview_box = QGroupBox("Prévia do topo e do pé da primeira página")
        preview_layout = QVBoxLayout(preview_box)
        self.preview_page = StampPreview(page_size, strips=True)
        preview_layout.addWidget(self.preview_page)
        self.layout_root.addWidget(preview_box)
        self.layout_root.addWidget(
            note_label(
                "O texto entra no conteúdo das páginas, como num documento impresso, e "
                "continua pesquisável. Ctrl+Z desfaz. Para tirar depois, use Remover "
                "cabeçalho, rodapé e marca d'água."
            )
        )
        for signal in (
            self.number.toggled,
            self.number_format.currentIndexChanged,
            self.number_slot.currentIndexChanged,
            self.start.valueChanged,
            self.font_choice.currentIndexChanged,
            self.size_choice.valueChanged,
            self.color.currentIndexChanged,
            self.margin.valueChanged,
        ):
            signal.connect(self._refresh)
        self.finish_layout()

    def eventFilter(self, watched, event) -> bool:
        if isinstance(watched, QLineEdit) and event.type() == event.Type.FocusIn:
            self._focused = watched
        return super().eventFilter(watched, event)

    def _insert(self, token: str) -> None:
        edit = self._focused or self.slots["header_right"]
        if edit.isReadOnly():
            return
        edit.insert(f"[{token}]")
        edit.setFocus()
        self._refresh()

    def _refresh(self, *_args) -> None:
        number_slot = self.number_slot.currentData() if self.number.isChecked() else None
        for slot, edit in self.slots.items():
            if slot == number_slot:
                if not edit.isReadOnly():
                    self._saved[slot] = edit.text()
                    edit.setReadOnly(True)
                    edit.setToolTip("Preenchido pela numeração")
                edit.setText(NUMBER_FORMATS[self.number_format.currentData()][1])
            elif edit.isReadOnly():
                edit.setReadOnly(False)
                edit.setToolTip("")
                edit.setText(self._saved.pop(slot, ""))
        for widget in (self.number_format, self.number_slot, self.start):
            widget.setEnabled(self.number.isChecked())
        super()._refresh()
        templates = self.templates()
        self.apply.setEnabled(bool(self.ranges and templates))
        total = self.start.value() + max(1, sum(end - start + 1 for start, end in self.ranges)) - 1
        preview = self.preview_page
        preview.texts = {
            slot: expand_tokens(text, self.start.value(), total, self.date, self.filename)
            for slot, text in templates.items()
        }
        preview.font_key = self.font_choice.currentData()
        preview.size = self.size_choice.value()
        preview.color = self.color.currentData()
        preview.margin = self.margin.value()
        preview.update()

    def templates(self) -> dict[str, str]:
        return {
            slot: edit.text().strip() for slot, edit in self.slots.items() if edit.text().strip()
        }

    def values(self) -> dict:
        return {
            "ranges": self.ranges,
            "slots": self.templates(),
            "font": self.font_choice.currentData(),
            "size": self.size_choice.value(),
            "color": self.color.currentData(),
            "margin": self.margin.value(),
            "start": self.start.value(),
            "date": self.date,
            "file": self.filename,
            "replace": self.replace.isChecked(),
        }


class WatermarkDialog(PagesDialog):
    """Marca d'água de texto ou de imagem, transparente, atrás ou na frente do conteúdo."""

    def __init__(self, page: int, count: int, page_size: tuple[float, float], parent) -> None:
        super().__init__("Inserir marca d'água", "Aplicar", page, count, f"1-{count}", parent)
        self.setObjectName("watermark_dialog")
        self.setMinimumWidth(720)
        columns = QHBoxLayout()
        options = QVBoxLayout()
        kind = QGroupBox("Tipo")
        kind_row = QHBoxLayout(kind)
        self.kinds = QButtonGroup(self)
        self.text_mode = QRadioButton("Texto")
        self.image_mode = QRadioButton("Imagem (logotipo, carimbo)")
        self.text_mode.setChecked(True)
        for button in (self.text_mode, self.image_mode):
            self.kinds.addButton(button)
            kind_row.addWidget(button)
        kind_row.addStretch()
        options.addWidget(kind)

        self.text_group = QGroupBox("Texto")
        text_form = QFormLayout(self.text_group)
        self.text = QComboBox()
        self.text.setEditable(True)
        self.text.addItems(WATERMARK_PRESETS)
        self.text.lineEdit().setMaxLength(MAX_STAMP_TEXT)
        self.text.setAccessibleName("Texto da marca d'água")
        text_form.addRow("Texto:", self.text)
        self.font_choice = _combo(STAMP_FONTS, "sans")
        text_form.addRow("Fonte:", self.font_choice)
        self.color = _combo(STAMP_COLORS, "gray")
        text_form.addRow("Cor:", self.color)
        size_row = QHBoxLayout()
        self.auto_size = QCheckBox("Automático")
        self.auto_size.setChecked(True)
        self.size_choice = QSpinBox()
        self.size_choice.setRange(MIN_WATERMARK_SIZE, MAX_WATERMARK_SIZE)
        self.size_choice.setValue(72)
        self.size_choice.setSuffix(" pt")
        size_row.addWidget(self.auto_size)
        size_row.addWidget(self.size_choice)
        size_row.addStretch()
        text_form.addRow("Tamanho:", size_row)
        self.angle = _combo(WATERMARK_ANGLES, "diagonal")
        text_form.addRow("Direção:", self.angle)
        options.addWidget(self.text_group)

        self.image_group = QGroupBox("Imagem")
        image_form = QFormLayout(self.image_group)
        path_row = QHBoxLayout()
        self.path = QLineEdit()
        self.path.setReadOnly(True)
        self.path.setPlaceholderText("Nenhuma imagem escolhida")
        browse = QPushButton("Procurar…")
        browse.clicked.connect(self._browse)
        path_row.addWidget(self.path, 1)
        path_row.addWidget(browse)
        image_form.addRow("Arquivo:", path_row)
        self.scale = QSpinBox()
        self.scale.setRange(MIN_IMAGE_SCALE, 100)
        self.scale.setValue(50)
        self.scale.setSuffix(" % da largura")
        image_form.addRow("Tamanho:", self.scale)
        options.addWidget(self.image_group)

        look = QGroupBox("Transparência e posição")
        look_form = QFormLayout(look)
        self.opacity = QSpinBox()
        self.opacity.setRange(MIN_OPACITY, 100)
        self.opacity.setValue(30)
        self.opacity.setSuffix(" %")
        self.opacity.setToolTip("Quanto menor, mais clara e discreta fica a marca.")
        look_form.addRow("Opacidade:", self.opacity)
        self.layer = _combo(WATERMARK_LAYERS, "behind")
        look_form.addRow("Camada:", self.layer)
        options.addWidget(look)
        self.replace = QCheckBox("Substituir a marca d'água que o Old School PDF aplicou antes")
        self.replace.setChecked(True)
        options.addWidget(self.replace)
        columns.addLayout(options, 1)
        side = QVBoxLayout()
        side.addWidget(QLabel("Prévia:"))
        self.preview_page = StampPreview(page_size)
        side.addWidget(self.preview_page, 1)
        columns.addLayout(side)
        self.layout_root.addLayout(columns)
        self.layout_root.addWidget(
            note_label(
                "A marca de texto vira desenho: não aparece na busca, na cópia de texto nem "
                "na conversão para Word. Ctrl+Z desfaz."
            )
        )
        self.text.currentTextChanged.connect(self._refresh)
        for signal in (
            self.kinds.buttonToggled,
            self.font_choice.currentIndexChanged,
            self.color.currentIndexChanged,
            self.auto_size.toggled,
            self.size_choice.valueChanged,
            self.angle.currentIndexChanged,
            self.scale.valueChanged,
            self.opacity.valueChanged,
        ):
            signal.connect(self._refresh)
        self.finish_layout()

    def _browse(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self, "Imagem da marca d'água", "", "Imagens (*.png *.jpg *.jpeg)"
        )
        if filename:
            self.set_image(abspath(filename))

    def set_image(self, path: str) -> None:
        self.path.setText(path)
        reader = QImageReader(path)
        reader.setAutoTransform(True)
        image = reader.read()
        self.preview_page.image = QPixmap.fromImage(image) if not image.isNull() else QPixmap()
        self._refresh()

    def _refresh(self, *_args) -> None:
        image = self.image_mode.isChecked()
        self.text_group.setVisible(not image)
        self.image_group.setVisible(image)
        self.size_choice.setEnabled(not self.auto_size.isChecked())
        super()._refresh()
        ready = bool(self.path.text()) if image else bool(self.text.currentText().strip())
        self.apply.setEnabled(bool(self.ranges) and ready)
        self.preview_page.watermark = self.values()
        self.preview_page.update()

    def values(self) -> dict:
        common = {
            "ranges": self.ranges,
            "opacity": self.opacity.value(),
            "layer": self.layer.currentData(),
            "replace": self.replace.isChecked(),
        }
        if self.image_mode.isChecked():
            return {
                **common,
                "mode": "image",
                "path": self.path.text(),
                "scale": self.scale.value(),
            }
        return {
            **common,
            "mode": "text",
            "text": " ".join(self.text.currentText().split()),
            "font": self.font_choice.currentData(),
            "color": self.color.currentData(),
            "size": 0 if self.auto_size.isChecked() else self.size_choice.value(),
            "angle": self.angle.currentData(),
        }


class RemoveStampsDialog(PagesDialog):
    def __init__(self, page: int, count: int, parent) -> None:
        super().__init__(
            "Remover cabeçalho, rodapé e marca d'água", "Remover", page, count, f"1-{count}", parent
        )
        self.setObjectName("remove_stamps_dialog")
        group = QGroupBox("O que remover")
        column = QVBoxLayout(group)
        self.header = QCheckBox("Numeração, cabeçalho e rodapé")
        self.watermark = QCheckBox("Marca d'água")
        for box in (self.header, self.watermark):
            box.setChecked(True)
            box.toggled.connect(self._refresh)
            column.addWidget(box)
        self.layout_root.addWidget(group)
        self.layout_root.addWidget(
            note_label(
                "Só sai o que o Old School PDF aplicou. Marcas de outros programas fazem parte "
                "do conteúdo da página: para escondê-las, use a redação, na aba Segurança."
            )
        )
        self.finish_layout()

    def _refresh(self, *_args) -> None:
        super()._refresh()
        if hasattr(self, "header"):
            self.apply.setEnabled(bool(self.ranges and self.kinds()))

    def kinds(self) -> list[str]:
        return [
            kind
            for kind, box in (("header", self.header), ("watermark", self.watermark))
            if box.isChecked()
        ]

    def values(self) -> dict:
        return {"ranges": self.ranges, "kinds": self.kinds()}


class FindReplaceDialog(QDialog):
    """Procura no texto original, mostra cada ocorrência e substitui as marcadas."""

    def __init__(self, viewer, parent) -> None:
        super().__init__(parent)
        self.setObjectName("find_replace_dialog")
        self.setWindowTitle("Localizar e substituir")
        self.setMinimumSize(720, 520)
        self.viewer = viewer
        self.found_for: dict | None = None
        root = QVBoxLayout(self)
        form = QFormLayout()
        self.query = QLineEdit()
        self.query.setObjectName("replace_query")
        self.query.setMaxLength(MAX_QUERY_LENGTH)
        self.query.setAccessibleName("Texto a localizar")
        form.addRow("&Localizar:", self.query)
        self.replacement = QLineEdit()
        self.replacement.setObjectName("replace_with")
        self.replacement.setMaxLength(400)
        self.replacement.setAccessibleName("Substituir por")
        self.replacement.setPlaceholderText("Deixe em branco para apagar o texto encontrado")
        form.addRow("&Substituir por:", self.replacement)
        root.addLayout(form)
        row = QHBoxLayout()
        self.case = QCheckBox("Diferenciar maiúsculas e minúsculas")
        self.word = QCheckBox("Somente palavras inteiras")
        self.scope = QComboBox()
        self.scope.addItem("Em todas as páginas", "all")
        self.scope.addItem(f"Só na página {viewer.page + 1}", "page")
        self.find_button = QPushButton("Locali&zar")
        self.find_button.setDefault(True)
        self.find_button.clicked.connect(self.find)
        for widget in (self.case, self.word, self.scope):
            row.addWidget(widget)
        row.addStretch()
        row.addWidget(self.find_button)
        root.addLayout(row)
        self.results = QTreeWidget()
        self.results.setObjectName("replace_results")
        self.results.setRootIsDecorated(False)
        self.results.setHeaderLabels(["Página", "Trecho", "Situação"])
        self.results.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        header = self.results.header()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.results.itemChanged.connect(self._refresh)
        root.addWidget(self.results, 1)
        marks = QHBoxLayout()
        self.check_all = QPushButton("Marcar todas")
        self.check_all.clicked.connect(lambda: self._check(True))
        self.uncheck_all = QPushButton("Desmarcar todas")
        self.uncheck_all.clicked.connect(lambda: self._check(False))
        self.summary = QLabel("Escreva o texto e clique em Localizar.")
        self.summary.setWordWrap(True)
        marks.addWidget(self.check_all)
        marks.addWidget(self.uncheck_all)
        marks.addWidget(self.summary, 1)
        root.addLayout(marks)
        root.addWidget(
            note_label(
                "A troca acontece no próprio PDF e mantém a fonte. Se o texto novo for maior, "
                "o bloco usa o espaço livre ao lado e reduz a fonte até 85%. O que não couber "
                "fica como estava e aparece no relatório. Ctrl+Z desfaz tudo de uma vez."
            )
        )
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.apply = self.buttons.button(QDialogButtonBox.StandardButton.Ok)
        self.apply.setText("Substituir marcadas")
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        root.addWidget(self.buttons)
        for signal in (
            self.query.textChanged,
            self.case.toggled,
            self.word.toggled,
            self.scope.currentIndexChanged,
        ):
            signal.connect(self._refresh)
        self.query.returnPressed.connect(self.find)
        viewer.matches_found.connect(self._found)
        viewer.matches_failed.connect(self._failed)
        viewer.changed.connect(self._refresh)
        self._refresh()

    def search_values(self) -> dict:
        count = self.viewer.info.page_count
        page = self.viewer.page
        ranges = [(0, count - 1)] if self.scope.currentData() == "all" else [(page, page)]
        return {
            "query": self.query.text(),
            "case": self.case.isChecked(),
            "word": self.word.isChecked(),
            "ranges": ranges,
        }

    def find(self) -> None:
        if not self.query.text().split() or self.viewer.busy:
            return
        values = self.search_values()
        if self.viewer.find_text(values):
            self.found_for = None
            self.pending = values
            self.results.clear()
            self.summary.setText("Procurando…")
            self._refresh()

    def _found(self, result: dict) -> None:
        self.found_for = getattr(self, "pending", None)
        self.results.blockSignals(True)
        self.results.clear()
        pages = set()
        for entry in result["items"]:
            pages.add(entry["page"])
            snippet = f"…{entry['before']} [{entry['match']}] {entry['after']}…"
            status = "Pode substituir" if entry["editable"] else entry["reason"]
            item = QTreeWidgetItem([str(entry["page"] + 1), snippet, status])
            item.setData(0, Qt.ItemDataRole.UserRole, entry)
            item.setToolTip(1, snippet)
            item.setToolTip(2, status)
            if entry["editable"]:
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(0, Qt.CheckState.Checked)
            else:
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEnabled)
            self.results.addTopLevelItem(item)
        self.results.blockSignals(False)
        count = len(result["items"])
        if count:
            text = f"{count} ocorrência(s) em {len(pages)} página(s)."
            if result.get("truncated"):
                text += " A lista chegou ao limite; substitua e localize de novo para ver o resto."
        else:
            text = "Nenhuma ocorrência no texto editável."
        self.summary.setText(text)
        self._refresh()

    def _failed(self, error: str) -> None:
        self.summary.setText(error)
        self._refresh()

    def _check(self, checked: bool) -> None:
        state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        self.results.blockSignals(True)
        for index in range(self.results.topLevelItemCount()):
            item = self.results.topLevelItem(index)
            if item.flags() & Qt.ItemFlag.ItemIsUserCheckable:
                item.setCheckState(0, state)
        self.results.blockSignals(False)
        self._refresh()

    def checked(self) -> list[dict]:
        entries = []
        for index in range(self.results.topLevelItemCount()):
            item = self.results.topLevelItem(index)
            if (
                item.flags() & Qt.ItemFlag.ItemIsUserCheckable
                and item.checkState(0) == Qt.CheckState.Checked
            ):
                entries.append(item.data(0, Qt.ItemDataRole.UserRole))
        return entries

    def _refresh(self, *_args) -> None:
        busy = bool(self.viewer.busy)
        fresh = self.found_for is not None and self.found_for == self.search_values()
        self.find_button.setEnabled(bool(self.query.text().split()) and not busy)
        self.apply.setEnabled(fresh and bool(self.checked()) and not busy)
        for button in (self.check_all, self.uncheck_all):
            button.setEnabled(self.results.topLevelItemCount() > 0)
        if self.found_for is not None and not fresh and self.results.topLevelItemCount():
            self.summary.setText("A busca mudou. Clique em Localizar de novo.")

    def values(self) -> dict:
        found = self.found_for or {}
        return {
            "query": found.get("query", ""),
            "case": found.get("case", False),
            "word": found.get("word", False),
            "replacement": self.replacement.text(),
            "items": [
                {key: entry[key] for key in ("page", "key", "start", "end")}
                for entry in self.checked()
            ],
        }

    def done(self, result: int) -> None:
        for signal, slot in (
            (self.viewer.matches_found, self._found),
            (self.viewer.matches_failed, self._failed),
            (self.viewer.changed, self._refresh),
        ):
            with suppress(RuntimeError, TypeError):
                signal.disconnect(slot)
        super().done(result)


def page_size(tab) -> tuple[float, float]:
    """Largura e altura da página atual como aparece, sem a rotação só de visualização."""
    if tab.page_properties:
        width, height, _ = tab.page_properties
        if tab.viewer.rotation in (90, 270):
            width, height = height, width
        return width, height
    return 595.0, 842.0


def source_name(tab) -> str:
    return Path(tab.viewer.session.source_path).name
