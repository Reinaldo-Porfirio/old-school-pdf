"""Comandos de páginas em branco, corte, tamanho do papel, marcadores e campos."""

from typing import TYPE_CHECKING

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QDialog, QInputDialog, QMessageBox

from oldschoolpdf.ui.field_dialog import FieldDialog
from oldschoolpdf.ui.outline_dialog import OutlineDialog
from oldschoolpdf.ui.page_dialogs import BlankPageDialog, CropDialog, ResizeDialog

if TYPE_CHECKING:
    from oldschoolpdf.ui.main_window import MainWindow
    from oldschoolpdf.ui.pdf_tab import PdfTab

FIELD_KIND_NAMES = {
    "text": "texto",
    "checkbox": "caixa de marcar",
    "choice": "lista",
    "radio": "opção",
}
ORGANIZE_ACTIONS = (
    "insert_blank",
    "crop_pages",
    "resize_pages",
    "outline",
    "add_field",
    "remove_field",
)


class OrganizeTools(QObject):
    def __init__(self, window: "MainWindow") -> None:
        super().__init__(window)
        self.window = window
        self.dialog: OutlineDialog | None = None

    # Hooks substituídos nos testes.
    def run_dialog(self, dialog: QDialog) -> int:
        return dialog.exec()

    def update_controls(self, tab: "PdfTab | None") -> None:
        actions = self.window.actions
        viewer = tab.viewer if tab else None
        info = viewer.info if viewer else None
        ready = bool(info and viewer.state == "ready" and not viewer.busy)
        organize = bool(ready and info.can_organize)
        modify = bool(ready and info.can_modify)
        forms = bool(modify and info.can_annotate and info.can_fill)
        actions["insert_blank"].setEnabled(organize)
        actions["crop_pages"].setEnabled(modify)
        actions["resize_pages"].setEnabled(modify)
        actions["outline"].setEnabled(
            bool(organize and viewer.outline_loaded and not viewer.outline_error)
            and self.dialog is None
        )
        actions["add_field"].setEnabled(bool(forms and tab.canvas.has_page))
        actions["remove_field"].setEnabled(
            bool(forms and any(field.kind in FIELD_KIND_NAMES for field in viewer.fields))
        )
        for key, allowed, reason in (
            ("crop_pages", modify, "As permissões deste PDF não permitem alterar as páginas."),
            ("add_field", forms, "As permissões deste PDF não permitem criar campos."),
        ):
            if info and not allowed and ready:
                actions[key].setToolTip(reason)
            else:
                actions[key].setToolTip(actions[key].text().replace("&", "").rstrip("…"))

    def _authorize(self, tab: "PdfTab") -> bool:
        return self.window.document_tools._authorize(tab)

    def insert_blank(self, tab: "PdfTab") -> None:
        viewer = tab.viewer
        if not viewer.info.can_organize:
            return
        dialog = BlankPageDialog(viewer.page, self.window)
        accepted = self.run_dialog(dialog) == QDialog.DialogCode.Accepted
        values = dialog.values()
        dialog.deleteLater()
        if accepted and self._authorize(tab):
            viewer.change("insert_blank", values)

    def crop(self, tab: "PdfTab") -> None:
        viewer = tab.viewer
        if not viewer.info.can_modify:
            return
        dialog = CropDialog(viewer.page, viewer.info.page_count, self.window)
        accepted = self.run_dialog(dialog) == QDialog.DialogCode.Accepted
        values = dialog.values()
        dialog.deleteLater()
        if accepted and values["ranges"] and self._authorize(tab):
            viewer.change("crop_pages", values)

    def resize(self, tab: "PdfTab") -> None:
        viewer = tab.viewer
        if not viewer.info.can_modify:
            return
        dialog = ResizeDialog(viewer.page, viewer.info.page_count, self.window)
        accepted = self.run_dialog(dialog) == QDialog.DialogCode.Accepted
        values = dialog.values()
        dialog.deleteLater()
        if accepted and values["ranges"] and self._authorize(tab):
            viewer.change("resize_pages", values)

    def outline(self, tab: "PdfTab") -> None:
        viewer = tab.viewer
        if self.dialog is not None or not viewer.outline_loaded or viewer.outline_error:
            return
        self.dialog = OutlineDialog(viewer, self.window)
        self.window._update_pdf_controls()
        accepted = self.run_dialog(self.dialog) == QDialog.DialogCode.Accepted
        payload = self.dialog.payload()
        self.dialog.deleteLater()
        self.dialog = None
        self.window._update_pdf_controls()
        if accepted and self._authorize(tab):
            viewer.change("set_outline", payload)

    def place_field(self, tab: "PdfTab") -> None:
        if tab.viewer.info.can_modify and self._authorize(tab):
            tab.prepare_placement("field")

    def placed_field(self, tab: "PdfTab", region) -> None:
        viewer = tab.viewer
        if not viewer.info or viewer.busy:
            return
        names = {field.name for field in viewer.fields}
        number = len(viewer.fields) + 1
        while f"campo_{number}" in names:
            number += 1
        dialog = FieldDialog(f"campo_{number}", set(), self.window)
        accepted = self.run_dialog(dialog) == QDialog.DialogCode.Accepted
        values = dialog.result_values(region)
        dialog.deleteLater()
        if accepted:
            viewer.change("add_field", values)

    def remove_field(self, tab: "PdfTab") -> None:
        viewer = tab.viewer
        fields = [field for field in viewer.fields if field.kind in FIELD_KIND_NAMES]
        if not fields:
            return
        labels = [f"{field.name} ({FIELD_KIND_NAMES[field.kind]})" for field in fields]
        label, ok = QInputDialog.getItem(
            self.window, "Excluir campo", "Campo desta página:", labels, 0, False
        )
        if not ok or label not in labels:
            return
        field = fields[labels.index(label)]
        choice = QMessageBox.question(
            self.window,
            "Excluir campo",
            f"Excluir o campo {field.name} da cópia de trabalho? Você pode desfazer.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if choice == QMessageBox.StandardButton.Yes and self._authorize(tab):
            viewer.change("remove_field", {"xref": field.xref})

    def report(self, tab: "PdfTab", action: str, report: dict) -> None:
        """Mensagem na barra de status depois de uma edição concluída."""
        if tab is not self.window._active_pdf:
            return
        viewer = tab.viewer
        messages = {
            "insert_blank": "Página(s) em branco inserida(s). Ctrl+Z desfaz.",
            "set_outline": f"Marcadores atualizados: {report.get('entries', 0)} no sumário.",
            "add_field": "Campo criado. Use Preencher formulário para testar.",
            "remove_field": "Campo excluído. Ctrl+Z desfaz.",
        }
        if action == "crop_pages":
            text = f"{report.get('pages', 0)} página(s) cortada(s)."
            if report.get("blank"):
                text += f" {report['blank']} página(s) em branco ficaram como estavam."
            text += " O conteúdo de fora continua no arquivo."
        elif action == "resize_pages":
            text = f"{report.get('pages', 0)} página(s) ajustada(s) ao novo papel."
        else:
            text = messages.get(action)
        if text:
            self.window.statusBar().showMessage(
                text + f"  |  {viewer.info.page_count} página(s) no documento.", 12000
            )
