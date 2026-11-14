"""Impressão do PDF ativo: diálogo do sistema e páginas renderizadas uma a uma."""

from contextlib import suppress
from typing import TYPE_CHECKING
from uuid import UUID

from PySide6.QtCore import QObject, QRectF, Signal
from PySide6.QtGui import QImage, QPainter
from PySide6.QtPrintSupport import QAbstractPrintDialog, QPrintDialog, QPrinter
from PySide6.QtWidgets import QDialog, QMessageBox

from oldschoolpdf.application.job_service import JobRegistry
from oldschoolpdf.application.pdf_viewer import PageFrame, PdfViewer
from oldschoolpdf.domain.tasks import TaskSpec, TaskState

if TYPE_CHECKING:
    from oldschoolpdf.ui.main_window import MainWindow
    from oldschoolpdf.ui.pdf_tab import PdfTab

HIGH_DPI = 300
LOW_DPI = 150
MAX_PRINT_PAGES = 5000


def print_dpi(printer_resolution: int, high_quality: bool) -> int:
    """Resolução da imagem enviada: a da impressora, limitada pela permissão do PDF."""
    limit = HIGH_DPI if high_quality else LOW_DPI
    return max(72, min(printer_resolution or limit, limit))


def page_sequence(printer: QPrinter, current: int, count: int) -> list[int]:
    """Páginas de base zero na ordem de impressão, com cópias quando o driver não as faz."""
    match printer.printRange():
        case QPrinter.PrintRange.CurrentPage:
            pages = [current]
        case QPrinter.PrintRange.PageRange:
            first = max(1, min(printer.fromPage() or 1, count))
            last = max(first, min(printer.toPage() or count, count))
            pages = list(range(first - 1, last))
        case _:
            pages = list(range(count))
    if printer.pageOrder() == QPrinter.PageOrder.LastPageFirst:
        pages.reverse()
    copies = 1 if printer.supportsMultipleCopies() else max(1, printer.copyCount())
    if printer.collateCopies():
        return pages * copies
    return [page for page in pages for _ in range(copies)]


def fit_rect(area: QRectF, width: int, height: int, rotate: bool) -> QRectF:
    """Maior retângulo centralizado na área que mantém a proporção da página."""
    if rotate:
        width, height = height, width
    scale = min(area.width() / width, area.height() / height)
    target_width, target_height = width * scale, height * scale
    return QRectF(
        area.x() + (area.width() - target_width) / 2,
        area.y() + (area.height() - target_height) / 2,
        target_width,
        target_height,
    )


class PrintJob(QObject):
    finished = Signal(bool, str)

    def __init__(
        self,
        viewer: PdfViewer,
        printer: QPrinter,
        pages: list[int],
        scale: float,
        jobs: JobRegistry,
    ) -> None:
        super().__init__(viewer)
        self.viewer = viewer
        self.printer = printer
        self.pages = pages
        self.scale = scale
        self.jobs = jobs
        self.painter = QPainter()
        self.done = False
        name = viewer.session.source_path.name
        self.task_id = jobs.submit(TaskSpec("pdf_print", f"Imprimir {name}"))
        viewer.workspace.jobs_changed.emit()

    def start(self) -> None:
        self.jobs.start(self.task_id)
        self.viewer.workspace.jobs_changed.emit()
        if not self.painter.begin(self.printer):
            self._finish("Não foi possível iniciar a impressão. Verifique a impressora.")
            return
        self.viewer.print_frame_ready.connect(self._frame)
        self.viewer.print_failed.connect(self._failed)
        if not self.viewer.print_pages(self.pages, self.scale):
            self._finish("A aba está ocupada. Tente imprimir novamente em instantes.")

    def cancel(self) -> None:
        if self.done:
            return
        self.jobs.cancel(self.task_id)
        self.printer.abort()
        self._finish(cancelled=True)

    def _failed(self, error: str) -> None:
        self._finish(error)

    def _frame(self, index: int, frame: PageFrame) -> None:
        if self.done:
            return
        if index > 0 and not self.printer.newPage():
            self._finish("A impressora recusou uma nova página.")
            return
        image = frame.image
        picture = QImage(
            image.data, image.width, image.height, image.stride, QImage.Format.Format_RGB888
        )
        self._draw(picture)
        done = index + 1
        self.jobs.update_progress(
            self.task_id,
            min(99, done * 100 // len(self.pages)),
            detail=f"Página {done} de {len(self.pages)}",
        )
        self.viewer.workspace.jobs_changed.emit()
        if done == len(self.pages):
            self._finish()

    def _draw(self, picture: QImage) -> None:
        area = QRectF(self.printer.pageRect(QPrinter.Unit.DevicePixel))
        area.moveTo(0, 0)
        landscape_page = picture.width() > picture.height()
        landscape_paper = area.width() > area.height()
        # Página deitada em papel em pé (ou o contrário) é girada para aproveitar o papel.
        rotate = landscape_page != landscape_paper and picture.width() != picture.height()
        target = fit_rect(area, picture.width(), picture.height(), rotate)
        painter = self.painter
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        if rotate:
            painter.translate(target.center())
            painter.rotate(90)
            painter.drawImage(
                QRectF(-target.height() / 2, -target.width() / 2, target.height(), target.width()),
                picture,
            )
        else:
            painter.drawImage(target, picture)
        painter.restore()

    def _finish(self, error: str | None = None, *, cancelled: bool = False) -> None:
        if self.done:
            return
        self.done = True
        if self.painter.isActive():
            self.painter.end()
        for signal, slot in (
            (self.viewer.print_frame_ready, self._frame),
            (self.viewer.print_failed, self._failed),
        ):
            with suppress(RuntimeError, TypeError):
                signal.disconnect(slot)
        self.viewer.end_print()
        if self.jobs.status(self.task_id).state == TaskState.PENDING:
            self.jobs.start(self.task_id)
        if not self.jobs.status(self.task_id).state.terminal:
            self.jobs.finish(self.task_id, error=error)
        self.viewer.workspace.jobs_changed.emit()
        if cancelled:
            self.finished.emit(False, "Impressão cancelada.")
        elif error:
            self.finished.emit(False, error)
        else:
            self.finished.emit(True, f"Impressão enviada: {len(self.pages)} página(s).")


class PrintTools(QObject):
    def __init__(self, window: "MainWindow") -> None:
        super().__init__(window)
        self.window = window
        self.job: PrintJob | None = None

    def create_printer(self) -> QPrinter:
        return QPrinter(QPrinter.PrinterMode.HighResolution)

    def choose_options(self, printer: QPrinter, page_count: int) -> bool:
        """Mostra o diálogo de impressão do sistema; devolve se o usuário confirmou."""
        dialog = QPrintDialog(printer, self.window)
        dialog.setWindowTitle("Imprimir")
        dialog.setMinMax(1, page_count)
        for option in (
            QAbstractPrintDialog.PrintDialogOption.PrintPageRange,
            QAbstractPrintDialog.PrintDialogOption.PrintCurrentPage,
            QAbstractPrintDialog.PrintDialogOption.PrintCollateCopies,
            QAbstractPrintDialog.PrintDialogOption.PrintToFile,
        ):
            dialog.setOption(option, True)
        dialog.setOption(QAbstractPrintDialog.PrintDialogOption.PrintSelection, False)
        return dialog.exec() == QDialog.DialogCode.Accepted

    def update_controls(self, tab: "PdfTab | None") -> None:
        viewer = tab.viewer if tab else None
        info = viewer.info if viewer else None
        action = self.window.actions["print"]
        ready = bool(info and viewer.state == "ready" and not viewer.busy and self.job is None)
        action.setEnabled(bool(ready and info.can_print))
        if info and not info.can_print:
            action.setToolTip("As permissões deste PDF não permitem imprimir.")
        else:
            action.setToolTip("Imprimir o PDF da aba ativa")

    def print_document(self, tab: "PdfTab") -> None:
        viewer = tab.viewer
        info = viewer.info
        if self.job is not None or info is None or viewer.busy:
            return
        if not info.can_print:
            QMessageBox.warning(
                self.window, "Imprimir", "As permissões deste PDF não permitem imprimir."
            )
            return
        printer = self.create_printer()
        printer.setDocName(viewer.session.source_path.name)
        printer.setFromTo(1, info.page_count)
        if not self.choose_options(printer, info.page_count):
            return
        pages = page_sequence(printer, viewer.page, info.page_count)
        if len(pages) > MAX_PRINT_PAGES:
            QMessageBox.warning(
                self.window,
                "Imprimir",
                f"Imprima até {MAX_PRINT_PAGES} páginas por vez. Escolha um intervalo menor.",
            )
            return
        dpi = print_dpi(printer.resolution(), info.can_print_hq)
        self.job = PrintJob(viewer, printer, pages, dpi / 72, self.window.jobs)
        self.job.finished.connect(self._finished)
        self.job.start()
        self.window._update_pdf_controls()

    def cancel(self, task_id: UUID) -> None:
        if self.job and self.job.task_id == task_id:
            self.job.cancel()

    def _finished(self, success: bool, message: str) -> None:
        self.job = None
        self.window.statusBar().showMessage(message, 8000)
        if not success and message != "Impressão cancelada.":
            QMessageBox.warning(self.window, "Imprimir", message)
        self.window._update_pdf_controls()
