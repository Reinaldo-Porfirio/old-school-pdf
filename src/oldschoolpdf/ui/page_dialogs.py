"""Diálogos para inserir páginas em branco, cortar margens e mudar o tamanho do papel."""

from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from oldschoolpdf.domain.editing import (
    MAX_BLANK_PAGES,
    MAX_CROP_MM,
    PAPER_SIZES,
    parse_intervals,
)
from oldschoolpdf.domain.errors import OldSchoolPDFError


def _note(text: str) -> QLabel:
    label = QLabel(text)
    label.setWordWrap(True)
    label.setProperty("role", "muted")
    return label


class _PagesDialog(QDialog):
    """Base com o campo de páginas, a prévia da seleção e os botões."""

    def __init__(self, title: str, action: str, page: int, count: int, default: str, parent):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(470)
        self.count = count
        self.ranges: list[tuple[int, int]] = []
        self.layout_root = QVBoxLayout(self)
        self.form = QFormLayout()
        row = QHBoxLayout()
        self.pages = QLineEdit(default)
        self.pages.setObjectName("pages_ranges")
        self.pages.setMaxLength(1800)
        self.pages.setAccessibleName("Páginas ou intervalos")
        self.pages.setToolTip("Use páginas e intervalos como 2–4,6–8.")
        row.addWidget(self.pages, 1)
        current = QPushButton("Atual")
        current.setToolTip("Somente a página atual")
        current.clicked.connect(lambda: self.pages.setText(str(page + 1)))
        everything = QPushButton("Todas")
        everything.setToolTip("Todas as páginas do documento")
        everything.clicked.connect(lambda: self.pages.setText(f"1-{count}"))
        row.addWidget(current)
        row.addWidget(everything)
        self.form.addRow("Páginas:", row)
        self.layout_root.addLayout(self.form)
        self.preview = QLabel()
        self.preview.setWordWrap(True)
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.apply = self.buttons.button(QDialogButtonBox.StandardButton.Ok)
        self.apply.setText(action)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        self.pages.textChanged.connect(self._refresh)

    def finish_layout(self) -> None:
        self.layout_root.addWidget(self.preview)
        self.layout_root.addWidget(self.buttons)
        self._refresh()

    def _refresh(self) -> None:
        try:
            self.ranges = parse_intervals(self.pages.text(), self.count)
            selected = sum(end - start + 1 for start, end in self.ranges)
            text = f"{selected} página(s) selecionada(s) de {self.count}."
        except OldSchoolPDFError as error:
            self.ranges = []
            text = str(error)
        self.preview.setText(text)
        self.apply.setEnabled(bool(self.ranges))


def _paper_combo(include_same: bool) -> QComboBox:
    combo = QComboBox()
    if include_same:
        combo.addItem("Igual à página atual", "same")
    for key, (label, _width, _height) in PAPER_SIZES.items():
        combo.addItem(label, key)
    return combo


class BlankPageDialog(QDialog):
    def __init__(self, page: int, parent) -> None:
        super().__init__(parent)
        self.setObjectName("blank_page_dialog")
        self.setWindowTitle("Inserir páginas em branco")
        self.setMinimumWidth(420)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.where = QComboBox()
        self.where.addItem(f"Depois da página {page + 1}", "after")
        self.where.addItem(f"Antes da página {page + 1}", "before")
        form.addRow("Posição:", self.where)
        self.count = QSpinBox()
        self.count.setRange(1, MAX_BLANK_PAGES)
        form.addRow("Quantidade:", self.count)
        self.size = _paper_combo(include_same=True)
        form.addRow("Tamanho:", self.size)
        self.orientation = QComboBox()
        self.orientation.addItem("Retrato", "portrait")
        self.orientation.addItem("Paisagem", "landscape")
        form.addRow("Orientação:", self.orientation)
        layout.addLayout(form)
        layout.addWidget(
            _note(
                "As páginas entram na cópia de trabalho e podem ser desfeitas com Ctrl+Z. "
                "Para escrever nelas, use Inserir caixa de texto."
            )
        )
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Inserir")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.size.currentIndexChanged.connect(self._refresh)
        self._refresh()

    def _refresh(self) -> None:
        self.orientation.setEnabled(self.size.currentData() != "same")

    def values(self) -> dict:
        return {
            "where": self.where.currentData(),
            "count": self.count.value(),
            "size": self.size.currentData(),
            "orientation": self.orientation.currentData(),
        }


class CropDialog(_PagesDialog):
    def __init__(self, page: int, count: int, parent) -> None:
        super().__init__("Cortar margens das páginas", "Cortar", page, count, str(page + 1), parent)
        self.setObjectName("crop_dialog")
        group = QGroupBox("Como cortar")
        grid = QVBoxLayout(group)
        self.modes = QButtonGroup(self)
        self.auto = QRadioButton("Remover as margens em branco (automático)")
        self.manual = QRadioButton("Cortar medidas fixas de cada lado")
        self.reset = QRadioButton("Restaurar o tamanho original (desfazer cortes anteriores)")
        for button in (self.auto, self.manual, self.reset):
            self.modes.addButton(button)
            grid.addWidget(button)
        self.auto.setChecked(True)
        padding_row = QHBoxLayout()
        padding_row.addWidget(QLabel("Folga ao redor do conteúdo:"))
        self.padding = self._spin(5)
        padding_row.addWidget(self.padding)
        padding_row.addStretch()
        grid.addLayout(padding_row)
        sides = QWidget()
        sides_grid = QGridLayout(sides)
        sides_grid.setContentsMargins(18, 0, 0, 0)
        self.left, self.top, self.right, self.bottom = (self._spin(10) for _ in range(4))
        for column, (label, spin) in enumerate(
            (("Esquerda", self.left), ("Superior", self.top)), start=0
        ):
            sides_grid.addWidget(QLabel(label), 0, column * 2)
            sides_grid.addWidget(spin, 0, column * 2 + 1)
        for column, (label, spin) in enumerate(
            (("Direita", self.right), ("Inferior", self.bottom))
        ):
            sides_grid.addWidget(QLabel(label), 1, column * 2)
            sides_grid.addWidget(spin, 1, column * 2 + 1)
        grid.addWidget(sides)
        self.sides = sides
        self.layout_root.addWidget(group)
        self.layout_root.addWidget(
            _note(
                "O corte esconde a área de fora, mas ela continua dentro do arquivo. "
                "Para apagar informação de verdade, use a redação, na aba Segurança."
            )
        )
        self.modes.buttonToggled.connect(lambda *_: self._mode_changed())
        self.finish_layout()
        self._mode_changed()

    @staticmethod
    def _spin(value: float) -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setRange(0, MAX_CROP_MM)
        spin.setDecimals(1)
        spin.setSuffix(" mm")
        spin.setValue(value)
        return spin

    def _mode_changed(self) -> None:
        self.padding.setEnabled(self.auto.isChecked())
        self.sides.setEnabled(self.manual.isChecked())

    def values(self) -> dict:
        if self.reset.isChecked():
            return {"ranges": self.ranges, "mode": "reset"}
        if self.auto.isChecked():
            return {"ranges": self.ranges, "mode": "auto", "margins": [self.padding.value()] * 4}
        margins = [spin.value() for spin in (self.left, self.top, self.right, self.bottom)]
        return {"ranges": self.ranges, "mode": "margins", "margins": margins}


class ResizeDialog(_PagesDialog):
    def __init__(self, page: int, count: int, parent) -> None:
        super().__init__(
            "Mudar o tamanho do papel", "Redimensionar", page, count, f"1-{count}", parent
        )
        self.setObjectName("resize_dialog")
        self.size = _paper_combo(include_same=False)
        self.form.addRow("Novo tamanho:", self.size)
        self.orientation = QComboBox()
        self.orientation.addItem("Automática (segue cada página)", "auto")
        self.orientation.addItem("Retrato", "portrait")
        self.orientation.addItem("Paisagem", "landscape")
        self.form.addRow("Orientação:", self.orientation)
        self.layout_root.addWidget(
            _note(
                "O conteúdo é reduzido ou ampliado na mesma proporção e centralizado no papel "
                "novo. Texto, links, anotações e campos acompanham e continuam editáveis."
            )
        )
        self.finish_layout()

    def values(self) -> dict:
        return {
            "ranges": self.ranges,
            "size": self.size.currentData(),
            "orientation": self.orientation.currentData(),
        }
