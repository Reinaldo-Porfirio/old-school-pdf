import os
import sys
from pathlib import Path

import pymupdf
import pytest
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QDialog, QFileDialog, QInputDialog, QMessageBox

from docforge.app import create_window
from docforge.domain.tasks import TaskState
from docforge.domain.viewer import rotate_rect
from docforge.infrastructure import local_files
from docforge.ui.edit_dialogs import FormDialog, MergeDialog, RangeDialog


@pytest.fixture
def editor(qtbot, tmp_path):
    def discard_after_test(window):
        # Evita diálogos pendentes na desmontagem, inclusive quando uma asserção falha.
        for tab in tuple(window._pdf_tabs()):
            tab.viewer.session.dirty = False
            tab.viewer.busy = ""
        window.pdf_workspace.close()
        if window.document_tools.merge_task:
            window.document_tools.cancel_merge(window.document_tools.merge_task.task_id)

    window = create_window(tmp_path / "settings.ini")
    qtbot.addWidget(window, before_close_func=discard_after_test)
    window.show()
    qtbot.waitUntil(window.isVisible)
    return window


@pytest.fixture
def pdf_fixture(tmp_path):
    def create(name="Caderno ç.pdf", count=3, *, rotation=0, forms=False, signed=False):
        path = tmp_path / name
        with pymupdf.open() as pdf:
            for number in range(1, count + 1):
                page = pdf.new_page(width=420, height=600)
                page.insert_text((34, 66), f"{path.stem} / {number:02}", fontsize=17)
                page.insert_text((34, 105), "Texto verificável", fontsize=16)
            page = pdf[0]
            if forms:
                for field_type, name, value, x in (
                    (pymupdf.PDF_WIDGET_TYPE_TEXT, "Nome", "Antes", 34),
                    (pymupdf.PDF_WIDGET_TYPE_CHECKBOX, "Conferido", "Off", 200),
                    (pymupdf.PDF_WIDGET_TYPE_COMBOBOX, "Revisão", "Aberta", 250),
                    (pymupdf.PDF_WIDGET_TYPE_TEXT, "Campo protegido", "Fixo", 34),
                ):
                    widget = pymupdf.Widget()
                    widget.field_type = field_type
                    widget.field_name = name
                    widget.field_value = value
                    width = 20 if name == "Conferido" else 110
                    y = 490 if name == "Campo protegido" else 450
                    widget.rect = pymupdf.Rect(x, y, x + width, y + 22)
                    if name == "Revisão":
                        widget.choice_values = ["Aberta", "Fechada"]
                    if name == "Campo protegido":
                        widget.script = "app.alert('não executar')"
                    page.add_widget(widget)
            if signed:
                pdf.xref_set_key(pdf.pdf_catalog(), "AcroForm/SigFlags", "3")
            page.set_rotation(rotation)
            pdf.save(path)
        return path

    return create


def open_tab(editor, qtbot, source):
    tab = editor.open_pdfs([source])[0]
    qtbot.waitUntil(lambda: tab.canvas.has_page, timeout=10000)
    return tab


def ready_revision(qtbot, tab, revision):
    qtbot.waitUntil(
        lambda: (
            tab.viewer.state == "ready"
            and tab.viewer.revision == revision
            and not tab.viewer.busy
            and tab.canvas.has_page
        ),
        timeout=10000,
    )


def choose_output(monkeypatch, path):
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *args, **kwargs: (str(path), ""))


def choose_ranges(monkeypatch, value, *, angle=90):
    def exec_dialog(dialog):
        dialog.pages.setText(value)
        dialog.angle.setCurrentIndex(dialog.angle.findData(angle))
        assert dialog.apply.isEnabled(), dialog.preview.text()
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(RangeDialog, "exec", exec_dialog)


def export_action(editor, qtbot, tab, key, *, successful=True):
    with qtbot.waitSignal(tab.viewer.export_completed, timeout=12000) as result:
        editor.actions[key].trigger()
    assert result.args[0] is successful, result.args[1]
    return result.args[1]


def pdf_pages(path):
    with pymupdf.open(path) as pdf:
        assert not pdf.is_repaired
        return [(page.get_text().splitlines()[0], page.rotation) for page in pdf]


def test_t06_merge_two_pdfs_with_preview_and_reopen(
    editor, qtbot, pdf_fixture, monkeypatch, tmp_path
):
    first = pdf_fixture("Entrada A.pdf", 3)
    second = pdf_fixture("Entrada B.pdf", 5, forms=True)
    originals = first.read_bytes(), second.read_bytes()
    destination = tmp_path / "Mesclado.pdf"
    choose_output(monkeypatch, destination)

    def exec_dialog(dialog):
        dialog.add_paths([second, first])
        qtbot.waitUntil(dialog.submit.isEnabled, timeout=10000)
        assert "8 página(s)" in dialog.status.text()
        dialog.up.click()
        assert [row["pages"] for row in dialog.records()] == [3, 5]
        dialog.accept()
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(MergeDialog, "exec", exec_dialog)
    editor.actions["merge"].trigger()
    qtbot.waitUntil(
        lambda: destination.exists() and editor.document_tools.merge_task is None, timeout=12000
    )
    assert pdf_pages(destination) == pdf_pages(first) + pdf_pages(second)
    with pymupdf.open(destination) as pdf:
        assert [field.field_name for field in pdf[3].widgets()] == [
            "Nome",
            "Conferido",
            "Revisão",
            "Campo protegido",
        ]
    tab = editor.tabs.currentWidget()
    qtbot.waitUntil(lambda: tab.canvas.has_page, timeout=10000)
    assert tab.viewer.session.source_path == destination
    assert (first.read_bytes(), second.read_bytes()) == originals
    assert not list(tmp_path.glob("*.part.pdf"))


def test_t07_split_and_extract_in_explicit_order(editor, qtbot, pdf_fixture, monkeypatch, tmp_path):
    source = pdf_fixture(count=8, forms=True)
    with pymupdf.open(source) as pdf:
        widget = pymupdf.Widget()
        widget.field_type = pymupdf.PDF_WIDGET_TYPE_TEXT
        widget.field_name = "Campo da página 3"
        widget.field_value = "Retido"
        widget.rect = pymupdf.Rect(34, 390, 204, 414)
        pdf[2].add_widget(widget)
        pdf.saveIncr()
    original = source.read_bytes()
    tab = open_tab(editor, qtbot, source)
    choose_ranges(monkeypatch, "2–4")
    selection = tmp_path / "Parte.pdf"
    choose_output(monkeypatch, selection)
    export_action(editor, qtbot, tab, "split")
    pages = pdf_pages(source)
    assert pdf_pages(selection) == pages[1:4]
    with pymupdf.open(selection) as pdf:
        assert pdf.is_form_pdf == 1
        assert [(field.field_name, field.field_value) for field in pdf[1].widgets()] == [
            ("Campo da página 3", "Retido"),
        ]
    choose_ranges(monkeypatch, "6-8,2-4")
    parts = tmp_path / "Volumes.pdf"
    choose_output(monkeypatch, parts)
    export_action(editor, qtbot, tab, "split")
    assert pdf_pages(tmp_path / "Volumes-01.pdf") == pages[5:8]
    assert pdf_pages(tmp_path / "Volumes-02.pdf") == pages[1:4]
    with pymupdf.open(tmp_path / "Volumes-01.pdf") as pdf:
        assert not pdf.is_form_pdf
    extract = tmp_path / "Extrato.pdf"
    choose_output(monkeypatch, extract)
    export_action(editor, qtbot, tab, "extract")
    assert pdf_pages(extract) == pages[5:8] + pages[1:4]
    assert source.read_bytes() == original
    assert not tab.viewer.session.dirty
    assert not list(tmp_path.glob("*.part.pdf"))


def test_t08_thumbnail_reorder_rotate_delete_undo_and_save(
    editor, qtbot, pdf_fixture, monkeypatch, tmp_path
):
    source = pdf_fixture(count=5, forms=True)
    original = source.read_bytes()
    pages = pdf_pages(source)
    tab = open_tab(editor, qtbot, source)
    model = editor.navigation_dock.model
    assert model.dropMimeData(
        model.mimeData([model.index(3)]), Qt.DropAction.MoveAction, 0, 0, model.index(-1)
    )
    ready_revision(qtbot, tab, 1)
    assert tab.viewer.page == 0
    assert editor.tabs.tabText(editor.tabs.currentIndex()).endswith(" *")
    choose_ranges(monkeypatch, "1", angle=270)
    editor.actions["rotate_pages"].trigger()
    ready_revision(qtbot, tab, 2)
    assert tab.page_properties[2] == 270
    choose_ranges(monkeypatch, "3")
    editor.actions["delete_pages"].trigger()
    ready_revision(qtbot, tab, 3)
    assert tab.viewer.info.page_count == 4
    editor.actions["undo"].trigger()
    ready_revision(qtbot, tab, 2)
    assert tab.viewer.info.page_count == 5
    editor.actions["redo"].trigger()
    ready_revision(qtbot, tab, 3)
    assert tab.viewer.info.page_count == 4
    target = tmp_path / "Organizado.pdf"
    choose_output(monkeypatch, target)
    export_action(editor, qtbot, tab, "save_as")
    assert pdf_pages(target) == [(pages[3][0], 270), pages[0], pages[2], pages[4]]
    with pymupdf.open(target) as pdf:
        assert pdf.is_form_pdf == 4
        assert [field.field_value for field in pdf[1].widgets()] == [
            "Antes",
            "Off",
            "Aberta",
            "Fixo",
        ]
    assert not tab.viewer.session.dirty
    editor.actions["undo"].trigger()
    ready_revision(qtbot, tab, 2)
    assert tab.viewer.session.dirty
    editor.actions["redo"].trigger()
    ready_revision(qtbot, tab, 3)
    assert not tab.viewer.session.dirty
    assert source.read_bytes() == original


def test_t09_cancel_running_export_from_queue(editor, qtbot, pdf_fixture, monkeypatch, tmp_path):
    source = pdf_fixture(count=12)
    original = source.read_bytes()
    tab = open_tab(editor, qtbot, source)
    choose_ranges(monkeypatch, "1-6", angle=180)
    editor.actions["rotate_pages"].trigger()
    ready_revision(qtbot, tab, 1)
    target = tmp_path / "Cancelado.pdf"
    choose_output(monkeypatch, target)
    cancelled = []

    def cancel_on_start():
        active = next(
            (
                record
                for record in editor.jobs.list_tasks()
                if record.spec.kind == "pdf_export" and record.state == TaskState.RUNNING
            ),
            None,
        )
        if active and not cancelled:
            cancelled.append(active.task_id)
            dock = editor.jobs_dock
            for row in range(dock.tree.topLevelItemCount()):
                item = dock.tree.topLevelItem(row)
                if item.data(0, Qt.ItemDataRole.UserRole) == active.task_id:
                    dock.tree.setCurrentItem(item)
                    assert dock.cancel_button.isEnabled()
                    dock.cancel_button.click()
                    break

    editor.pdf_workspace.jobs_changed.connect(cancel_on_start)
    message = export_action(editor, qtbot, tab, "save_as", successful=False)
    assert "cancelada" in message
    assert editor.jobs.status(cancelled[0]).state == TaskState.CANCELLED
    assert not target.exists()
    assert not list(tmp_path.glob("*.part.pdf"))
    assert source.read_bytes() == original
    assert tab.viewer.session.dirty and tab.viewer.can_undo
    export_action(editor, qtbot, tab, "save_as")
    assert pdf_pages(target)[0][1] == 180


def test_t10_write_failure_leaves_origin_and_revision_intact(
    editor, qtbot, pdf_fixture, monkeypatch, tmp_path
):
    source = pdf_fixture()
    original = source.read_bytes()
    tab = open_tab(editor, qtbot, source)
    choose_ranges(monkeypatch, "2")
    editor.actions["rotate_pages"].trigger()
    ready_revision(qtbot, tab, 1)
    alerts = []
    monkeypatch.setattr(QMessageBox, "warning", lambda _parent, _title, text: alerts.append(text))
    choose_output(monkeypatch, tmp_path / "Ausente" / "Saída.pdf")
    editor.actions["save_as"].trigger()
    assert "temporário" in alerts[-1] or "destino" in alerts[-1]
    target = tmp_path / "Falhou.pdf"
    choose_output(monkeypatch, target)

    def deny_publication(*_args):
        raise PermissionError("permissão negada no teste")

    monkeypatch.setattr(local_files, "_install_new", deny_publication)
    message = export_action(editor, qtbot, tab, "save_as", successful=False)
    assert "acesso à pasta" in message
    assert any(record.state == TaskState.FAILED for record in editor.jobs.list_tasks())
    assert tab.viewer.session.dirty and tab.viewer.revision == 1
    assert not target.exists()
    assert not list(tmp_path.glob("*.part.pdf"))
    assert source.read_bytes() == original


@pytest.mark.parametrize("choice", ["Cancel", "Discard", "Save"])
def test_t11_dirty_close_checks_choice(editor, qtbot, pdf_fixture, monkeypatch, tmp_path, choice):
    source = pdf_fixture()
    original = source.read_bytes()
    tab = open_tab(editor, qtbot, source)
    choose_ranges(monkeypatch, "1")
    editor.actions["rotate_pages"].trigger()
    ready_revision(qtbot, tab, 1)
    asked = []

    def reply(_parent, _title, _text, options, default):
        asked.append((options, default))
        return getattr(QMessageBox.StandardButton, choice)

    monkeypatch.setattr(QMessageBox, "question", reply)
    target = tmp_path / "Gravado no fechamento.pdf"
    choose_output(monkeypatch, target)
    editor.actions["close_tab"].trigger()
    assert asked == [
        (
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
    ]
    if choice == "Cancel":
        assert editor.tabs.currentWidget() is tab and tab.viewer.session.dirty
    else:
        qtbot.waitUntil(lambda: editor.tabs.count() == 1, timeout=12000)
    assert target.exists() is (choice == "Save")
    if target.exists():
        assert pdf_pages(target)[0][1] == 90
    assert source.read_bytes() == original


def test_t22_existing_pdf_requires_confirmation_and_original_alias_is_protected(
    editor, qtbot, pdf_fixture, monkeypatch, tmp_path
):
    source = pdf_fixture("Origem.pdf")
    destination = pdf_fixture("Destino.pdf", 2)
    original, previous = source.read_bytes(), destination.read_bytes()
    tab = open_tab(editor, qtbot, source)
    alerts, confirmed = [], []
    monkeypatch.setattr(QMessageBox, "warning", lambda _parent, _title, text: alerts.append(text))
    alias = tmp_path / "Vínculo.pdf"
    os.link(source, alias)
    for protected in (source, alias):
        choose_output(monkeypatch, protected)
        editor.actions["save_as"].trigger()
        assert "preservar" in alerts[-1]

    def answer(box):
        assert box.defaultButton().text() == "Escolher outro nome"
        confirmed.append(box.windowTitle())
        label = "Escolher outro nome" if len(confirmed) == 1 else "Substituir com backup"
        next(candidate for candidate in box.buttons() if candidate.text() == label).click()
        return int(box.result())

    monkeypatch.setattr(QMessageBox, "exec", answer)
    choose_output(monkeypatch, destination)
    editor.actions["save_as"].trigger()
    assert destination.read_bytes() == previous
    assert not list(tmp_path.glob("*.backup-*.pdf"))
    export_action(editor, qtbot, tab, "save_as")
    assert len(confirmed) == 2
    assert pdf_pages(destination) == pdf_pages(source)
    (backup,) = tmp_path.glob("Destino.backup-*.pdf")
    assert backup.read_bytes() == previous
    assert source.read_bytes() == alias.read_bytes() == original
    assert not list(tmp_path.glob("*.part.pdf"))


def canvas_position(tab, x, y):
    x, y, _, _ = rotate_rect((x, y, x, y), tab.viewer.rotation)
    return tab.canvas.mapFromScene(
        QPointF(x * tab.canvas.bounds.width(), y * tab.canvas.bounds.height())
    )


def drag_on_page(tab, qtbot, area):
    qtbot.waitUntil(lambda: not tab.render_timer.isActive(), timeout=5000)
    start, finish = canvas_position(tab, *area[:2]), canvas_position(tab, *area[2:])
    viewport = tab.canvas.viewport()
    qtbot.mousePress(viewport, Qt.MouseButton.LeftButton, pos=start)
    qtbot.mouseMove(viewport, pos=finish)
    qtbot.mouseRelease(viewport, Qt.MouseButton.LeftButton, pos=finish)


def click_on_page(tab, qtbot, point):
    qtbot.waitUntil(lambda: not tab.render_timer.isActive(), timeout=5000)
    qtbot.mouseClick(
        tab.canvas.viewport(), Qt.MouseButton.LeftButton, pos=canvas_position(tab, *point)
    )


def test_t12_annotations_edit_move_delete_save_and_reopen(
    editor, qtbot, pdf_fixture, monkeypatch, tmp_path
):
    source = pdf_fixture(rotation=90)
    original = source.read_bytes()
    tab = open_tab(editor, qtbot, source)
    editor.actions["rotate"].trigger()
    qtbot.waitUntil(lambda: tab.canvas.rotation == 90, timeout=8000)
    with pymupdf.open(source) as pdf:
        page = pdf[0]
        line = (page.search_for("Texto verificável")[0] + (-5, -4, 5, 4)) * page.rotation_matrix
        text_area = tuple(
            value / size
            for value, size in zip(
                line,
                (page.rect.width, page.rect.height) * 2,
                strict=True,
            )
        )
    monkeypatch.setattr(QInputDialog, "getMultiLineText", lambda *_args: ("Revisão em João", True))
    monkeypatch.setattr(QInputDialog, "getItem", lambda *_args: ("Aprovado", True))
    image = QImage(90, 60, QImage.Format.Format_RGB888)
    image.fill(Qt.GlobalColor.green)
    image_path = tmp_path / "Ilustração.png"
    assert image.save(str(image_path))
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *_args: (str(image_path), ""))
    for revision, (action, area) in enumerate(
        (
            ("highlight", text_area),
            ("underline", text_area),
            ("comment", (0.40, 0.43)),
            ("text", (0.20, 0.54, 0.40, 0.76)),
            ("stamp", (0.58, 0.20, 0.82, 0.46)),
            ("rectangle", (0.48, 0.53, 0.73, 0.77)),
            ("ellipse", (0.67, 0.63, 0.85, 0.79)),
            ("insert_image", (0.08, 0.33, 0.28, 0.52)),
        ),
        1,
    ):
        assert editor.actions[action].isEnabled()
        editor.actions[action].trigger()
        assert tab.placement
        if len(area) == 2:
            click_on_page(tab, qtbot, area)
        else:
            drag_on_page(tab, qtbot, area)
        ready_revision(qtbot, tab, revision)
    qtbot.waitUntil(lambda: len(tab.viewer.annotations) == 8, timeout=8000)
    entries = {entry.kind: entry for entry in tab.viewer.annotations}
    comment = entries["comment"]
    x0, y0, x1, y1 = comment.region
    click_on_page(tab, qtbot, ((x0 + x1) / 2, (y0 + y1) / 2))
    assert tab.selected_annotation == comment.xref
    editor.actions["move_object"].trigger()
    click_on_page(tab, qtbot, (0.56, 0.35))
    ready_revision(qtbot, tab, 9)
    qtbot.waitUntil(lambda: len(tab.viewer.annotations) == 8)
    moved = next(entry for entry in tab.viewer.annotations if entry.kind == "comment")
    assert moved.region[:2] == pytest.approx((0.56, 0.35), abs=0.012)
    selection = editor.properties_dock.editor.objects
    selection.setCurrentIndex(selection.findData(moved.xref))
    monkeypatch.setattr(
        QInputDialog, "getMultiLineText", lambda *_args: ("Comentário atualizado", True)
    )
    editor.actions["change_object"].trigger()
    ready_revision(qtbot, tab, 10)
    qtbot.waitUntil(lambda: len(tab.viewer.annotations) == 8)
    ellipse = next(entry for entry in tab.viewer.annotations if entry.kind == "ellipse")
    selection.setCurrentIndex(selection.findData(ellipse.xref))
    monkeypatch.setattr(QMessageBox, "question", lambda *_args: QMessageBox.StandardButton.Yes)
    editor.actions["remove_object"].trigger()
    ready_revision(qtbot, tab, 11)
    qtbot.waitUntil(lambda: len(tab.viewer.annotations) == 7)
    editor.actions["undo"].trigger()
    ready_revision(qtbot, tab, 10)
    qtbot.waitUntil(lambda: len(tab.viewer.annotations) == 8)
    editor.actions["redo"].trigger()
    ready_revision(qtbot, tab, 11)
    target = tmp_path / "Com anotações.pdf"
    choose_output(monkeypatch, target)
    export_action(editor, qtbot, tab, "save_as")
    with pymupdf.open(target) as pdf:
        page = pdf[0]
        annotations = list(page.annots())
        assert sorted(annot.type[1] for annot in annotations) == [
            "FreeText",
            "Highlight",
            "Square",
            "Stamp",
            "Stamp",
            "Text",
            "Underline",
        ]
        assert page.rotation == 90
        assert "Texto verificável" in page.get_text()
        assert not pdf.is_repaired
        text = next(annot for annot in annotations if annot.type[1] == "FreeText")
        assert text.info["content"] == "Revisão em João"
        sticky = next(annot for annot in annotations if annot.type[1] == "Text")
        assert sticky.info["content"] == "Comentário atualizado"
        location = sticky.rect * page.rotation_matrix
        assert (location.x0 / page.rect.width, location.y0 / page.rect.height) == pytest.approx(
            (0.56, 0.35), abs=0.012
        )
        assert page.get_pixmap(annots=True).samples != page.get_pixmap(annots=False).samples
    assert source.read_bytes() == original
    reopened = open_tab(editor, qtbot, target)
    qtbot.waitUntil(lambda: len(reopened.viewer.annotations) == 7)


def test_acroform_edit_text_checkbox_and_choice_without_scripts(
    editor, qtbot, pdf_fixture, monkeypatch, tmp_path
):
    source = pdf_fixture(forms=True)
    original = source.read_bytes()
    tab = open_tab(editor, qtbot, source)
    qtbot.waitUntil(lambda: len(tab.viewer.fields) == 4)
    assert editor.actions["forms"].isEnabled()

    def choose_field(name, value):
        def exec_dialog(dialog):
            locked = next(
                i for i, field in enumerate(dialog.fields) if field.name == "Campo protegido"
            )
            dialog.selector.setCurrentIndex(locked)
            assert not dialog.apply.isEnabled()
            index = next(i for i, field in enumerate(dialog.fields) if field.name == name)
            dialog.selector.setCurrentIndex(index)
            assert dialog.apply.isEnabled()
            if dialog.fields[index].kind == "text":
                dialog.line.setText(value)
            else:
                dialog.choice.setCurrentIndex(dialog.choice.findData(value))
            return QDialog.DialogCode.Accepted

        monkeypatch.setattr(FormDialog, "exec", exec_dialog)

    for revision, (field, value) in enumerate(
        (
            ("Nome", "João de Souza"),
            ("Conferido", "Yes"),
            ("Revisão", "Fechada"),
        ),
        1,
    ):
        choose_field(field, value)
        editor.actions["forms"].trigger()
        ready_revision(qtbot, tab, revision)
        qtbot.waitUntil(lambda: len(tab.viewer.fields) == 4)
        assert next(item for item in tab.viewer.fields if item.name == field).value == value
    editor.actions["undo"].trigger()
    ready_revision(qtbot, tab, 2)
    qtbot.waitUntil(lambda: len(tab.viewer.fields) == 4)
    assert tab.viewer.fields[2].value == "Aberta"
    editor.actions["redo"].trigger()
    ready_revision(qtbot, tab, 3)
    target = tmp_path / "Formulário preenchido.pdf"
    choose_output(monkeypatch, target)
    export_action(editor, qtbot, tab, "save_as")
    with pymupdf.open(target) as pdf:
        assert {field.field_name: field.field_value for field in pdf[0].widgets()} == {
            "Nome": "João de Souza",
            "Conferido": "Yes",
            "Revisão": "Fechada",
            "Campo protegido": "Fixo",
        }
    assert source.read_bytes() == original


@pytest.mark.parametrize("kind", ["flag", "detached_cms"])
def test_t15_warn_before_editing_or_exporting_pdf_with_signature(
    editor, qtbot, pdf_fixture, monkeypatch, tmp_path, kind
):
    if kind == "detached_cms":
        source = tmp_path / "Assinatura CMS.pdf"
        fixture = Path(__file__).resolve().parents[1] / "fixtures" / "assinado-t15.pdf"
        source.write_bytes(fixture.read_bytes())
    else:
        source = pdf_fixture(forms=True, signed=True)
    original = source.read_bytes()
    tab = open_tab(editor, qtbot, source)
    assert tab.viewer.info.signed
    assert "Indicada" in editor.properties_dock.fields["signature"].text()
    confirmations = []

    def decide(_parent, title, message, _buttons, default):
        assert default == QMessageBox.StandardButton.Cancel
        assert "invalidar" in message
        confirmations.append(title)
        return (
            QMessageBox.StandardButton.Cancel
            if len(confirmations) < 3
            else QMessageBox.StandardButton.Ok
        )

    monkeypatch.setattr(QMessageBox, "warning", decide)
    target = tmp_path / "Edição com ciência.pdf"
    choose_output(monkeypatch, target)
    editor.actions["save_as"].trigger()
    assert not target.exists()
    choose_ranges(monkeypatch, "1")
    editor.actions["rotate_pages"].trigger()
    assert tab.viewer.revision == 0 and not tab.viewer.busy
    editor.actions["rotate_pages"].trigger()
    ready_revision(qtbot, tab, 1)
    export_action(editor, qtbot, tab, "save_as")
    assert confirmations == ["Assinatura digital indicada"] * 3
    assert pdf_pages(target)[0][1] == 90
    assert source.read_bytes() == original


def test_continuous_scroll_renders_visible_pages_and_restores_page_mode(editor, qtbot, pdf_fixture):
    tab = open_tab(editor, qtbot, pdf_fixture(count=15))
    editor.actions["continuous"].trigger()
    view = tab.continuous
    qtbot.waitUntil(lambda: view.isVisible() and 0 in view.pages.images, timeout=10000)
    view.verticalScrollBar().setValue(4 * view.pages.height)
    qtbot.waitUntil(
        lambda: tab.viewer.page >= 4 and tab.viewer.page in view.pages.images, timeout=10000
    )
    assert len(view.pages.images) <= 4
    page = tab.viewer.page
    editor.actions["find"].trigger()
    qtbot.waitUntil(lambda: tab.canvas.has_page and tab.canvas.page == page, timeout=10000)
    assert not editor.actions["continuous"].isChecked()
    assert tab.search.isVisible()


@pytest.mark.skipif(
    sys.platform != "win32", reason="Bloqueio de substituição de arquivo pelo Windows"
)
def test_windows_locked_destination_fails_safely(editor, qtbot, pdf_fixture, monkeypatch):
    source = pdf_fixture("PDF de origem.pdf")
    target = pdf_fixture("PDF em uso.pdf", 2)
    before, previous = source.read_bytes(), target.read_bytes()
    tab = open_tab(editor, qtbot, source)
    monkeypatch.setattr(editor.document_tools, "_overwrite", lambda _path: True)
    choose_output(monkeypatch, target)
    with target.open("rb"):
        assert "acesso" in export_action(editor, qtbot, tab, "save_as", successful=False)
    assert target.read_bytes() == previous
    assert source.read_bytes() == before
    assert not list(target.parent.glob("*.part.pdf"))


def test_worker_exit_recovers_validated_revision_and_allows_save(
    editor, qtbot, pdf_fixture, monkeypatch, tmp_path
):
    source = pdf_fixture()
    before = source.read_bytes()
    tab = open_tab(editor, qtbot, source)
    choose_ranges(monkeypatch, "2", angle=180)
    editor.actions["rotate_pages"].trigger()
    ready_revision(qtbot, tab, 1)
    work = tab.viewer.session.working_copy
    assert work.is_file()
    tab.viewer._worker.process.kill()
    qtbot.waitUntil(tab.recover_button.isVisible, timeout=6000)
    tab.recover_button.click()
    ready_revision(qtbot, tab, 0)
    assert tab.viewer.session.dirty and not tab.viewer.can_undo
    assert tab.viewer.page == 1 and tab.page_properties[2] == 180
    target = tmp_path / "Recuperado.pdf"
    choose_output(monkeypatch, target)
    export_action(editor, qtbot, tab, "save_as")
    assert pdf_pages(target)[1][1] == 180
    assert source.read_bytes() == before
    editor.close_current_tab()
    assert not work.parent.exists()


def test_encrypted_copy_keeps_password_and_enforces_permissions(
    editor, qtbot, pdf_fixture, monkeypatch, tmp_path
):
    source = tmp_path / "Acesso restrito.pdf"
    permissions = pymupdf.PDF_PERM_ANNOTATE | pymupdf.PDF_PERM_FORM
    with pymupdf.open(pdf_fixture(forms=True)) as pdf:
        pdf.save(
            source,
            encryption=pymupdf.PDF_ENCRYPT_AES_256,
            user_pw="m23-teste",
            owner_pw="m23-proprietario",
            permissions=permissions,
        )
    original = source.read_bytes()
    tab = editor.open_pdfs([source])[0]
    qtbot.waitUntil(lambda: tab.viewer.state == "password", timeout=10000)
    tab.password.setText("m23-teste")
    qtbot.keyClick(tab.password, Qt.Key.Key_Return)
    ready_revision(qtbot, tab, 0)
    assert not editor.actions["rotate_pages"].isEnabled()
    with qtbot.waitSignal(tab.viewer.message, timeout=8000) as message:
        assert tab.viewer.change("rotate_pages", {"ranges": [(0, 0)], "angle": 90})
    assert "permissões" in message.args[0]
    monkeypatch.setattr(QInputDialog, "getMultiLineText", lambda *_args: ("Nota autorizada", True))
    editor.actions["comment"].trigger()
    click_on_page(tab, qtbot, (0.45, 0.50))
    ready_revision(qtbot, tab, 1)
    target = tmp_path / "Cópia protegida.pdf"
    choose_output(monkeypatch, target)
    export_action(editor, qtbot, tab, "save_as")
    with pymupdf.open(source) as pdf:
        assert pdf.authenticate("m23-teste") == 2
        encryption = pdf.metadata["encryption"]
        assert "AES" in encryption and "256" in encryption
    with pymupdf.open(target) as pdf:
        assert pdf.is_encrypted and not pdf.authenticate("senha errada")
        assert pdf.authenticate("m23-teste") == 2
        assert pdf.metadata["encryption"] == encryption
        assert pdf.permissions & permissions == permissions
        assert not (pdf.permissions & pymupdf.PDF_PERM_ASSEMBLE)
        page = pdf[0]
        assert page.rotation == 0
        assert [annot.info["content"] for annot in page.annots()] == ["Nota autorizada"]
    assert source.read_bytes() == original
