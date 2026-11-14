"""Abre o editor do texto original para a página atual da aba ativa."""

from typing import TYPE_CHECKING

from PySide6.QtCore import QObject

from oldschoolpdf.ui.text_edit_dialog import TextEditDialog, describe_report

if TYPE_CHECKING:
    from oldschoolpdf.ui.main_window import MainWindow
    from oldschoolpdf.ui.pdf_tab import PdfTab


class TextTools(QObject):
    def __init__(self, window: "MainWindow") -> None:
        super().__init__(window)
        self.window = window
        self.dialog: TextEditDialog | None = None

    def update_controls(self, tab: "PdfTab | None") -> None:
        viewer = tab.viewer if tab else None
        info = viewer.info if viewer else None
        action = self.window.actions["edit_text"]
        ready = bool(info and viewer.state == "ready" and not viewer.busy)
        action.setEnabled(bool(ready and info.can_modify and self.dialog is None))
        if info and not info.can_modify:
            action.setToolTip("As permissões deste PDF não permitem alterar o conteúdo.")
        else:
            action.setToolTip("Editar o texto original da página atual")

    def run_dialog(self, dialog: TextEditDialog) -> int:
        return dialog.exec()

    def edit(self, tab: "PdfTab") -> None:
        viewer = tab.viewer
        if self.dialog is not None or not viewer.info or not viewer.info.can_modify:
            return
        documents = self.window.document_tools
        self.dialog = TextEditDialog(
            viewer, viewer.page, lambda: documents._authorize(tab), self.window
        )
        self.dialog.finished.connect(self._closed)
        self.window._update_pdf_controls()
        self.run_dialog(self.dialog)

    def _closed(self) -> None:
        dialog, self.dialog = self.dialog, None
        if dialog is not None:
            if dialog.report is not None:
                self.window.statusBar().showMessage(
                    "Texto alterado. " + describe_report(dialog.report), 15000
                )
            dialog.deleteLater()
        self.window._update_pdf_controls()
