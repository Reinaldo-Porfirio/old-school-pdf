"""Diálogos locais para metadados, proteção, redação e assinaturas."""

from base64 import b64encode
from pathlib import Path

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QPointF, Qt, Signal
from PySide6.QtGui import QColor, QImage, QPainter, QPen
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from oldschoolpdf.domain.errors import OldSchoolPDFError
from oldschoolpdf.domain.security import (
    METADATA_FIELDS,
    PERMISSION_LABELS,
    REDACTION_DPI,
    SIGNATURE_PAD_SIZE,
    RedactionArea,
    validate_passwords,
)

VISUAL_WARNING = (
    "A assinatura visual é uma imagem ou um desenho. Ela não tem verificação criptográfica."
)


def _note(layout, text: str) -> QLabel:
    label = QLabel(text)
    label.setTextFormat(Qt.TextFormat.PlainText)
    label.setWordWrap(True)
    layout.addWidget(label)
    return label


def _buttons(dialog: QDialog, layout, title: str) -> QPushButton:
    box = QDialogButtonBox(
        QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
    )
    button = box.button(QDialogButtonBox.StandardButton.Ok)
    button.setText(title)
    box.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")
    box.accepted.connect(dialog.accept)
    box.rejected.connect(dialog.reject)
    layout.addWidget(box)
    return button


def _password(name: str) -> QLineEdit:
    entry = QLineEdit()
    entry.setObjectName(name)
    entry.setEchoMode(QLineEdit.EchoMode.Password)
    entry.setMaxLength(1024)
    return entry


class MetadataDialog(QDialog):
    def __init__(self, current_owner: bool, parent: QWidget) -> None:
        super().__init__(parent)
        self.setWindowTitle("Remover metadados")
        self.setMinimumWidth(465)
        layout = QVBoxLayout(self)
        _note(
            layout,
            "Selecione os metadados a remover da cópia. Marcar todos os campos remove a "
            "ficha Info completa. Comentários, anexos e conteúdo das páginas permanecem.",
        )
        group = QGroupBox("Informações do documento")
        grid = QGridLayout(group)
        self.fields = {}
        for index, (key, label) in enumerate(METADATA_FIELDS.items()):
            check = QCheckBox(label)
            check.setObjectName("metadata_" + key)
            check.setChecked(True)
            grid.addWidget(check, index // 2, index % 2)
            self.fields[key] = check
        layout.addWidget(group)
        self.xml = QCheckBox("Remover o pacote XMP completo")
        self.xml.setObjectName("metadata_xmp")
        self.xml.setChecked(True)
        layout.addWidget(self.xml)
        self.owner = _password("metadata_owner") if current_owner else None
        if self.owner:
            form = QFormLayout()
            form.addRow("Senha de proprietário atual", self.owner)
            layout.addLayout(form)
        self.proceed = _buttons(self, layout, "Escolher destino…")
        for checkbox in (*self.fields.values(), self.xml):
            checkbox.toggled.connect(self._update)
        if self.owner:
            self.owner.textChanged.connect(self._update)
        self._update()

    def _update(self) -> None:
        selected = self.xml.isChecked() or any(field.isChecked() for field in self.fields.values())
        self.proceed.setEnabled(selected and (self.owner is None or bool(self.owner.text())))

    def values(self) -> dict:
        return {
            "fields": [key for key, field in self.fields.items() if field.isChecked()],
            "xml": self.xml.isChecked(),
            "current_owner": self.owner.text() if self.owner else "",
        }


class ProtectionDialog(QDialog):
    def __init__(self, current_owner: bool, parent: QWidget) -> None:
        super().__init__(parent)
        self.setWindowTitle("Proteger cópia com senha")
        self.setMinimumWidth(490)
        layout = QVBoxLayout(self)
        _note(
            layout,
            "A cópia será criptografada com AES-256. A senha de abertura permite ler o PDF. "
            "A senha de proprietário libera as permissões.",
        )
        form = QFormLayout()
        self.current_owner = _password("protect_current_owner") if current_owner else None
        if self.current_owner:
            form.addRow("Senha de proprietário atual", self.current_owner)
        self.user = _password("protect_user")
        self.user_check = _password("protect_user_repeat")
        self.owner = _password("protect_owner")
        self.owner_check = _password("protect_owner_repeat")
        for label, field in (
            ("Nova senha de abertura", self.user),
            ("Repita a senha de abertura", self.user_check),
            ("Nova senha de proprietário", self.owner),
            ("Repita a senha de proprietário", self.owner_check),
        ):
            form.addRow(label, field)
        layout.addLayout(form)
        group = QGroupBox("Permitir com a senha de abertura")
        grid = QGridLayout(group)
        self.allowed = {}
        for index, (key, label) in enumerate(PERMISSION_LABELS.items()):
            check = QCheckBox(label)
            check.setObjectName("permission_" + key)
            grid.addWidget(check, index // 2, index % 2)
            self.allowed[key] = check
        layout.addWidget(group)
        _note(layout, "As restrições de uso dependem do leitor de PDF.")
        self.error = _note(layout, "")
        self.error.setObjectName("protection_error")
        _buttons(self, layout, "Escolher destino…")

    def accept(self) -> None:
        try:
            if self.current_owner is not None and not self.current_owner.text():
                raise OldSchoolPDFError("Informe a senha de proprietário atual.")
            validate_passwords(self.user.text(), self.owner.text())
            if (
                self.user.text() != self.user_check.text()
                or self.owner.text() != self.owner_check.text()
            ):
                raise OldSchoolPDFError("Confira a repetição das duas senhas.")
        except OldSchoolPDFError as error:
            self.error.setText(str(error))
            return
        super().accept()

    def values(self) -> dict:
        return {
            "user": self.user.text(),
            "owner": self.owner.text(),
            "allowed": [key for key, check in self.allowed.items() if check.isChecked()],
            "current_owner": self.current_owner.text() if self.current_owner else "",
        }


class RedactionReviewDialog(QDialog):
    def __init__(self, marks: list[RedactionArea], parent: QWidget) -> None:
        super().__init__(parent)
        self.setWindowTitle("Revisar redação irreversível")
        self.setMinimumWidth(510)
        layout = QVBoxLayout(self)
        pages = sorted({mark.page + 1 for mark in marks})
        summary = QLabel(f"{len(marks)} área(s) em {len(pages)} página(s)")
        summary.setProperty("role", "badge")
        layout.addWidget(summary)
        page_list = QPlainTextEdit(", ".join(map(str, pages)))
        page_list.setReadOnly(True)
        page_list.setAccessibleName("Páginas com áreas marcadas")
        page_list.setMaximumHeight(70)
        layout.addWidget(page_list)
        _note(
            layout,
            f"A cópia transforma todas as páginas em imagens de {REDACTION_DPI} DPI. "
            "Os pixels das áreas marcadas são substituídos por preto. Texto selecionável, "
            "OCR, links, campos, anexos, metadados e assinaturas digitais serão removidos. "
            "Marque todas as ocorrências visíveis que precisam desaparecer.",
        )
        self.acknowledge = QCheckBox("Revisei as áreas e quero gerar a cópia rasterizada.")
        self.acknowledge.setObjectName("redaction_acknowledge")
        layout.addWidget(self.acknowledge)
        self.proceed = _buttons(self, layout, "Escolher destino…")
        self.proceed.setEnabled(False)
        self.acknowledge.toggled.connect(self.proceed.setEnabled)


class SignaturePad(QWidget):
    ink_changed = Signal(bool)

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("signature_pad")
        self.setAccessibleName("Área para desenhar a assinatura")
        self.setFixedSize(*SIGNATURE_PAD_SIZE)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.image = QImage(*SIGNATURE_PAD_SIZE, QImage.Format.Format_ARGB32_Premultiplied)
        self.last: QPointF | None = None
        self.clear()

    def clear(self) -> None:
        self.image.fill(Qt.GlobalColor.transparent)
        self.last = None
        self.has_ink = False
        self.update()
        self.ink_changed.emit(False)

    def paintEvent(self, event) -> None:
        with QPainter(self) as painter:
            painter.fillRect(self.rect(), QColor("#fafafa"))
            painter.drawImage(0, 0, self.image)
            painter.setPen(QColor("#68717e"))
            painter.drawRect(self.rect().adjusted(0, 0, -1, -1))

    def _stroke(self, position: QPointF) -> None:
        with QPainter(self.image) as painter:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setPen(
                QPen(QColor("#142c54"), 3.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
            )
            if self.last == position:
                painter.drawPoint(position)
            else:
                painter.drawLine(self.last, position)
        self.last = position
        if not self.has_ink:
            self.has_ink = True
            self.ink_changed.emit(True)
        self.update()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.last = event.position()
            self._stroke(event.position())

    def mouseMoveEvent(self, event) -> None:
        if self.last is not None:
            self._stroke(event.position())

    def mouseReleaseEvent(self, event) -> None:
        if self.last is not None and event.button() == Qt.MouseButton.LeftButton:
            self._stroke(event.position())
            self.last = None


class VisualSignatureDialog(QDialog):
    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setWindowTitle("Inserir assinatura visual")
        layout = QVBoxLayout(self)
        _note(layout, VISUAL_WARNING).setObjectName("visual_signature_warning")
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)
        drawing = QWidget()
        draw_layout = QVBoxLayout(drawing)
        self.pad = SignaturePad()
        draw_layout.addWidget(self.pad, alignment=Qt.AlignmentFlag.AlignHCenter)
        clear = QPushButton("Limpar desenho")
        clear.clicked.connect(self.pad.clear)
        draw_layout.addWidget(clear, alignment=Qt.AlignmentFlag.AlignRight)
        self.tabs.addTab(drawing, "Desenhar")
        image = QWidget()
        image_layout = QVBoxLayout(image)
        self.path = ""
        self.file_label = _note(image_layout, "Selecione uma imagem PNG ou JPEG.")
        choose = QPushButton("Escolher imagem…")
        choose.clicked.connect(self._choose)
        image_layout.addWidget(choose, alignment=Qt.AlignmentFlag.AlignLeft)
        image_layout.addStretch()
        self.tabs.addTab(image, "Usar imagem")
        self.proceed = _buttons(self, layout, "Inserir na página")
        self.pad.ink_changed.connect(self._update)
        self.tabs.currentChanged.connect(self._update)
        self._update()

    def _choose(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self, "Escolher imagem de assinatura", "", "Imagens (*.png *.jpg *.jpeg)"
        )
        if filename:
            self.path = filename
            self.file_label.setText(Path(filename).name)
            self._update()

    def _update(self) -> None:
        self.proceed.setEnabled(
            self.pad.has_ink if self.tabs.currentIndex() == 0 else bool(self.path)
        )

    def values(self) -> dict:
        if self.tabs.currentIndex() == 1:
            return {"path": self.path}
        data = QByteArray()
        buffer = QBuffer(data)
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        saved = self.pad.image.save(buffer, "PNG")
        buffer.close()
        if not saved:
            raise OldSchoolPDFError("Não foi possível preparar o desenho da assinatura.")
        return {"drawing": b64encode(bytes(data)).decode("ascii")}


class SignDialog(QDialog):
    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setWindowTitle("Assinar digitalmente uma cópia")
        self.setMinimumWidth(490)
        layout = QVBoxLayout(self)
        _note(
            layout,
            "Use seu certificado local PKCS#12. A cópia recebe uma assinatura criptográfica "
            "invisível, sem serviço de carimbo do tempo.",
        )
        self.path = ""
        self.file_label = _note(layout, "Nenhum arquivo de certificado selecionado")
        choose = QPushButton("Escolher certificado…")
        choose.clicked.connect(self._choose)
        layout.addWidget(choose, alignment=Qt.AlignmentFlag.AlignLeft)
        form = QFormLayout()
        self.passphrase = _password("signing_passphrase")
        form.addRow("Senha do certificado", self.passphrase)
        layout.addLayout(form)
        self.proceed = _buttons(self, layout, "Escolher destino…")
        self.proceed.setEnabled(False)

    def _choose(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self, "Certificado PKCS#12", "", "Certificados PKCS#12 (*.pfx *.p12)"
        )
        if filename:
            self.path = filename
            self.file_label.setText(Path(filename).name)
            self.proceed.setEnabled(True)

    def values(self) -> dict:
        return {"pfx": self.path, "passphrase": self.passphrase.text()}


class TrustDialog(QDialog):
    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setWindowTitle("Verificar assinaturas digitais")
        self.setMinimumWidth(460)
        self.paths: list[str] = []
        layout = QVBoxLayout(self)
        _note(
            layout,
            "A verificação examina a integridade do PDF. Para avaliar a cadeia de confiança, "
            "selecione raízes de confiança que você já conhece. A verificação é offline.",
        )
        self.selection = _note(layout, "Nenhuma raiz selecionada")
        row = QHBoxLayout()
        choose = QPushButton("Selecionar raízes locais…")
        choose.clicked.connect(self._choose)
        row.addWidget(choose)
        self.clear = QPushButton("Limpar seleção")
        self.clear.clicked.connect(self._clear)
        self.clear.setEnabled(False)
        row.addWidget(self.clear)
        layout.addLayout(row)
        self.proceed = _buttons(self, layout, "Verificar")

    def _choose(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(
            self, "Raízes de confiança", "", "Certificados X.509 (*.pem *.crt *.cer *.der)"
        )
        if files:
            self.paths = files
            self.selection.setText(
                "\n".join(Path(name).name for name in files)
                if len(files) <= 8
                else "Selecione até oito arquivos de certificados."
            )
            self.clear.setEnabled(True)
            self.proceed.setEnabled(len(files) <= 8)

    def _clear(self) -> None:
        self.paths = []
        self.selection.setText("Nenhuma raiz selecionada")
        self.clear.setEnabled(False)
        self.proceed.setEnabled(True)


class SignatureReportDialog(QDialog):
    def __init__(self, filename: str, signatures: list[dict], parent: QWidget) -> None:
        super().__init__(parent)
        self.setWindowTitle("Relatório de assinaturas digitais")
        self.resize(630, 450)
        layout = QVBoxLayout(self)
        _note(layout, filename)
        lines = []
        coverage = {
            "ENTIRE_FILE": "Arquivo completo",
            "ENTIRE_REVISION": "Revisão assinada, com alterações posteriores",
            "CONTIGUOUS_BLOCK_FROM_START": "Trecho inicial do arquivo",
            "UNCLEAR": "Indeterminada",
        }
        for entry in signatures:
            lines.append("Campo  " + entry["field"])
            if "error" in entry:
                lines.extend((entry["error"], ""))
                continue
            lines.extend(
                (
                    "Signatário  " + entry["signer"],
                    "Impressão digital SHA-256  " + entry["fingerprint"],
                    "Integridade  " + ("Preservada" if entry["intact"] else "Falhou"),
                    "Criptografia da assinatura  " + ("Válida" if entry["valid"] else "Inválida"),
                    "Cobertura  " + coverage.get(entry["coverage"], "Indeterminada"),
                    "Cadeia de confiança local  "
                    + ("Verificada" if entry["trusted"] else "Não estabelecida"),
                    "",
                )
            )
        report = QPlainTextEdit(
            "\n".join(lines) if lines else "Nenhuma assinatura digital encontrada."
        )
        report.setReadOnly(True)
        report.setObjectName("signature_report")
        layout.addWidget(report, 1)
        _note(
            layout,
            "Verificação offline. Revogação e carimbo do tempo dependem das evidências "
            "locais disponíveis. Integridade, cobertura e confiança são verificações distintas.",
        )
        box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        box.button(QDialogButtonBox.StandardButton.Close).setText("Fechar")
        box.rejected.connect(self.reject)
        layout.addWidget(box)
