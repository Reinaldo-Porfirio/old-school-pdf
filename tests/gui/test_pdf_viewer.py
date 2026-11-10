import json
import subprocess
import sys

import pymupdf
import pytest
from PySide6.QtCore import QMimeData, QPointF, QProcess, Qt, QTimer, QUrl
from PySide6.QtGui import QDesktopServices, QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import QApplication, QFileDialog, QLineEdit

from oldschoolpdf.domain.tasks import TaskState


@pytest.fixture
def make_pdf(tmp_path):
    def create(
        name="Relatório ç 漢字 📝.pdf", *, count=3, password=None, permissions=-1, active=False
    ):
        path = tmp_path / name
        with pymupdf.open() as doc:
            for i in range(count):
                page = doc.new_page(width=420, height=600)
                page.insert_text((32, 50), f"Página {i + 1}", fontsize=18)
                if i in (0, 2):
                    page.insert_text((32, 100), "Relatório de obra", fontsize=16)
                page.insert_text((32, 160), "Outro conteúdo que fica fora da seleção.", fontsize=12)
            doc.set_metadata({"title": "<b>Título de teste</b>", "author": "Equipe de teste"})
            if active:
                page = doc[0]
                page.insert_link(
                    {
                        "kind": pymupdf.LINK_URI,
                        "from": pymupdf.Rect(30, 80, 160, 105),
                        "uri": "https://example.invalid/",
                    }
                )
                marker = (tmp_path / "execucao-indevida.txt").as_posix()
                action = f"<< /S /Launch /F ({marker}) >>"
                doc.xref_set_key(doc.pdf_catalog(), "OpenAction", action)
            options = (
                {}
                if password is None
                else {
                    "encryption": pymupdf.PDF_ENCRYPT_AES_256,
                    "user_pw": password,
                    "owner_pw": "senha-de-proprietario-de-teste",
                    "permissions": permissions,
                }
            )
            doc.save(path, **options)
        return path

    return create


def _wait_page(qtbot, tab, page):
    qtbot.waitUntil(lambda: tab.canvas.has_page and tab.canvas.page == page, timeout=8000)


def test_t01_open_menu_thumbnails_page_navigation_and_preserve_original(
    window, qtbot, make_pdf, monkeypatch
):
    path = make_pdf()
    before = path.read_bytes()
    monkeypatch.setattr(QFileDialog, "getOpenFileNames", lambda *args: ([str(path)], ""))
    window.actions["open"].trigger()
    tab = window.tabs.currentWidget()
    _wait_page(qtbot, tab, 0)
    assert tab.viewer.info.page_count == 3
    assert "Página 1/3" in window.document_status.text()
    assert window.properties_dock.fields["title"].text() == "<b>Título de teste</b>"
    dock = window.navigation_dock
    qtbot.waitUntil(lambda: 0 in dock.model.images, timeout=6000)
    index = dock.model.index(1)
    qtbot.mouseClick(
        dock.thumbnails.viewport(),
        Qt.MouseButton.LeftButton,
        pos=dock.thumbnails.visualRect(index).center(),
    )
    _wait_page(qtbot, tab, 1)
    tab.page_number.setValue(3)
    _wait_page(qtbot, tab, 2)
    assert not window.actions["page_next"].isEnabled()
    assert window.open_pdfs([path]) == [tab]
    assert window.tabs.count() == 2
    window.close_current_tab()
    assert path.read_bytes() == before


def test_t02_password_retry_then_open_and_keep_copy_permission(window, qtbot, make_pdf):
    path = make_pdf("protegido.pdf", password="teste-m1-123", permissions=0)
    tab = window.open_pdfs([path])[0]
    qtbot.waitUntil(lambda: tab.viewer.state == "password", timeout=8000)
    assert tab.password.echoMode() == QLineEdit.EchoMode.Password
    assert not tab.canvas.has_page
    tab.password.setText("incorreta")
    qtbot.keyClick(tab.password, Qt.Key.Key_Return)
    qtbot.waitUntil(lambda: "incorreta" in tab.password_notice.text(), timeout=6000)
    assert not tab.password.text()
    tab.password.setText("teste-m1-123")
    qtbot.keyClick(tab.password, Qt.Key.Key_Return)
    _wait_page(qtbot, tab, 0)
    assert not tab.password.text()
    assert tab.viewer.info.protected
    assert not window.actions["copy"].isEnabled()
    assert not window.actions["select"].isEnabled()
    assert "cópia restrita" in window.properties_dock.fields["access"].text()
    assert window.close()
    assert "teste-m1-123" not in window.settings.path.read_text(encoding="utf-8")
    assert all(record.error is None for record in window.jobs.list_tasks())


def test_t03_bad_header_and_corrupt_file_leave_other_pdf_usable(window, qtbot, make_pdf, tmp_path):
    good = window.open_pdfs([make_pdf()])[0]
    _wait_page(qtbot, good, 0)
    invalid = tmp_path / "outro-formato.pdf"
    invalid.write_bytes(b"Not a PDF")
    broken = tmp_path / "corrompido.pdf"
    broken.write_bytes(b"%PDF-1.7\ntruncated\n")
    first, second = window.open_pdfs([invalid, broken])
    qtbot.waitUntil(lambda: first.viewer.state == second.viewer.state == "error", timeout=8000)
    assert "cabeçalho PDF válido" in first.notice_text.text()
    assert "corrompido" in second.notice_text.text()
    assert not window.actions["find"].isEnabled()
    window.tabs.setCurrentWidget(good)
    window.actions["page_next"].trigger()
    _wait_page(qtbot, good, 1)
    assert invalid.read_bytes() == b"Not a PDF"
    assert broken.read_bytes() == b"%PDF-1.7\ntruncated\n"


def test_t04_zoom_preserves_aspect_and_rotation_is_only_visual(window, qtbot, make_pdf):
    path = make_pdf()
    before = path.read_bytes()
    tab = window.open_pdfs([path])[0]
    _wait_page(qtbot, tab, 0)
    for zoom in (0.5, 2.0):
        index = window.zoom_combo.findData(zoom)
        assert index >= 0
        window.zoom_combo.setCurrentIndex(index)
        window.zoom_combo.activated.emit(index)
        qtbot.waitUntil(lambda level=zoom: tab.actual_zoom == level, timeout=5000)
        assert tab.canvas.bounds.width() == pytest.approx(420 * zoom)
        assert tab.canvas.bounds.height() == pytest.approx(600 * zoom)
    window.actions["rotate"].trigger()
    qtbot.waitUntil(lambda: tab.canvas.rotation == 90, timeout=5000)
    assert tab.canvas.bounds.width() == pytest.approx(1200)
    assert tab.canvas.bounds.height() == pytest.approx(840)
    window.actions["fit_width"].trigger()
    qtbot.waitUntil(lambda: tab.actual_zoom < 2.0, timeout=5000)
    assert tab.canvas.bounds.width() < tab.canvas.viewport().width()
    window.actions["fit"].trigger()
    qtbot.waitUntil(
        lambda: tab.canvas.bounds.height() < tab.canvas.viewport().height(), timeout=5000
    )
    assert path.read_bytes() == before


def test_t05_search_accented_phrase_jump_and_copy_selected_area(
    window, qtbot, make_pdf, monkeypatch
):
    tab = window.open_pdfs([make_pdf()])[0]
    _wait_page(qtbot, tab, 0)
    window.activateWindow()
    tab.canvas.setFocus()
    qtbot.keyClick(tab.canvas, Qt.Key.Key_F, Qt.KeyboardModifier.ControlModifier)
    qtbot.waitUntil(tab.search.isVisible)
    assert tab.query.hasFocus()
    tab.query.setText("RELATÓRIO DE OBRA")
    qtbot.keyClick(tab.query, Qt.Key.Key_Return)
    qtbot.waitUntil(lambda: len(tab.viewer.hits) == 2 and not tab.viewer.searching, timeout=8000)
    assert tab.search_status.text() == "1/2 · Busca concluída"
    qtbot.keyClick(tab.query, Qt.Key.Key_F3)
    _wait_page(qtbot, tab, 2)
    assert tab.search_status.text() == "2/2 · Busca concluída"
    assert [index.row() for index in window.navigation_dock.thumbnails.selectedIndexes()] == [2]
    assert tab.canvas._markers
    writes = []

    class Clipboard:
        setText = writes.append

    monkeypatch.setattr(QApplication, "clipboard", Clipboard)
    scale = tab.actual_zoom
    viewport = tab.canvas.viewport()
    start = tab.canvas.mapFromScene(QPointF(30 * scale, 79 * scale))
    end = tab.canvas.mapFromScene(QPointF(220 * scale, 113 * scale))
    qtbot.mousePress(viewport, Qt.MouseButton.LeftButton, pos=start)
    qtbot.mouseMove(viewport, pos=end)
    qtbot.mouseRelease(viewport, Qt.MouseButton.LeftButton, pos=end)
    assert tab.canvas.selected_region()
    qtbot.keyClick(tab.canvas, Qt.Key.Key_C, Qt.KeyboardModifier.ControlModifier)
    qtbot.waitUntil(lambda: bool(writes), timeout=6000)
    assert writes[0].strip() == "Relatório de obra"


def test_drop_opens_local_pdf_and_restores_each_tabs_page_and_zoom(window, qtbot, make_pdf):
    first = window.open_pdfs([make_pdf()])[0]
    _wait_page(qtbot, first, 0)
    first.page_number.setValue(2)
    first.set_zoom(1.25)
    _wait_page(qtbot, first, 1)
    path = make_pdf("segundo.PDF", count=1)
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(path))])
    actions = Qt.DropAction.CopyAction | Qt.DropAction.MoveAction
    event = QDragEnterEvent(
        QPointF(20, 20), actions, mime, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier
    )
    QApplication.sendEvent(window, event)
    assert event.isAccepted()
    drop = QDropEvent(
        QPointF(20, 20), actions, mime, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier
    )
    QApplication.sendEvent(window, drop)
    assert drop.isAccepted() and drop.dropAction() == Qt.DropAction.CopyAction
    second = window.tabs.currentWidget()
    _wait_page(qtbot, second, 0)
    window.tabs.setCurrentWidget(first)
    _wait_page(qtbot, first, 1)
    assert first.actual_zoom == pytest.approx(1.25)
    assert second.viewer.info.page_count == 1


def test_large_pdf_uses_lazy_thumbnails_and_cancelled_search_does_not_publish_results(
    window, qtbot, make_pdf
):
    tab = window.open_pdfs([make_pdf("muitas-paginas.pdf", count=320)])[0]
    _wait_page(qtbot, tab, 0)
    assert window.navigation_dock.model.count == 320
    qtbot.waitUntil(lambda: bool(window.navigation_dock.model.images), timeout=8000)
    assert len(window.navigation_dock.model.images) < 16
    tab.show_search()
    tab.query.setText("termo inexistente")
    qtbot.mouseClick(tab.search_button, Qt.MouseButton.LeftButton)
    job = tab.viewer.search_job
    qtbot.waitUntil(lambda: tab.viewer.search_page > 0, timeout=8000)
    qtbot.mouseClick(tab.stop_search, Qt.MouseButton.LeftButton)
    assert not tab.viewer.searching
    assert tab.search_status.text() == "Busca cancelada"
    assert window.jobs.status(job).state == TaskState.CANCELLED
    tab.page_number.setValue(310)
    _wait_page(qtbot, tab, 309)
    assert not tab.viewer.hits


def test_cancel_open_stops_process_and_keeps_window_responsive(window, qtbot, make_pdf):
    tab = window.open_pdfs([make_pdf()])[0]
    process = tab.viewer._worker.process
    process.setArguments(["-c", "import time; time.sleep(30)"])
    ticks = []
    timer = QTimer(window)
    timer.timeout.connect(lambda: ticks.append(1))
    timer.start(10)
    qtbot.waitUntil(
        lambda: process.state() == QProcess.ProcessState.Running and len(ticks) > 2, timeout=5000
    )
    job = tab.viewer.open_job
    window.jobs_dock.tree.setCurrentItem(window.jobs_dock.tree.topLevelItem(0))
    qtbot.mouseClick(window.jobs_dock.cancel_button, Qt.MouseButton.LeftButton)
    assert window.tabs.count() == 1
    assert process.state() == QProcess.ProcessState.NotRunning
    assert window.jobs.status(job).state == TaskState.CANCELLED
    timer.stop()


def test_reader_timeout_only_invalidates_its_own_document(window, qtbot, make_pdf):
    healthy = window.open_pdfs([make_pdf()])[0]
    _wait_page(qtbot, healthy, 0)
    stuck = window.open_pdfs([make_pdf("leitor-travado.pdf")])[0]
    stuck.viewer._worker.TIMEOUT_MS = 180
    stuck.viewer._worker.process.setArguments(["-c", "import time; time.sleep(30)"])
    qtbot.waitUntil(lambda: stuck.viewer.state == "error", timeout=5000)
    assert "prazo" in stuck.notice_text.text()
    assert window.jobs.status(stuck.viewer.open_job).state == TaskState.FAILED
    window.tabs.setCurrentWidget(healthy)
    healthy.page_number.setValue(2)
    _wait_page(qtbot, healthy, 1)


def test_pdf_actions_and_links_are_passive(window, qtbot, make_pdf, tmp_path, monkeypatch):
    urls = []
    monkeypatch.setattr(QDesktopServices, "openUrl", urls.append)
    path = make_pdf(active=True)
    tab = window.open_pdfs([path])[0]
    _wait_page(qtbot, tab, 0)
    point = tab.canvas.mapFromScene(QPointF(60 * tab.actual_zoom, 95 * tab.actual_zoom))
    qtbot.mouseClick(tab.canvas.viewport(), Qt.MouseButton.LeftButton, pos=point)
    assert not (tmp_path / "execucao-indevida.txt").exists()
    assert not urls
    assert window.tabs.currentWidget() is tab


def test_viewer_preferences_migrate_and_preserve_m0_shortcut(window):
    from PySide6.QtCore import QSettings

    window.save_settings()
    settings = QSettings(str(window.settings.path), QSettings.Format.IniFormat)
    settings.setValue("preferences/shortcuts", json.dumps({"home": "Ctrl+O"}))
    settings.remove("viewer")
    settings.sync()
    preferences = window.settings.load_preferences()
    assert preferences.shortcuts["home"] == "Ctrl+O"
    assert preferences.shortcuts["open"] == ""
    assert preferences.shortcuts["find"] == "Ctrl+F"
    assert preferences.pdf_cache_mib == 64 and preferences.pdf_parallelism == 2


def test_worker_process_never_loads_layout_runtime():
    code = (
        "import sys; from oldschoolpdf.infrastructure.pdf_engine import PdfEngine; "
        "PdfEngine(); assert 'onnxruntime' not in sys.modules"
    )
    result = subprocess.run([sys.executable, "-I", "-c", code], capture_output=True, timeout=12)
    assert result.returncode == 0, result.stderr
    assert result.stdout == result.stderr == b""
