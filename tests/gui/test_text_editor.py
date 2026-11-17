import pymupdf
import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QMessageBox

from oldschoolpdf.app import create_window
from oldschoolpdf.ui.text_edit_dialog import TextEditDialog

# O diálogo fica visível nos testes; o plugin offscreen do Qt não repassa limites de tamanho.
pytestmark = pytest.mark.qt_log_ignore("does not support propagateSizeHints")


@pytest.fixture
def window(qtbot, tmp_path, monkeypatch):
    def discard(window):
        if window.text_tools.dialog is not None:
            window.text_tools.dialog.edits.clear()
            window.text_tools.dialog.done(0)
        for tab in tuple(window._pdf_tabs()):
            tab.viewer.session.dirty = False
            tab.viewer.busy = ""
        window.pdf_workspace.close()

    window = create_window(tmp_path / "settings.ini")
    qtbot.addWidget(window, before_close_func=discard)
    monkeypatch.setattr(window.text_tools, "run_dialog", lambda dialog: dialog.show())
    window.show()
    qtbot.waitUntil(window.isVisible)
    return window


def make_pdf(path, *, signed=False, permissions=None, scanned=False):
    with pymupdf.open() as pdf:
        page = pdf.new_page(width=420, height=600)
        if scanned:
            pixmap = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 60, 60), False)
            pixmap.clear_with(180)
            page.insert_image(pymupdf.Rect(40, 40, 380, 380), pixmap=pixmap)
        else:
            page.insert_text((40, 70), "Contrato de prestação", fontsize=16)
            page.insert_text((40, 120), "Valor total: R$ 100,00", fontsize=12)
            page.insert_text((40, 300), "Assinaturas ao final", fontsize=12)
        if signed:
            pdf.xref_set_key(pdf.pdf_catalog(), "AcroForm/SigFlags", "3")
        if permissions is None:
            pdf.save(path)
        else:
            pdf.save(
                path,
                encryption=pymupdf.PDF_ENCRYPT_AES_256,
                owner_pw="dono",
                user_pw="",
                permissions=permissions,
            )
    return path


def open_editor(window, qtbot, path):
    tab = window.open_pdfs([path])[0]
    qtbot.waitUntil(lambda: tab.canvas.has_page, timeout=10000)
    qtbot.waitUntil(lambda: window.actions["edit_text"].isEnabled(), timeout=5000)
    window.actions["edit_text"].trigger()
    dialog = window.text_tools.dialog
    assert isinstance(dialog, TextEditDialog)
    qtbot.waitUntil(lambda: not dialog.working, timeout=20000)
    return tab, dialog


def choose(dialog, fragment):
    index = next(i for i, block in enumerate(dialog.blocks) if fragment in block.text)
    dialog.list.setCurrentRow(index)
    return index


def replace_all(dialog, text):
    cursor = dialog.editor.textCursor()
    cursor.select(QTextCursor.SelectionType.Document)
    cursor.insertText(text)


def working_text(tab):
    with pymupdf.open(tab.viewer.session.working_copy) as pdf:
        return " ".join(pdf[0].get_text().split())


def test_edit_preview_apply_and_undo(window, qtbot, tmp_path):
    source = make_pdf(tmp_path / "contrato.pdf")
    tab, dialog = open_editor(window, qtbot, source)
    assert len(dialog.blocks) == 3 and all(block.editable for block in dialog.blocks)
    assert "Fonte no PDF" in dialog.details.text()
    choose(dialog, "Valor total")
    replace_all(dialog, "Valor total: R$ 150,00")
    assert "1 bloco(s) alterado(s)" in dialog.counter.text()
    assert dialog.apply_button.isEnabled()

    dialog.preview_button.click()
    qtbot.waitUntil(lambda: dialog.preview.pixmap is not None and not dialog.working, timeout=20000)
    assert dialog.pages.currentIndex() == 1 and "verificada" in dialog.status.text()
    assert dialog.preview.pixmap is not None

    dialog.apply_button.click()
    qtbot.waitUntil(lambda: window.text_tools.dialog is None, timeout=20000)
    assert tab.viewer.revision == 1 and tab.viewer.can_undo
    assert "Texto alterado" in window.statusBar().currentMessage()
    text = working_text(tab)
    assert "R$ 150,00" in text and "100,00" not in text and "Assinaturas ao final" in text
    with pymupdf.open(source) as original:
        assert "100,00" in original[0].get_text()

    window.actions["undo"].trigger()
    qtbot.waitUntil(lambda: tab.viewer.revision == 0 and not tab.viewer.busy, timeout=10000)


def test_bold_toggle_reaches_the_pdf(window, qtbot, tmp_path):
    tab, dialog = open_editor(window, qtbot, make_pdf(tmp_path / "negrito.pdf"))
    choose(dialog, "Assinaturas")
    cursor = dialog.editor.textCursor()
    cursor.movePosition(QTextCursor.MoveOperation.Start)
    cursor.movePosition(QTextCursor.MoveOperation.EndOfWord, QTextCursor.MoveMode.KeepAnchor)
    dialog.editor.setTextCursor(cursor)
    dialog.bold.trigger()
    block = dialog.blocks[dialog.current]
    runs = dialog.edits[block.key]
    assert runs[0].text == "Assinaturas" and runs[0].bold and not runs[-1].bold
    dialog.apply_button.click()
    qtbot.waitUntil(lambda: window.text_tools.dialog is None, timeout=20000)
    with pymupdf.open(tab.viewer.session.working_copy) as pdf:
        spans = [
            span
            for block in pdf[0].get_text("dict")["blocks"]
            for line in block["lines"]
            for span in line["spans"]
            if "Assinaturas" in span["text"]
        ]
    assert spans and spans[0]["flags"] & pymupdf.TEXT_FONT_BOLD


def test_clicking_the_page_selects_a_block(window, qtbot, tmp_path):
    _, dialog = open_editor(window, qtbot, make_pdf(tmp_path / "clique.pdf"))
    index = next(i for i, block in enumerate(dialog.blocks) if "Assinaturas" in block.text)
    preview = dialog.original
    box = preview._box(preview._target(), dialog.blocks[index].region)
    qtbot.mouseClick(preview, Qt.MouseButton.LeftButton, pos=box.center().toPoint())
    assert dialog.current == index and preview.selected == index
    assert dialog.list.currentRow() == index


def test_text_that_does_not_fit_keeps_dialog_open(window, qtbot, tmp_path):
    tab, dialog = open_editor(window, qtbot, make_pdf(tmp_path / "longo.pdf"))
    choose(dialog, "Contrato")
    replace_all(dialog, "Contrato de prestação de serviços técnicos especializados " * 2)
    dialog.shrink.setCurrentIndex(0)
    dialog.apply_button.click()
    qtbot.waitUntil(lambda: not dialog.working, timeout=20000)
    assert window.text_tools.dialog is dialog
    assert "não cabe" in dialog.status.text()
    assert tab.viewer.revision == 0 and not tab.viewer.busy
    dialog.expand.setChecked(True)
    dialog.shrink.setCurrentIndex(2)
    replace_all(dialog, "Contrato de prestação de serviços técnicos")
    dialog.apply_button.click()
    qtbot.waitUntil(lambda: window.text_tools.dialog is None, timeout=20000)
    assert "serviços técnicos" in working_text(tab)


def test_signed_pdf_asks_before_applying(window, qtbot, tmp_path, monkeypatch):
    tab, dialog = open_editor(window, qtbot, make_pdf(tmp_path / "assinado.pdf", signed=True))
    answers = [QMessageBox.StandardButton.Cancel, QMessageBox.StandardButton.Ok]
    monkeypatch.setattr(QMessageBox, "warning", lambda *args: answers.pop(0))
    choose(dialog, "Valor")
    replace_all(dialog, "Valor total: R$ 1,00")
    dialog.apply_button.click()
    assert tab.viewer.revision == 0 and window.text_tools.dialog is dialog
    dialog.apply_button.click()
    qtbot.waitUntil(lambda: window.text_tools.dialog is None, timeout=20000)
    assert tab.viewer.revision == 1


def test_closing_with_pending_edits_asks_to_discard(window, qtbot, tmp_path, monkeypatch):
    _, dialog = open_editor(window, qtbot, make_pdf(tmp_path / "pendente.pdf"))
    choose(dialog, "Valor")
    replace_all(dialog, "Outro valor")
    answers = [QMessageBox.StandardButton.Cancel, QMessageBox.StandardButton.Discard]
    monkeypatch.setattr(QMessageBox, "question", lambda *args: answers.pop(0))
    dialog.reject()
    assert window.text_tools.dialog is dialog
    dialog.reject()
    qtbot.waitUntil(lambda: window.text_tools.dialog is None)


def test_restore_block_and_unchanged_text_count_as_no_edit(window, qtbot, tmp_path):
    _, dialog = open_editor(window, qtbot, make_pdf(tmp_path / "restaurar.pdf"))
    choose(dialog, "Valor")
    replace_all(dialog, "Mudou")
    assert dialog.edits
    dialog.restore.trigger()
    assert not dialog.edits and not dialog.apply_button.isEnabled()
    replace_all(dialog, "Valor total: R$ 100,00")
    assert not dialog.edits


def test_scanned_page_and_locked_pdf_explain_the_limits(window, qtbot, tmp_path):
    _, dialog = open_editor(window, qtbot, make_pdf(tmp_path / "digitalizado.pdf", scanned=True))
    assert not dialog.blocks and "OCR" in dialog.status.text()
    dialog.done(0)
    qtbot.waitUntil(lambda: window.text_tools.dialog is None)

    allowed = pymupdf.PDF_PERM_PRINT | pymupdf.PDF_PERM_COPY | pymupdf.PDF_PERM_ACCESSIBILITY
    tab = window.open_pdfs([make_pdf(tmp_path / "travado.pdf", permissions=allowed)])[0]
    qtbot.waitUntil(lambda: tab.canvas.has_page, timeout=10000)
    assert not tab.viewer.info.can_modify
    assert not window.actions["edit_text"].isEnabled()
    assert "não permitem alterar" in window.actions["edit_text"].toolTip()
