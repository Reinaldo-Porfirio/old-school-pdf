"""Entrada da interface para OCR, conversão e lotes locais."""

from dataclasses import replace
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QDialog

from oldschoolpdf.application.media_runner import MediaRunner
from oldschoolpdf.domain.media import MediaOperation
from oldschoolpdf.domain.tasks import TaskState
from oldschoolpdf.infrastructure.ocr_models import available_models
from oldschoolpdf.ui.media_dialogs import BatchDialog, BatchReport
from oldschoolpdf.ui.ocr_setup import OcrSetupDialog

if TYPE_CHECKING:
    from oldschoolpdf.ui.main_window import MainWindow

MEDIA_ACTIONS = {
    "ocr": ("Reconhecer texto…", "ocr", MediaOperation.OCR),
    "images": ("Exportar PDF como imagens…", "image", MediaOperation.RENDER),
    "images_pdf": ("Reunir imagens em PDF…", "image", MediaOperation.IMAGES_PDF),
    "extract_text": ("Extrair texto UTF-8…", "text", MediaOperation.TEXT),
    "extract_images": ("Extrair imagens incorporadas…", "image", MediaOperation.EXTRACT_IMAGES),
    "compress": ("Otimizar PDF…", "save", MediaOperation.OPTIMIZE),
    "batch": ("Processar lote…", "merge", MediaOperation.OPTIMIZE),
}


class MediaTools(QObject):
    def __init__(self, window: "MainWindow") -> None:
        super().__init__(window)
        self.window = window
        workspace = window.pdf_workspace
        self.runner = MediaRunner(workspace.jobs, workspace.process_factory, self)
        self.runner.changed.connect(self._changed)
        self.runner.completed.connect(self._completed)

    def update_controls(self, *, refresh_models: bool = True) -> None:
        window = self.window
        prefs = window.preferences
        if refresh_models:
            available = available_models(prefs.ocr_tessdata)
            window.capabilities.ocr_languages = tuple(
                code for code in prefs.ocr_languages if code in available
            )
        languages = window.capabilities.ocr_languages
        for key in MEDIA_ACTIONS:
            window.actions[key].setEnabled(
                not self.runner.active and (key != "ocr" or bool(languages))
            )
        reason = (
            "OCR local com os idiomas validados."
            if languages
            else "Valide por.traineddata ou eng.traineddata em OCR > Configurar OCR local."
        )
        window.actions["ocr"].setToolTip(reason)
        window.actions["ocr"].setStatusTip(reason)
        window.actions["batch_report"].setEnabled(bool(self.runner.records()))
        window.actions["batch_cancel"].setEnabled(self.runner.active)

    def show_setup(self) -> None:
        window = self.window
        prefs = window.preferences
        self.update_controls()
        dialog = OcrSetupDialog(
            self.runner.process_factory,
            prefs.ocr_tessdata,
            window.capabilities.ocr_languages,
            window,
        )
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.result_settings is not None:
            directory, languages = dialog.result_settings
            window.apply_preferences(
                replace(prefs, ocr_tessdata=directory, ocr_languages=languages)
            )
            window._save_or_warn()
            window.statusBar().showMessage(
                "Modelos de OCR configurados." if languages else "OCR desativado.", 7000
            )
        dialog.deleteLater()

    def show_batch(self, mode: MediaOperation) -> None:
        if self.runner.active:
            return
        self.update_controls()
        window = self.window
        if mode == MediaOperation.OCR and not window.capabilities.ocr_languages:
            window.statusBar().showMessage(
                "Modelos indisponíveis. Confira Configurar OCR local.", 8000
            )
            return
        tab = window._active_pdf
        source = preview = None
        if (
            tab
            and tab.viewer.info
            and tab.viewer.revision == 0
            and not tab.viewer.session.dirty
            and tab.viewer.session.working_copy is None
        ):
            source = tab.viewer.session.source_path
            preview = tab.canvas.page_item.pixmap()
        dialog = BatchDialog(
            mode,
            window.preferences.ocr_tessdata,
            window.capabilities.ocr_languages,
            source,
            preview,
            window,
        )
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.request is not None:
            self.runner.start(dialog.request)
        dialog.deleteLater()

    def show_report(self) -> None:
        dialog = BatchReport(self.runner, self.window)
        dialog.open_pdf.connect(lambda path: self.window.open_pdfs([path]))
        dialog.exec()
        dialog.deleteLater()

    def _changed(self) -> None:
        self.update_controls(refresh_models=False)
        self.window.jobs_dock.refresh()

    def _completed(self) -> None:
        records = self.runner.records()
        success = sum(item.state == TaskState.SUCCEEDED for item in records)
        self.window.statusBar().showMessage(
            f"Processamento finalizado · {success}/{len(records)} concluída(s). "
            "Consulte o relatório do lote.",
            10000,
        )
