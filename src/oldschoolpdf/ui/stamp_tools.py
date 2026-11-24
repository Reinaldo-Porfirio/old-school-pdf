"""Comandos de numeração, cabeçalho e rodapé, marca d'água e localizar e substituir."""

from typing import TYPE_CHECKING

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QDialog, QMessageBox

from oldschoolpdf.ui.stamp_dialogs import (
    FindReplaceDialog,
    HeaderFooterDialog,
    RemoveStampsDialog,
    WatermarkDialog,
    page_size,
    source_name,
)

if TYPE_CHECKING:
    from oldschoolpdf.ui.main_window import MainWindow
    from oldschoolpdf.ui.pdf_tab import PdfTab

STAMP_ACTIONS = ("header_footer", "watermark", "remove_stamps", "find_replace")


def _pages(numbers: list[int], count: int) -> str:
    text = ", ".join(str(number) for number in numbers)
    return text + (f" e mais {count - len(numbers)}" if count > len(numbers) else "")


class StampTools(QObject):
    def __init__(self, window: "MainWindow") -> None:
        super().__init__(window)
        self.window = window

    # Hooks substituídos nos testes.
    def run_dialog(self, dialog: QDialog) -> int:
        return dialog.exec()

    def warn(self, title: str, text: str) -> None:
        QMessageBox.information(self.window, title, text)

    def update_controls(self, tab: "PdfTab | None") -> None:
        viewer = tab.viewer if tab else None
        info = viewer.info if viewer else None
        ready = bool(info and viewer.state == "ready" and not viewer.busy)
        modify = bool(ready and info.can_modify)
        for key in STAMP_ACTIONS:
            action = self.window.actions[key]
            action.setEnabled(modify)
            if info and ready and not info.can_modify:
                action.setToolTip("As permissões deste PDF não permitem alterar o conteúdo.")
            else:
                action.setToolTip(action.text().replace("&", "").rstrip("…"))

    def _authorize(self, tab: "PdfTab") -> bool:
        return self.window.document_tools._authorize(tab)

    def _run(self, tab: "PdfTab", dialog: QDialog, action: str) -> None:
        accepted = self.run_dialog(dialog) == QDialog.DialogCode.Accepted
        values = dialog.values()
        dialog.deleteLater()
        if accepted and self._authorize(tab):
            tab.viewer.change(action, values)

    def header_footer(self, tab: "PdfTab") -> None:
        viewer = tab.viewer
        if viewer.info.can_modify:
            dialog = HeaderFooterDialog(
                viewer.page, viewer.info.page_count, page_size(tab), source_name(tab), self.window
            )
            self._run(tab, dialog, "header_footer")

    def watermark(self, tab: "PdfTab") -> None:
        viewer = tab.viewer
        if viewer.info.can_modify:
            dialog = WatermarkDialog(
                viewer.page, viewer.info.page_count, page_size(tab), self.window
            )
            self._run(tab, dialog, "watermark")

    def remove_stamps(self, tab: "PdfTab") -> None:
        viewer = tab.viewer
        if viewer.info.can_modify:
            dialog = RemoveStampsDialog(viewer.page, viewer.info.page_count, self.window)
            self._run(tab, dialog, "remove_stamps")

    def find_replace(self, tab: "PdfTab") -> None:
        viewer = tab.viewer
        if not viewer.info.can_modify:
            return
        dialog = FindReplaceDialog(viewer, self.window)
        tab_query = tab.query.text().strip()
        if tab_query:
            dialog.query.setText(tab_query)
        self._run(tab, dialog, "replace_matches")

    def report(self, tab: "PdfTab", action: str, report: dict) -> None:
        """Mensagem na barra de status e, se algo merece atenção, um aviso."""
        if tab is not self.window._active_pdf:
            return
        status = self.window.statusBar()
        if action == "header_footer":
            text = f"Numeração, cabeçalho e rodapé aplicados em {report.get('pages', 0)} página(s)."
            if report.get("replaced"):
                text += f" O anterior foi substituído em {report['replaced']}."
            status.showMessage(text + " Ctrl+Z desfaz.", 12000)
            if report.get("crowded_count"):
                self.warn(
                    "Confira o cabeçalho e o rodapé",
                    "Nas páginas "
                    + _pages(report["crowded"], report["crowded_count"])
                    + " o texto novo ficou encostado em algo que já existia na página. "
                    "Se não ficou bom, desfaça (Ctrl+Z) e aumente a distância da borda ou "
                    "diminua a fonte.",
                )
        elif action == "watermark":
            status.showMessage(
                f"Marca d'água aplicada em {report.get('pages', 0)} página(s). Ctrl+Z desfaz.",
                12000,
            )
            if report.get("hidden_count"):
                self.warn(
                    "Marca d'água escondida em algumas páginas",
                    "Nas páginas "
                    + _pages(report["hidden"], report["hidden_count"])
                    + " a marca ficou atrás de uma imagem que cobre a página, como em "
                    "documentos digitalizados. Para que ela apareça também nelas, desfaça "
                    "(Ctrl+Z) e escolha “Na frente do conteúdo”.",
                )
        elif action == "remove_stamps":
            removed = report.get("removed", {})
            parts = []
            if removed.get("header"):
                parts.append(f"cabeçalho e rodapé de {removed['header']} página(s)")
            if removed.get("watermark"):
                parts.append(f"marca d'água de {removed['watermark']} página(s)")
            status.showMessage("Removido: " + " e ".join(parts) + ". Ctrl+Z desfaz.", 12000)
        elif action == "replace_matches":
            text = (
                f"{report.get('items', 0)} ocorrência(s) substituída(s) em "
                f"{report.get('pages', 0)} página(s). Ctrl+Z desfaz."
            )
            status.showMessage(text, 15000)
            failed = report.get("failed") or []
            if failed:
                lines = [
                    f"• Página {item['page']}"
                    + (f" (“{item['text'][:40]}”)" if item.get("text") else "")
                    + f": {item['reason']}"
                    for item in failed[:8]
                ]
                if len(failed) > 8:
                    lines.append(f"… e mais {len(failed) - 8}.")
                self.warn(
                    "Algumas ocorrências ficaram como estavam",
                    text + "\n\nEstas não puderam ser trocadas com segurança:\n" + "\n".join(lines),
                )
