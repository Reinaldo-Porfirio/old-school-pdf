"""Orquestra operações de segurança da aba ativa."""

from dataclasses import asdict
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QDialog, QMessageBox

from docforge.domain.errors import DocForgeError
from docforge.domain.security import MAX_REDACTION_AREAS, MAX_REDACTION_PAGES, RedactionArea
from docforge.domain.viewer import PdfRect
from docforge.ui.security_dialogs import (
    VISUAL_WARNING,
    MetadataDialog,
    ProtectionDialog,
    RedactionReviewDialog,
    SignatureReportDialog,
    SignDialog,
    TrustDialog,
    VisualSignatureDialog,
)

if TYPE_CHECKING:
    from docforge.ui.main_window import MainWindow
    from docforge.ui.pdf_tab import PdfTab


class SecurityTools(QObject):
    def __init__(self, window: "MainWindow") -> None:
        super().__init__(window)
        self.window = window
        self.documents = window.document_tools
        self.signing = window.capabilities.signing_available()

    def update_controls(self, tab: "PdfTab | None") -> None:
        viewer = tab.viewer if tab else None
        info = viewer.info if viewer else None
        ready = bool(info and viewer.state == "ready" and not viewer.busy)
        rasterizable = ready and not info.protected and info.page_count <= MAX_REDACTION_PAGES
        signable = ready and self.signing and not info.protected
        actions = self.window.actions
        for key, enabled in (
            ("metadata", ready),
            ("password", ready),
            ("redact", rasterizable and len(tab.redactions) < MAX_REDACTION_AREAS),
            ("unmark_redaction", ready and bool(tab.redactions)),
            ("export_redaction", rasterizable and bool(tab.redactions)),
            ("visual_sign", ready and info.can_annotate),
            ("digital_sign", signable and not info.signed and not info.repaired),
            ("verify_signatures", signable),
        ):
            actions[key].setEnabled(enabled)
        for key in ("digital_sign", "verify_signatures"):
            if not self.signing:
                actions[key].setToolTip("Instale o extra opcional signing para usar este comando.")
            elif info and info.protected:
                actions[key].setToolTip("Disponível para PDFs sem criptografia.")
            elif key == "digital_sign" and info and (info.repaired or info.signed):
                actions[key].setToolTip(
                    "A assinatura exige um PDF íntegro e sem assinatura anterior."
                )
            else:
                actions[key].setToolTip(actions[key].text())
        actions["redact"].setToolTip(
            f"Marque uma área em um PDF sem criptografia de até {MAX_REDACTION_PAGES} páginas."
        )
        actions["visual_sign"].setToolTip(VISUAL_WARNING)

    def metadata(self, tab: "PdfTab") -> None:
        info = tab.viewer.info
        dialog = MetadataDialog(info.protected and not info.owner_authenticated, self.window)
        try:
            if dialog.exec() == QDialog.DialogCode.Accepted:
                self.documents.export_security(
                    tab, "Remover metadados", "metadados-removidos", "metadata", dialog.values()
                )
        finally:
            dialog.deleteLater()

    def protect(self, tab: "PdfTab") -> None:
        info = tab.viewer.info
        dialog = ProtectionDialog(info.protected and not info.owner_authenticated, self.window)
        try:
            if dialog.exec() == QDialog.DialogCode.Accepted:
                self.documents.export_security(
                    tab, "Proteger cópia AES-256", "protegido", "protect", dialog.values()
                )
        finally:
            dialog.deleteLater()

    def mark(self, tab: "PdfTab") -> None:
        tab.prepare_placement("redact")

    def unmark(self, tab: "PdfTab") -> None:
        if tab.redactions:
            tab.redactions.pop()
            tab.refresh_redactions()

    def redact(self, tab: "PdfTab") -> None:
        dialog = RedactionReviewDialog(tab.redactions, self.window)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.documents.export_security(
                tab,
                "Exportar redação rasterizada",
                "redigido",
                "redact",
                {"marks": [asdict(mark) for mark in tab.redactions]},
            )
        dialog.deleteLater()

    def visual(self, tab: "PdfTab") -> None:
        self.documents.place(tab, "visual_signature")

    def placed(self, tab: "PdfTab", kind: str, region: PdfRect) -> None:
        viewer = tab.viewer
        if viewer.state != "ready" or viewer.busy:
            return
        tab.canvas.clear_selection()
        if kind == "redact":
            if len(tab.redactions) < MAX_REDACTION_AREAS:
                tab.redactions.append(RedactionArea(viewer.page, region))
                tab.refresh_redactions()
            return
        dialog = VisualSignatureDialog(self.window)
        try:
            if dialog.exec() == QDialog.DialogCode.Accepted:
                viewer.change(
                    "add_annotation",
                    {"kind": "visual_signature", "region": region, **dialog.values()},
                )
        except DocForgeError as error:
            QMessageBox.warning(self.window, "Assinatura visual", str(error))
        finally:
            dialog.deleteLater()

    def sign(self, tab: "PdfTab") -> None:
        dialog = SignDialog(self.window)
        try:
            if dialog.exec() == QDialog.DialogCode.Accepted:
                self.documents.export_security(
                    tab, "Assinar cópia digitalmente", "assinado", "sign", dialog.values()
                )
        finally:
            dialog.deleteLater()

    def verify(self, tab: "PdfTab") -> None:
        dialog = TrustDialog(self.window)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            tab.viewer.verify_signatures(dialog.paths)
        dialog.deleteLater()

    def report(self, tab: "PdfTab", signatures: list[dict]) -> None:
        dialog = SignatureReportDialog(tab.viewer.session.source_path.name, signatures, self.window)
        dialog.open()
        dialog.finished.connect(dialog.deleteLater)
