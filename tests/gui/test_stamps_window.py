"""Numeração, marca d'água, localizar e substituir e desenho pela interface."""

import pymupdf
import pytest
from PySide6.QtCore import QPointF, Qt
from PySide6.QtWidgets import QDialog

from oldschoolpdf.app import create_window
from oldschoolpdf.domain.viewer import rotate_rect
from oldschoolpdf.ui.stamp_dialogs import (
    FindReplaceDialog,
    HeaderFooterDialog,
    RemoveStampsDialog,
    WatermarkDialog,
)

pytestmark = pytest.mark.qt_log_ignore("does not support propagateSizeHints")


@pytest.fixture
def window(qtbot, tmp_path):
    def discard(window):
        for tab in tuple(window._pdf_tabs()):
            tab.viewer.session.dirty = False
            tab.viewer.busy = ""
        window.pdf_workspace.close()

    window = create_window(tmp_path / "settings.ini")
    qtbot.addWidget(window, before_close_func=discard)
    window.show()
    qtbot.waitUntil(window.isVisible)
    return window


def make_pdf(path, *, rotation=0):
    with pymupdf.open() as pdf:
        for number in range(3):
            page = pdf.new_page(width=420, height=600)
            page.insert_text((40, 120), f"Cláusula {number + 1} do fornecedor.", fontsize=12)
            page.insert_text((40, 160), "Texto do corpo do documento.", fontsize=11)
            page.set_rotation(rotation)
        pdf.save(path)
    return path


def open_tab(window, qtbot, path):
    tab = window.open_pdfs([path])[0]
    qtbot.waitUntil(lambda: tab.canvas.has_page and tab.viewer.outline_loaded, timeout=10000)
    return tab


def wait_revision(qtbot, tab, revision):
    qtbot.waitUntil(
        lambda: tab.viewer.revision == revision and not tab.viewer.busy and tab.canvas.has_page,
        timeout=20000,
    )


def run_with(monkeypatch, window, configure):
    monkeypatch.setattr(window.stamp_tools, "run_dialog", configure)


def page_text(tab):
    with pymupdf.open(tab.viewer.session.working_copy) as doc:
        return [" ".join(page.get_text().split()) for page in doc]


def canvas_position(tab, x, y):
    x, y, _, _ = rotate_rect((x, y, x, y), tab.viewer.rotation)
    return tab.canvas.mapFromScene(
        QPointF(x * tab.canvas.bounds.width(), y * tab.canvas.bounds.height())
    )


def stroke(tab, qtbot, points):
    qtbot.waitUntil(lambda: not tab.render_timer.isActive(), timeout=5000)
    viewport = tab.canvas.viewport()
    positions = [canvas_position(tab, *point) for point in points]
    qtbot.mousePress(viewport, Qt.MouseButton.LeftButton, pos=positions[0])
    for position in positions[1:]:
        qtbot.mouseMove(viewport, pos=position)
    qtbot.mouseRelease(viewport, Qt.MouseButton.LeftButton, pos=positions[-1])


def test_numbering_watermark_and_removal_from_the_menus(window, qtbot, tmp_path, monkeypatch):
    tab = open_tab(window, qtbot, make_pdf(tmp_path / "Contrato ç.pdf"))
    for key in ("header_footer", "watermark", "remove_stamps", "find_replace"):
        assert window.actions[key].isEnabled(), key
    warnings = []
    monkeypatch.setattr(window.stamp_tools, "warn", lambda title, text: warnings.append(text))

    def numbering(dialog):
        assert isinstance(dialog, HeaderFooterDialog)
        footer = dialog.slots["footer_center"]
        assert footer.isReadOnly() and footer.text() == "Página [página] de [total]"
        dialog.number_slot.setCurrentIndex(dialog.number_slot.findData("footer_right"))
        assert not footer.isReadOnly() and dialog.slots["footer_right"].isReadOnly()
        dialog.slots["header_left"].setFocus()
        dialog._focused = dialog.slots["header_left"]
        dialog.slots["header_left"].setText("Processo — ")
        dialog._insert("arquivo")
        assert dialog.slots["header_left"].text() == "Processo — [arquivo]"
        assert dialog.preview_page.texts["header_left"] == "Processo — Contrato ç.pdf"
        assert dialog.preview_page.texts["footer_right"] == "Página 1 de 3"
        dialog.pages.setText("2-3")
        dialog.start.setValue(1)
        assert dialog.apply.isEnabled()
        return QDialog.DialogCode.Accepted

    run_with(monkeypatch, window, numbering)
    window.actions["header_footer"].trigger()
    wait_revision(qtbot, tab, 1)
    texts = page_text(tab)
    assert "Página" not in texts[0]
    assert "Página 1 de 2" in texts[1] and "Página 2 de 2" in texts[2]
    assert "Processo — Contrato ç.pdf" in texts[1]
    assert "aplicados em 2 página(s)" in window.statusBar().currentMessage()
    assert not warnings

    def mark(dialog):
        assert isinstance(dialog, WatermarkDialog)
        assert dialog.text.currentText() == "CONFIDENCIAL"
        dialog.text.setEditText("CÓPIA")
        dialog.angle.setCurrentIndex(dialog.angle.findData("horizontal"))
        assert dialog.preview_page.watermark["text"] == "CÓPIA"
        dialog.image_mode.setChecked(True)
        assert not dialog.apply.isEnabled() and dialog.image_group.isVisibleTo(dialog)
        dialog.text_mode.setChecked(True)
        assert dialog.apply.isEnabled()
        return QDialog.DialogCode.Accepted

    run_with(monkeypatch, window, mark)
    window.actions["watermark"].trigger()
    wait_revision(qtbot, tab, 2)
    # A marca é desenho: o texto das páginas não muda.
    assert page_text(tab) == texts
    with pymupdf.open(tab.viewer.session.working_copy) as doc:
        assert all(page.get_drawings() for page in doc)

    def remove(dialog):
        assert isinstance(dialog, RemoveStampsDialog)
        dialog.watermark.setChecked(False)
        dialog.header.setChecked(False)
        assert not dialog.apply.isEnabled()
        dialog.header.setChecked(True)
        return QDialog.DialogCode.Accepted

    run_with(monkeypatch, window, remove)
    window.actions["remove_stamps"].trigger()
    wait_revision(qtbot, tab, 3)
    assert not any("Página" in text for text in page_text(tab))
    assert "cabeçalho e rodapé de 2" in window.statusBar().currentMessage()
    window.actions["undo"].trigger()
    wait_revision(qtbot, tab, 2)
    assert "Página 1 de 2" in page_text(tab)[1]


def test_find_and_replace_lists_and_replaces_marked_matches(window, qtbot, tmp_path, monkeypatch):
    tab = open_tab(window, qtbot, make_pdf(tmp_path / "Busca.pdf"))
    tab.show_search()
    tab.query.setText("fornecedor")

    def replace(dialog):
        assert isinstance(dialog, FindReplaceDialog)
        assert dialog.query.text() == "fornecedor" and not dialog.apply.isEnabled()
        dialog.replacement.setText("prestador")
        dialog.find()
        qtbot.waitUntil(lambda: dialog.results.topLevelItemCount() == 3, timeout=10000)
        assert "3 ocorrência(s) em 3 página(s)" in dialog.summary.text()
        assert dialog.apply.isEnabled()
        dialog.results.topLevelItem(1).setCheckState(0, Qt.CheckState.Unchecked)
        assert len(dialog.values()["items"]) == 2
        dialog.word.setChecked(True)
        assert not dialog.apply.isEnabled() and "mudou" in dialog.summary.text()
        dialog.word.setChecked(False)
        assert dialog.apply.isEnabled()
        return QDialog.DialogCode.Accepted

    run_with(monkeypatch, window, replace)
    window.actions["find_replace"].trigger()
    wait_revision(qtbot, tab, 1)
    texts = page_text(tab)
    assert "prestador" in texts[0] and "fornecedor" in texts[1] and "prestador" in texts[2]
    assert "2 ocorrência(s) substituída(s)" in window.statusBar().currentMessage()


@pytest.mark.parametrize("rotation", [0, 90])
def test_pen_arrow_and_strikeout_are_drawn_with_the_mouse(window, qtbot, tmp_path, rotation):
    tab = open_tab(window, qtbot, make_pdf(tmp_path / "Desenho.pdf", rotation=rotation))
    window.actions["ink"].trigger()
    assert tab.placement == "ink" and tab.drawing_bar.isVisible()
    assert tab.finish_button.isVisible()
    tab.pen_color.setCurrentIndex(tab.pen_color.findData("red"))
    assert window.pen["color"] == "red"
    stroke(tab, qtbot, [(0.2, 0.5), (0.3, 0.55), (0.4, 0.5)])
    stroke(tab, qtbot, [(0.2, 0.62), (0.4, 0.62)])
    stroke(tab, qtbot, [(0.6, 0.62), (0.7, 0.7)])
    tab.undo_stroke.click()
    assert tab.canvas.stroke_count == 2
    qtbot.keyClick(tab.canvas, Qt.Key.Key_Return)
    wait_revision(qtbot, tab, 1)
    assert not tab.drawing_bar.isVisible() and not tab.canvas.stroke_mode
    qtbot.waitUntil(lambda: bool(tab.viewer.annotations), timeout=5000)
    ink = tab.viewer.annotations[0]
    assert ink.kind == "ink" and abs(ink.region[0] - 0.2) < 0.03 and ink.region[2] < 0.45

    window.actions["arrow"].trigger()
    assert tab.drawing_bar.isVisible() and not tab.finish_button.isVisible()
    stroke(tab, qtbot, [(0.1, 0.9), (0.5, 0.75)])
    wait_revision(qtbot, tab, 2)
    qtbot.waitUntil(lambda: len(tab.viewer.annotations) == 2, timeout=5000)
    arrow = next(item for item in tab.viewer.annotations if item.kind == "arrow")
    assert arrow.region[0] < 0.12 and arrow.region[3] > 0.88

    with pymupdf.open(tab.viewer.session.working_copy) as doc:
        page = doc[0]
        line = (page.search_for("Cláusula")[0] + (-3, -3, 3, 3)) * page.rotation_matrix
        area = (
            line.x0 / page.rect.width,
            line.y0 / page.rect.height,
            line.x1 / page.rect.width,
            line.y1 / page.rect.height,
        )
    window.actions["strikeout"].trigger()
    tab.canvas.region_chosen.emit(area)
    wait_revision(qtbot, tab, 3)
    qtbot.waitUntil(lambda: len(tab.viewer.annotations) == 3, timeout=5000)
    assert {item.kind for item in tab.viewer.annotations} == {"ink", "arrow", "strikeout"}


def test_drawing_is_cancelled_with_escape(window, qtbot, tmp_path):
    tab = open_tab(window, qtbot, make_pdf(tmp_path / "Cancela.pdf"))
    window.actions["ink"].trigger()
    stroke(tab, qtbot, [(0.2, 0.5), (0.4, 0.5)])
    assert tab.canvas.stroke_count == 1
    qtbot.keyClick(tab.canvas, Qt.Key.Key_Escape)
    assert not tab.placement and not tab.canvas.stroke_count and not tab.drawing_bar.isVisible()
    tab.finish_drawing()
    assert tab.viewer.revision == 0
