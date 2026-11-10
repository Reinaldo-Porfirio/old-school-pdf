"""Comandos da janela para organizar, editar e gravar PDFs."""

from collections.abc import Callable
from os.path import abspath
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, Qt
from PySide6.QtWidgets import QDialog, QFileDialog, QInputDialog, QMessageBox

from docforge.application.pdf_output import PdfOutputTask
from docforge.domain.editing import ANNOTATION_LABELS, STAMP_LABELS
from docforge.domain.errors import DocForgeError
from docforge.infrastructure.local_files import (
    OutputFile,
    check_local,
    check_pdf,
    file_stamp,
    same_target,
)
from docforge.ui.edit_dialogs import FormDialog, MergeDialog, RangeDialog

if TYPE_CHECKING:
    from docforge.ui.main_window import MainWindow
    from docforge.ui.pdf_tab import PdfTab


class DocumentTools(QObject):
    def __init__(self, window: "MainWindow") -> None:
        super().__init__(window)
        self.window = window
        self.workspace = window.pdf_workspace
        self.merge_task: PdfOutputTask | None = None
        self.merge_process = None
        self._exit_discards = set()

    def _status(self, text: str) -> None:
        self.window.statusBar().showMessage(text, 9500)

    def _alert(self, text: str) -> None:
        QMessageBox.warning(self.window, "DocForge Ultimate", text)

    def _signature_dialog(self) -> bool:
        choice = QMessageBox.warning(
            self.window,
            "Assinatura digital indicada",
            "O PDF indica uma assinatura digital. Alterar páginas, editar campos ou gravar "
            "uma nova versão pode invalidar essa assinatura. O arquivo de origem é preservado. "
            "Deseja continuar na cópia?",
            QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        return choice == QMessageBox.StandardButton.Ok

    def _authorize(self, tab: "PdfTab") -> bool:
        viewer = tab.viewer
        if viewer.state != "ready" or viewer.busy:
            return False
        if viewer.info.signed and not viewer.signature_confirmed:
            viewer.signature_confirmed = self._signature_dialog()
            return viewer.signature_confirmed
        return True

    def _protected_sources(self, paths: tuple[Path, ...]) -> tuple[Path, ...]:
        opened = (
            path
            for tab in self.window._pdf_tabs()
            if tab.viewer.info
            for path in (tab.viewer.session.source_path, tab.viewer.session.working_copy)
            if path
        )
        return tuple(dict.fromkeys((*paths, *opened)))

    def _overwrite(self, path: Path) -> bool:
        box = QMessageBox(
            QMessageBox.Icon.Warning,
            "O PDF de destino já existe",
            f"Já existe um arquivo chamado {path.name}. Escolha outro nome ou substitua "
            "o destino mantendo uma cópia de segurança.",
            parent=self.window,
        )
        box.setTextFormat(Qt.TextFormat.PlainText)
        other = box.addButton("Escolher outro nome", QMessageBox.ButtonRole.RejectRole)
        replace = box.addButton("Substituir com backup", QMessageBox.ButtonRole.AcceptRole)
        box.setDefaultButton(other)
        box.exec()
        return box.clickedButton() is replace

    def _output_files(
        self, title: str, suggestion: Path, count: int, sources: tuple[Path, ...]
    ) -> list[OutputFile]:
        filename, _ = QFileDialog.getSaveFileName(
            self.window,
            title,
            str(suggestion),
            "Arquivos PDF (*.pdf)",
            options=QFileDialog.Option.DontConfirmOverwrite,
        )
        if not filename:
            return []
        path = Path(abspath(filename))
        if not path.suffix:
            path = path.with_suffix(".pdf")
        targets = (
            [path]
            if count == 1
            else [
                path.with_name(f"{path.stem}-{number:02d}{path.suffix}")
                for number in range(1, count + 1)
            ]
        )
        staged = []
        try:
            for target in targets:
                check_local(target, missing_leaf=True)
                if any(same_target(target, source) for source in sources):
                    raise DocForgeError("Escolha outro nome para preservar o PDF de origem.")
                expected = None
                if target.exists():
                    if count != 1:
                        raise DocForgeError(
                            "Um nome da divisão já existe. Escolha outra base para as saídas."
                        )
                    check_pdf(target)
                    expected = file_stamp(target)
                    if not self._overwrite(target):
                        return []
                staged.append(OutputFile.prepare(target, sources, expected=expected))
        except (OSError, DocForgeError) as error:
            for output in staged:
                output.cleanup()
            self._alert(
                str(error)
                if isinstance(error, DocForgeError)
                else "A pasta de destino está indisponível."
            )
            return []
        return staged

    def _export(
        self,
        tab: "PdfTab",
        title: str,
        suffix: str,
        groups: list[list[tuple[int, int]] | None],
        *,
        save: bool = False,
        done: Callable[[bool], None] | None = None,
        security: dict | None = None,
    ) -> bool:
        if not self._authorize(tab):
            return False
        viewer = tab.viewer
        origin = viewer.session.source_path
        sources = self._protected_sources((origin,))
        suggestion = origin.with_name(f"{origin.stem}-{suffix}.pdf")
        outputs = self._output_files(title, suggestion, len(groups), sources)
        if not outputs:
            return False
        task = PdfOutputTask(
            self.workspace.jobs, title, outputs, sources, self.workspace.jobs_changed.emit
        )
        if not viewer.export(task, groups, save=save, security=security):
            return False

        def finished(ok: bool, message: str) -> None:
            self._status(message)
            if done:
                done(ok)

        viewer.export_completed.connect(finished, Qt.ConnectionType.SingleShotConnection)
        return True

    def export_security(
        self, tab: "PdfTab", title: str, suffix: str, action: str, values: dict
    ) -> bool:
        return self._export(
            tab, title, suffix, [None], security={"action": action, "values": values}
        )

    def save(self, tab: "PdfTab", done: Callable[[bool], None] | None = None) -> bool:
        return self._export(tab, "Salvar como", "editado", [None], save=True, done=done)

    def ranges(self, tab: "PdfTab", mode: str) -> None:
        viewer = tab.viewer
        if viewer.busy or not viewer.info.can_organize:
            return
        dialog = RangeDialog(mode, viewer.page, viewer.info.page_count, self.window)
        accepted = dialog.exec() == QDialog.DialogCode.Accepted
        ranges, angle = dialog.ranges, dialog.angle.currentData()
        dialog.deleteLater()
        if not accepted or not ranges:
            return
        if mode in {"delete", "rotate"}:
            if self._authorize(tab):
                action = "delete_pages" if mode == "delete" else "rotate_pages"
                viewer.change(action, {"ranges": ranges, "angle": angle})
        elif mode == "split":
            self._export(tab, "Dividir PDF", "parte", [[group] for group in ranges])
        else:
            self._export(tab, "Extrair páginas", "paginas", [ranges])

    def choose_move(self, tab: "PdfTab") -> None:
        viewer = tab.viewer
        if viewer.busy or not viewer.info.can_organize:
            return
        target, ok = QInputDialog.getInt(
            self.window,
            "Reordenar páginas",
            f"Posição final da página {viewer.page + 1}",
            viewer.page + 1,
            1,
            viewer.info.page_count,
        )
        if ok:
            self.move_page(tab, viewer.page, target - 1)

    def move_page(self, tab: "PdfTab", source: int, target: int) -> None:
        if source != target and tab.viewer.info.can_organize and self._authorize(tab):
            tab.viewer.change("move_page", {"target": target}, page=source)

    def place(self, tab: "PdfTab", kind: str) -> None:
        if tab.viewer.info.can_annotate and self._authorize(tab):
            tab.prepare_placement(kind)

    def placed(self, tab: "PdfTab", kind: str, region) -> None:
        viewer = tab.viewer
        if not viewer.info or not viewer.info.can_annotate or viewer.busy:
            return
        if kind == "move":
            obj = tab.annotation()
            if obj and obj.movable:
                viewer.change(
                    "move_annotation",
                    {
                        "xref": obj.xref,
                        "delta": (region[0] - obj.region[0], region[1] - obj.region[1]),
                    },
                )
            return
        values = {"kind": kind, "region": region, "view_rotation": viewer.rotation}
        if kind in {"comment", "text"}:
            value, ok = QInputDialog.getMultiLineText(
                self.window, ANNOTATION_LABELS[kind], "Texto da anotação"
            )
            if not ok:
                return
            values["text"] = value
        elif kind == "stamp":
            label, ok = QInputDialog.getItem(
                self.window, "Carimbo", "Modelo", list(STAMP_LABELS), 0, False
            )
            if not ok:
                return
            values["stamp"] = STAMP_LABELS.index(label)
        elif kind == "image":
            filename, _ = QFileDialog.getOpenFileName(
                self.window, "Inserir imagem", "", "Imagens (*.png *.jpg *.jpeg)"
            )
            if not filename:
                return
            values["path"] = abspath(filename)
        viewer.change("add_annotation", values)

    def move_object(self, tab: "PdfTab") -> None:
        if tab.annotation() and tab.annotation().movable and self._authorize(tab):
            tab.prepare_placement("move")

    def change_object_text(self, tab: "PdfTab") -> None:
        obj = tab.annotation()
        if obj and obj.editable and self._authorize(tab):
            text, ok = QInputDialog.getMultiLineText(
                self.window, "Editar anotação", "Texto da anotação", obj.text
            )
            if ok:
                tab.viewer.change("change_annotation", {"xref": obj.xref, "text": text})

    def remove_object(self, tab: "PdfTab") -> None:
        obj = tab.annotation()
        if not obj or not obj.editable or not self._authorize(tab):
            return
        choice = QMessageBox.question(
            self.window,
            "Excluir anotação",
            "Excluir o objeto selecionado da cópia de trabalho? Você pode desfazer.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if choice == QMessageBox.StandardButton.Yes:
            tab.viewer.change("remove_annotation", {"xref": obj.xref})

    def forms(self, tab: "PdfTab") -> None:
        viewer = tab.viewer
        if viewer.info.can_fill and viewer.fields and self._authorize(tab):
            dialog = FormDialog(viewer.fields, self.window)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                viewer.change("fill_field", dialog.value())
            dialog.deleteLater()

    def merge(self) -> None:
        if self.merge_task:
            return
        dialog = MergeDialog(self.workspace.process_factory, self.window)
        accepted = dialog.exec() == QDialog.DialogCode.Accepted
        inputs = dialog.records()
        dialog.deleteLater()
        if not accepted or len(inputs) < 2:
            return
        confirmed = any(item["signed"] for item in inputs)
        if confirmed and not self._signature_dialog():
            return
        paths = tuple(Path(item["path"]) for item in inputs)
        sources = self._protected_sources(paths)
        outputs = self._output_files(
            "Mesclar PDFs", paths[0].with_name("PDFs-mesclados.pdf"), 1, sources
        )
        if not outputs:
            return
        task = self.merge_task = PdfOutputTask(
            self.workspace.jobs, "Mesclar PDFs", outputs, sources, self.workspace.jobs_changed.emit
        )
        self.merge_process = self.workspace.process_factory(self)
        self.merge_process.reply.connect(
            lambda reply, _data: self._finish_merge(reply.get("error"))
        )
        self.merge_process.failed.connect(self._finish_merge)
        self.window.actions["merge"].setEnabled(False)
        task.start()
        if self.merge_task is task:
            self.merge_process.request(
                "merge", {"inputs": inputs, "stage": str(outputs[0].stage), "confirmed": confirmed}
            )

    def cancel_merge(self, task_id) -> None:
        if self.merge_task and self.merge_task.task_id == task_id:
            self.merge_task.cancel()
            self._finish_merge()

    def _finish_merge(self, error: str | None = None) -> None:
        task, self.merge_task = self.merge_task, None
        process, self.merge_process = self.merge_process, None
        if not task:
            return
        process.stop()
        process.deleteLater()
        ok, message = task.finish(error)
        self.window.actions["merge"].setEnabled(True)
        if ok:
            self.window.open_pdfs([task.outputs[0].destination])
        self._status(message)

    def _dirty_choice(self, tab: "PdfTab") -> QMessageBox.StandardButton:
        return QMessageBox.question(
            self.window,
            "Alterações ainda não gravadas",
            "Deseja gravar as alterações desta aba em um novo PDF antes de fechar?",
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )

    def may_close_tab(self, tab: "PdfTab") -> bool:
        if tab.viewer.busy:
            self._status("Aguarde a operação ou cancele a exportação pela fila.")
            return False
        if not tab.viewer.session.dirty:
            return True
        choice = self._dirty_choice(tab)
        if choice == QMessageBox.StandardButton.Save:
            self.save(
                tab, lambda ok: self.window.close_tab(self.window.tabs.indexOf(tab)) if ok else None
            )
        return choice == QMessageBox.StandardButton.Discard

    def may_close_window(self) -> bool:
        tabs = tuple(self.window._pdf_tabs())
        if self.merge_task or any(tab.viewer.busy for tab in tabs):
            self._status("Aguarde as operações ou cancele a exportação pela fila.")
            return False
        for tab in tabs:
            viewer = tab.viewer
            key = (viewer.session.session_id, viewer.revision)
            if not viewer.session.dirty or key in self._exit_discards:
                continue
            self.window.tabs.setCurrentWidget(tab)
            choice = self._dirty_choice(tab)
            if choice == QMessageBox.StandardButton.Discard:
                self._exit_discards.add(key)
                continue
            if choice == QMessageBox.StandardButton.Save and self.save(tab, self._resume_close):
                return False
            self._exit_discards.clear()
            return False
        self._exit_discards.clear()
        return True

    def _resume_close(self, ok: bool) -> None:
        if ok:
            self.window.close()
        else:
            self._exit_discards.clear()
