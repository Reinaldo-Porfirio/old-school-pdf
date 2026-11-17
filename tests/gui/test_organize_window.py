"""Páginas, marcadores, campos, continuação de texto e Word pela interface."""

import pymupdf
import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QInputDialog, QMessageBox

from oldschoolpdf.app import create_window
from oldschoolpdf.domain.media import MediaOperation
from oldschoolpdf.ui.field_dialog import FieldDialog
from oldschoolpdf.ui.media_dialogs import BatchDialog
from oldschoolpdf.ui.outline_dialog import OutlineDialog
from oldschoolpdf.ui.page_dialogs import BlankPageDialog, CropDialog, ResizeDialog

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


def make_pdf(path, *, toc=True):
    with pymupdf.open() as pdf:
        for number in range(3):
            page = pdf.new_page(width=420, height=600)
            page.insert_text((40, 70), f"Capítulo {number + 1}", fontsize=20)
            for line in range(10):
                page.insert_text((40, 120 + line * 14), "Texto do corpo do documento.", fontsize=10)
        if toc:
            pdf.set_toc([[1, "Início", 1], [2, "Detalhe", 2], [1, "Fim", 3]])
        pdf.save(path)
    return path


def open_tab(window, qtbot, path):
    tab = window.open_pdfs([path])[0]
    qtbot.waitUntil(lambda: tab.canvas.has_page and tab.viewer.outline_loaded, timeout=10000)
    return tab


def wait_revision(qtbot, tab, revision):
    qtbot.waitUntil(
        lambda: tab.viewer.revision == revision and not tab.viewer.busy and tab.canvas.has_page,
        timeout=15000,
    )


def run_with(monkeypatch, window, configure):
    def run(dialog):
        return configure(dialog)

    monkeypatch.setattr(window.organize_tools, "run_dialog", run)


def test_blank_pages_crop_and_resize_from_the_menus(window, qtbot, tmp_path, monkeypatch):
    tab = open_tab(window, qtbot, make_pdf(tmp_path / "Livro ç.pdf"))
    for key in ("insert_blank", "crop_pages", "resize_pages", "outline"):
        assert window.actions[key].isEnabled(), key

    def blank(dialog):
        assert isinstance(dialog, BlankPageDialog)
        dialog.count.setValue(2)
        dialog.size.setCurrentIndex(dialog.size.findData("a4"))
        assert dialog.orientation.isEnabled()
        return QDialog.DialogCode.Accepted

    run_with(monkeypatch, window, blank)
    window.actions["insert_blank"].trigger()
    wait_revision(qtbot, tab, 1)
    assert tab.viewer.info.page_count == 5 and tab.viewer.page == 1
    assert "em branco" in window.statusBar().currentMessage()

    def crop(dialog):
        assert isinstance(dialog, CropDialog)
        dialog.pages.setText("1")
        assert dialog.padding.isEnabled() and not dialog.sides.isEnabled()
        return QDialog.DialogCode.Accepted

    run_with(monkeypatch, window, crop)
    window.actions["crop_pages"].trigger()
    wait_revision(qtbot, tab, 2)
    assert "cortada" in window.statusBar().currentMessage()

    def resize(dialog):
        assert isinstance(dialog, ResizeDialog)
        assert dialog.pages.text() == "1-5"
        dialog.pages.setText("1-x")
        assert not dialog.apply.isEnabled()
        dialog.pages.setText("1,4-5")
        dialog.size.setCurrentIndex(dialog.size.findData("letter"))
        return QDialog.DialogCode.Accepted

    run_with(monkeypatch, window, resize)
    window.actions["resize_pages"].trigger()
    wait_revision(qtbot, tab, 3)
    assert "ajustada" in window.statusBar().currentMessage()
    window.actions["undo"].trigger()
    wait_revision(qtbot, tab, 2)


def test_outline_panel_navigates_and_editor_applies_changes(window, qtbot, tmp_path, monkeypatch):
    tab = open_tab(window, qtbot, make_pdf(tmp_path / "Sumário.pdf"))
    tree = window.navigation_dock.outline_tree
    qtbot.waitUntil(lambda: tree.topLevelItemCount() == 2, timeout=5000)
    child = tree.topLevelItem(0).child(0)
    assert child.text(0) == "Detalhe"
    tree.itemClicked.emit(tree.topLevelItem(1), 0)
    qtbot.waitUntil(lambda: tab.viewer.page == 2, timeout=5000)

    def edit(dialog):
        assert isinstance(dialog, OutlineDialog)
        assert dialog.list.count() == 3 and not dialog.apply.isEnabled()
        dialog.list.setCurrentRow(2)
        dialog.title.setText("Conclusão")
        dialog.title.textEdited.emit("Conclusão")
        dialog.buttons["indent"].click()
        assert dialog.entries[2]["level"] == 2
        dialog.buttons["add"].click()
        assert dialog.list.count() == 4 and dialog.entries[3]["source"] is None
        dialog.page.setValue(1)
        monkeypatch.setattr(dialog, "ask_merge", lambda count: "append")
        with qtbot.waitSignal(tab.viewer.outline_suggested, timeout=10000):
            dialog.buttons["suggest"].click()
        # "Acrescentar ao final" mantém os quatro e adiciona os três capítulos.
        assert dialog.list.count() == 7
        assert dialog.apply.isEnabled()
        return QDialog.DialogCode.Accepted

    run_with(monkeypatch, window, edit)
    window.actions["outline"].trigger()
    wait_revision(qtbot, tab, 1)
    qtbot.waitUntil(lambda: tab.viewer.outline_loaded, timeout=5000)
    titles = [entry.title for entry in tab.viewer.outline]
    assert titles[:3] == ["Início", "Detalhe", "Conclusão"]
    assert len(titles) == 7 and titles[-1] == "Capítulo 3"
    assert "Marcadores atualizados" in window.statusBar().currentMessage()


def test_pdf_without_outline_shows_hint(window, qtbot, tmp_path):
    open_tab(window, qtbot, make_pdf(tmp_path / "Sem índice.pdf", toc=False))
    assert "não tem marcadores" in window.navigation_dock.outline_state.text()


def test_field_is_drawn_created_filled_and_removed(window, qtbot, tmp_path, monkeypatch):
    tab = open_tab(window, qtbot, make_pdf(tmp_path / "Ficha.pdf"))
    assert window.actions["add_field"].isEnabled()
    assert not window.actions["remove_field"].isEnabled()

    def field(dialog):
        assert isinstance(dialog, FieldDialog)
        dialog.kind.setCurrentIndex(dialog.kind.findData("choice"))
        assert not dialog.create.isEnabled()
        dialog.choices.setPlainText("Sim\nNão")
        dialog.name.setText("resposta")
        assert dialog.create.isEnabled(), dialog.status.text()
        return QDialog.DialogCode.Accepted

    run_with(monkeypatch, window, field)
    window.actions["add_field"].trigger()
    assert tab.placement == "field" and tab.placement_note.isVisible()
    tab.canvas.region_chosen.emit((0.1, 0.5, 0.5, 0.56))
    wait_revision(qtbot, tab, 1)
    qtbot.waitUntil(lambda: any(f.kind == "choice" for f in tab.viewer.fields), timeout=5000)
    assert window.actions["forms"].isEnabled() and window.actions["remove_field"].isEnabled()
    monkeypatch.setattr(QInputDialog, "getItem", lambda *a, **k: (a[3][0], True))
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)
    window.actions["remove_field"].trigger()
    wait_revision(qtbot, tab, 2)
    qtbot.waitUntil(lambda: not tab.viewer.fields, timeout=5000)


def test_text_editor_offers_continuation_on_new_page(window, qtbot, tmp_path, monkeypatch):
    open_tab(window, qtbot, make_pdf(tmp_path / "Texto.pdf"))
    monkeypatch.setattr(window.text_tools, "run_dialog", lambda dialog: dialog.show())
    window.actions["edit_text"].trigger()
    dialog = window.text_tools.dialog
    qtbot.waitUntil(lambda: not dialog.working, timeout=20000)
    assert dialog.overflow.isEnabled() and dialog.options()["overflow"] == "none"
    dialog.overflow.setChecked(True)
    assert dialog.options()["overflow"] == "new_page"
    dialog.done(0)


def test_preview_navigates_continuation_pages_and_shows_failures(
    window, qtbot, tmp_path, monkeypatch
):
    open_tab(window, qtbot, make_pdf(tmp_path / "Prévia.pdf"))
    monkeypatch.setattr(window.text_tools, "run_dialog", lambda dialog: dialog.show())
    window.actions["edit_text"].trigger()
    dialog = window.text_tools.dialog
    qtbot.waitUntil(lambda: not dialog.working, timeout=20000)
    assert "Gerar prévia" in dialog.preview.message
    assert not dialog.preview_next.isVisible()
    index = next(i for i, block in enumerate(dialog.blocks) if "Texto do corpo" in block.text)
    dialog.list.setCurrentRow(index)
    dialog.editor.setPlainText("Uma frase bem comprida para ocupar a página. " * 60)
    assert "desatualizada" in dialog.preview.message
    dialog.overflow.setChecked(True)
    dialog.preview_button.click()
    qtbot.waitUntil(lambda: not dialog.working and dialog.preview_pages > 0, timeout=30000)
    assert dialog.pages.currentIndex() == 1 and dialog.preview_next.isEnabled()
    assert not dialog.preview_previous.isEnabled() and "1 de" in dialog.preview_label.text()
    dialog.preview_next.click()
    qtbot.waitUntil(lambda: not dialog.working and dialog.preview_view == 1, timeout=30000)
    assert "continuação" in dialog.preview_label.text() and dialog.preview_previous.isEnabled()
    # Sem a continuação, o texto não cabe: o motivo aparece na própria área da prévia.
    dialog.overflow.setChecked(False)
    dialog.shrink.setCurrentIndex(dialog.shrink.findData("none"))
    dialog.preview_button.click()
    qtbot.waitUntil(
        lambda: not dialog.working and "não cabe" in dialog.preview.message, timeout=30000
    )
    assert dialog.pages.currentIndex() == 1 and not dialog.preview_next.isVisible()
    dialog.edits.clear()
    dialog.done(0)


def test_batch_dialog_offers_word_with_page_ranges(qtbot, tmp_path):
    source = make_pdf(tmp_path / "Para Word.pdf")
    dialog = BatchDialog(MediaOperation.DOCX, "", (), source, None, None)
    qtbot.addWidget(dialog)
    assert dialog.mode == MediaOperation.DOCX
    assert dialog.form.isRowVisible(dialog.ranges)
    assert "Word" in dialog.note.text() or "LibreOffice" in dialog.note.text()
    assert dialog.files.count() == 1
    item = dialog.files.item(0)
    assert item.data(Qt.ItemDataRole.UserRole).endswith("Para Word.pdf")
