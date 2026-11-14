import pymupdf
import pytest
from PySide6.QtCore import QRectF
from PySide6.QtPrintSupport import QPrinter
from PySide6.QtWidgets import QMessageBox

from oldschoolpdf.app import create_window
from oldschoolpdf.domain.tasks import TaskState
from oldschoolpdf.ui.print_tools import fit_rect, page_sequence, print_dpi


@pytest.fixture
def window(qtbot, tmp_path):
    def discard(window):
        for tab in tuple(window._pdf_tabs()):
            tab.viewer.session.dirty = False
        window.pdf_workspace.close()

    window = create_window(tmp_path / "settings.ini")
    qtbot.addWidget(window, before_close_func=discard)
    window.show()
    qtbot.waitUntil(window.isVisible)
    return window


def make_pdf(path, count=3, *, landscape_page=None, permissions=None):
    with pymupdf.open() as pdf:
        for number in range(count):
            width, height = (600, 400) if number == landscape_page else (400, 600)
            page = pdf.new_page(width=width, height=height)
            page.draw_rect(pymupdf.Rect(20, 20, 200, 120), color=None, fill=(0.1, 0.2, 0.5))
            page.insert_text((30, 200), f"Página impressa {number + 1}", fontsize=18)
        if permissions is None:
            pdf.save(path)
        else:
            pdf.save(
                path,
                encryption=pymupdf.PDF_ENCRYPT_AES_256,
                owner_pw="dono-teste",
                user_pw="",
                permissions=permissions,
            )
    return path


def open_tab(window, qtbot, path):
    tab = window.open_pdfs([path])[0]
    qtbot.waitUntil(lambda: tab.canvas.has_page, timeout=10000)
    return tab


def to_file(window, monkeypatch, output, configure=None):
    def create():
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
        printer.setOutputFileName(str(output))
        return printer

    def accept(printer, page_count):
        if configure:
            configure(printer)
        return True

    monkeypatch.setattr(window.print_tools, "create_printer", create)
    monkeypatch.setattr(window.print_tools, "choose_options", accept)


def printed_pages(path):
    with pymupdf.open(path) as pdf:
        pages = []
        for page in pdf:
            pixmap = page.get_pixmap(dpi=30)
            samples = pixmap.samples
            dark = sum(1 for value in samples[::3] if value < 128)
            pages.append((page.rect.width > page.rect.height, dark))
        return pages


def finished_job(window):
    return [
        job
        for job in window.jobs.list_tasks()
        if job.spec.kind == "pdf_print" and job.state.terminal
    ]


def test_print_all_pages_reaches_printer_and_queue(window, qtbot, tmp_path, monkeypatch):
    tab = open_tab(window, qtbot, make_pdf(tmp_path / "três páginas.pdf"))
    output = tmp_path / "impresso.pdf"
    to_file(window, monkeypatch, output)
    assert window.actions["print"].isEnabled()
    window.actions["print"].trigger()
    qtbot.waitUntil(lambda: window.print_tools.job is None, timeout=20000)
    pages = printed_pages(output)
    assert len(pages) == 3
    assert all(dark > 20 for _, dark in pages)
    job = finished_job(window)[-1]
    assert job.state == TaskState.SUCCEEDED
    assert not tab.viewer.busy and not tab.viewer.printing


def test_print_range_current_page_and_copies(window, qtbot, tmp_path, monkeypatch):
    tab = open_tab(window, qtbot, make_pdf(tmp_path / "intervalo.pdf", count=4))
    output = tmp_path / "intervalo-impresso.pdf"

    def range_with_copies(printer):
        printer.setPrintRange(QPrinter.PrintRange.PageRange)
        printer.setFromTo(2, 3)
        printer.setCopyCount(2)
        printer.setCollateCopies(True)

    to_file(window, monkeypatch, output, range_with_copies)
    window.actions["print"].trigger()
    qtbot.waitUntil(lambda: window.print_tools.job is None, timeout=20000)
    assert len(printed_pages(output)) == 4

    tab.viewer.go_to(2)
    current = tmp_path / "atual.pdf"
    to_file(
        window,
        monkeypatch,
        current,
        lambda printer: printer.setPrintRange(QPrinter.PrintRange.CurrentPage),
    )
    qtbot.waitUntil(lambda: window.actions["print"].isEnabled())
    window.actions["print"].trigger()
    qtbot.waitUntil(lambda: window.print_tools.job is None, timeout=20000)
    assert len(printed_pages(current)) == 1


def test_landscape_page_is_rotated_to_fill_portrait_paper(window, qtbot, tmp_path, monkeypatch):
    open_tab(window, qtbot, make_pdf(tmp_path / "paisagem.pdf", count=2, landscape_page=1))
    output = tmp_path / "paisagem-impresso.pdf"
    to_file(window, monkeypatch, output)
    window.actions["print"].trigger()
    qtbot.waitUntil(lambda: window.print_tools.job is None, timeout=20000)
    pages = printed_pages(output)
    assert len(pages) == 2
    # O papel continua em pé e a página deitada ocupa a folha girada, sem sair branca.
    assert not pages[1][0] and pages[1][1] > 20


def test_pdf_without_print_permission_disables_command(window, qtbot, tmp_path):
    allowed = pymupdf.PDF_PERM_ACCESSIBILITY | pymupdf.PDF_PERM_COPY
    tab = open_tab(window, qtbot, make_pdf(tmp_path / "sem-impressao.pdf", permissions=allowed))
    assert not tab.viewer.info.can_print
    assert not window.actions["print"].isEnabled()
    assert "não permitem imprimir" in window.actions["print"].toolTip()


def test_low_quality_permission_limits_resolution(window, qtbot, tmp_path):
    allowed = pymupdf.PDF_PERM_PRINT | pymupdf.PDF_PERM_ACCESSIBILITY
    tab = open_tab(window, qtbot, make_pdf(tmp_path / "baixa.pdf", permissions=allowed))
    assert tab.viewer.info.can_print and not tab.viewer.info.can_print_hq
    assert print_dpi(1200, tab.viewer.info.can_print_hq) == 150
    assert print_dpi(1200, True) == 300
    assert print_dpi(0, True) == 300


def test_cancel_and_closing_the_tab_end_printing_cleanly(window, qtbot, tmp_path, monkeypatch):
    tab = open_tab(window, qtbot, make_pdf(tmp_path / "longo.pdf", count=30))
    to_file(window, monkeypatch, tmp_path / "cancelado.pdf")
    window.actions["print"].trigger()
    job = window.print_tools.job
    assert job is not None and tab.viewer.printing
    window.jobs_dock.cancel_requested.emit(job.task_id)
    qtbot.waitUntil(lambda: window.print_tools.job is None, timeout=10000)
    assert window.jobs.status(job.task_id).state == TaskState.CANCELLED
    assert not tab.viewer.busy

    warnings = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *args: warnings.append(args))
    to_file(window, monkeypatch, tmp_path / "fechado.pdf")
    window.actions["print"].trigger()
    job = window.print_tools.job
    # A interface não deixa fechar a aba ocupada; o processo pode encerrar mesmo assim.
    assert not window.document_tools.may_close_tab(tab)
    tab.viewer.close()
    qtbot.waitUntil(lambda: window.print_tools.job is None, timeout=10000)
    assert window.jobs.status(job.task_id).state == TaskState.FAILED
    assert warnings and "fechada" in warnings[-1][2]


def test_page_sequence_and_fit_rules():
    printer = QPrinter()
    printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
    assert page_sequence(printer, 1, 3) == [0, 1, 2]
    printer.setPrintRange(QPrinter.PrintRange.PageRange)
    printer.setFromTo(2, 9)
    assert page_sequence(printer, 0, 3) == [1, 2]
    printer.setPageOrder(QPrinter.PageOrder.LastPageFirst)
    printer.setCopyCount(2)
    printer.setCollateCopies(False)
    assert page_sequence(printer, 0, 3) == [2, 2, 1, 1]
    area = QRectF(0, 0, 100, 200)
    assert fit_rect(area, 50, 50, False) == QRectF(0, 50, 100, 100)
    assert fit_rect(area, 400, 200, True) == QRectF(0, 0, 100, 200)
