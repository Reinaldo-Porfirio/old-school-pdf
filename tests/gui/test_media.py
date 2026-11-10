import os
from pathlib import Path

import pymupdf
import pytest
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QDialog, QFileDialog

from docforge.app import create_window
from docforge.domain.media import MediaOperation
from docforge.domain.tasks import TaskState
from docforge.infrastructure import media_output
from docforge.ui.media_dialogs import BatchDialog, BatchReport
from docforge.ui.ocr_setup import OcrSetupDialog

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


@pytest.fixture
def workstation(qtbot, tmp_path):
    def clean_up(window):
        runner = window.media_tools.runner
        if runner.active:
            runner.cancel_all()
            qtbot.waitUntil(lambda: not runner.active, timeout=8000)
        window.pdf_workspace.close()

    window = create_window(tmp_path / "media.ini")
    qtbot.addWidget(window, before_close_func=clean_up)
    window.show()
    qtbot.waitUntil(window.isVisible)
    return window


def make_pdf(path, count=3, *, image=None):
    with pymupdf.open() as pdf:
        xref = None
        for index in range(count):
            page = pdf.new_page(width=360, height=520)
            page.insert_text((32, 65), f"Revisão técnica · página {index + 1}", fontsize=18)
            if image is not None:
                rect = pymupdf.Rect(44, 130, 280, 366)
                xref = (
                    page.insert_image(rect, pixmap=image)
                    if xref is None
                    else page.insert_image(rect, xref=xref)
                )
        pdf.save(path)
    return path


def set_dialog(monkeypatch, paths, destination, mode=None, configure=None, *, only_inputs=True):
    def exec_dialog(dialog):
        if mode is not None:
            dialog.operation.setCurrentIndex(dialog.operation.findData(mode.value))
        if only_inputs:
            dialog.files.clear()
        dialog.add_paths(paths)
        dialog.destination.setText(str(destination))
        if configure:
            configure(dialog)
        assert dialog.run_button.isEnabled(), dialog.status.text()
        dialog.accept()
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(BatchDialog, "exec", exec_dialog)


def run_action(window, qtbot, key):
    runner = window.media_tools.runner
    with qtbot.waitSignal(runner.completed, timeout=30000):
        window.actions[key].trigger()
    assert not runner.active
    return runner.records()


def no_stages(folder):
    return not list(folder.glob(".docforge-lote-*"))


@pytest.fixture
def tessdata():
    path = os.environ.get("DOCFORGE_TEST_TESSDATA")
    if not path:
        pytest.skip("Defina DOCFORGE_TEST_TESSDATA com os modelos locais para testar OCR real")
    path = Path(path).absolute()
    assert all((path / f"{code}.traineddata").is_file() for code in ("por", "eng"))
    return path


def setup_ocr(window, qtbot, monkeypatch, path):
    def configure(dialog):
        dialog.choose.click()
        assert dialog.validate.isEnabled() and not dialog.apply_button.isEnabled()
        dialog.validate.click()
        qtbot.waitUntil(dialog.apply_button.isEnabled, timeout=18000)
        assert dialog.languages == ("por", "eng")
        dialog.apply_button.click()
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(QFileDialog, "getExistingDirectory", lambda *_args: str(path))
    monkeypatch.setattr(OcrSetupDialog, "exec", configure)
    window.actions["ocr_setup"].trigger()
    assert window.actions["ocr"].isEnabled()
    assert window.settings.load_preferences().ocr_tessdata == str(path)
    assert window.capabilities.check().get("tesseract").detected


@pytest.mark.parametrize(
    "language,phrase,term",
    [
        ("por", "Relatório de revisão técnica", "revisão técnica"),
        ("eng", "Technical inspection report", "inspection report"),
    ],
)
def test_t13_searchable_ocr_preserves_rotated_scan_and_only_processes_selection(
    workstation,
    qtbot,
    tmp_path,
    monkeypatch,
    tessdata,
    language,
    phrase,
    term,
):
    setup_ocr(workstation, qtbot, monkeypatch, tessdata)
    source = tmp_path / "Digitalização de teste.pdf"
    with pymupdf.open() as art, pymupdf.open() as scan:
        draft = art.new_page(width=450, height=300)
        draft.insert_text((34, 78), phrase, fontsize=28)
        draft.insert_text((34, 136), "DocForge Ultimate 2026", fontsize=26)
        image = draft.get_pixmap(dpi=220)
        first = scan.new_page(width=300, height=450)
        first.insert_image(first.rect, pixmap=image, rotate=90)
        first.set_rotation(90)
        page = scan.new_page(width=450, height=300)
        page.insert_text((34, 90), "Camada de texto existente", fontsize=20)
        last = scan.new_page(width=450, height=300)
        last.insert_image(last.rect, pixmap=image)
        scan.save(source)
    before = source.read_bytes()
    tab = workstation.open_pdfs([source])[0]
    qtbot.waitUntil(lambda: tab.canvas.has_page, timeout=12000)

    def options(dialog):
        assert dialog.suggested == source and dialog._has_preview
        dialog.ranges.setText("1–2")
        dialog.language.setCurrentIndex(dialog.language.findData(language))

    set_dialog(monkeypatch, [source], tmp_path, configure=options, only_inputs=False)
    (record,) = run_action(workstation, qtbot, "ocr")
    assert record.state == TaskState.SUCCEEDED, record.error
    assert "1 página(s) com OCR" in record.detail and "1 já tinham texto" in record.detail
    with pymupdf.open(record.result) as result, pymupdf.open(source) as original:
        assert result.page_count == original.page_count == 3
        assert result[0].rotation == 90
        assert term in result[0].get_text().casefold()
        assert result[0].search_for(term)
        assert result[0].get_pixmap(dpi=100).samples == original[0].get_pixmap(dpi=100).samples
        assert result[1].get_text() == original[1].get_text()
        assert not result[2].get_text().strip()
    assert source.read_bytes() == before and no_stages(tmp_path)

    def report(dialog):
        assert dialog.results.topLevelItemCount() == 1 and dialog.open_button.isEnabled()
        assert "1 página(s) com OCR" in dialog.entry_note.text()
        dialog.open_button.click()
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(BatchReport, "exec", report)
    workstation.actions["batch_report"].trigger()
    reopened = workstation.tabs.currentWidget()
    qtbot.waitUntil(lambda: reopened.canvas.has_page, timeout=12000)
    workstation.actions["find"].trigger()
    reopened.query.setText(term)
    qtbot.keyClick(reopened.query, Qt.Key.Key_Return)
    qtbot.waitUntil(lambda: bool(reopened.viewer.hits), timeout=12000)


def test_t14_ocr_absent_stays_disabled_with_configuration_path(workstation, monkeypatch):
    assert not workstation.actions["ocr"].isEnabled()
    assert "Configurar OCR local" in workstation.actions["ocr"].toolTip()
    assert workstation.actions["ocr_setup"].isEnabled()
    assert not workstation.capabilities.check().get("tesseract").detected
    inspected = []

    def show_setup(dialog):
        inspected.append(dialog.status.text())
        assert not dialog.apply_button.isEnabled() and not dialog.validate.isEnabled()
        return QDialog.DialogCode.Rejected

    monkeypatch.setattr(OcrSetupDialog, "exec", show_setup)
    workstation.actions["ocr_setup"].trigger()
    assert inspected and ".traineddata" in inspected[0]
    assert not workstation.media_tools.runner.records()


def test_invalid_local_model_is_not_enabled(workstation, qtbot, tmp_path, monkeypatch):
    models = tmp_path / "Modelos incompatíveis"
    models.mkdir()
    (models / "por.traineddata").write_bytes(b"not a model\n" * 200)

    def configure(dialog):
        dialog.choose.click()
        assert dialog.validate.isEnabled()
        dialog.validate.click()
        qtbot.waitUntil(lambda: dialog.process is None, timeout=18000)
        assert not dialog.apply_button.isEnabled()
        assert not dialog.languages
        return QDialog.DialogCode.Rejected

    monkeypatch.setattr(QFileDialog, "getExistingDirectory", lambda *_args: str(models))
    monkeypatch.setattr(OcrSetupDialog, "exec", configure)
    workstation.actions["ocr_setup"].trigger()
    assert not workstation.actions["ocr"].isEnabled()


def test_t18_batch_keeps_ten_tabs_responsive_logs_failures_and_retries(
    workstation,
    qtbot,
    tmp_path,
    monkeypatch,
):
    sources = [make_pdf(tmp_path / f"Caderno {i:02d} ç.pdf") for i in range(10)]
    corrupt = tmp_path / "Falha.pdf"
    corrupt.write_bytes(b"%PDF-1.7\ntruncado\n")
    before = {path: path.read_bytes() for path in [*sources, corrupt]}
    tabs = workstation.open_pdfs(sources)
    qtbot.waitUntil(lambda: all(tab.viewer.state == "ready" for tab in tabs), timeout=20000)
    existing = tmp_path / (sources[0].stem + " - Páginas")
    existing.mkdir()
    marker = existing / "já existia.txt"
    marker.write_text("preservar", encoding="utf-8")
    set_dialog(monkeypatch, [sources[0], corrupt, sources[-1]], tmp_path, MediaOperation.RENDER)
    active_records = []
    ticks = []
    runner = workstation.media_tools.runner

    def observe():
        if any(r.state == TaskState.RUNNING and r.progress > 0 for r in runner.records()):
            active_records.append(True)
            if len(active_records) == 1:
                workstation.tabs.setCurrentWidget(tabs[3])
                assert workstation.actions["find"].isEnabled()

    runner.changed.connect(observe)
    timer = QTimer(workstation)
    timer.timeout.connect(lambda: ticks.append(1) if runner.active else None)
    timer.start(10)
    first, bad, last = run_action(workstation, qtbot, "batch")
    timer.stop()
    assert ticks and active_records and workstation.tabs.count() == 11
    assert workstation.tabs.currentWidget() is tabs[3]
    assert (first.state, bad.state, last.state) == (
        TaskState.SUCCEEDED,
        TaskState.FAILED,
        TaskState.SUCCEEDED,
    )
    assert bad.error and first.detail and last.detail
    assert first.result != existing and first.result.is_dir()
    assert len(list(first.result.glob("pagina-*.png"))) == 3
    assert marker.read_text(encoding="utf-8") == "preservar"
    assert all(path.read_bytes() == content for path, content in before.items())
    assert no_stages(tmp_path)

    make_pdf(corrupt, 1)
    with qtbot.waitSignal(runner.completed, timeout=18000):
        runner.retry()
    (retried,) = runner.records()
    assert retried.spec.inputs == (corrupt,) and retried.state == TaskState.SUCCEEDED
    assert first.result.is_dir() and last.result.is_dir() and no_stages(tmp_path)


def test_cancel_running_conversion_from_queue_discards_partial_output(
    workstation,
    qtbot,
    tmp_path,
    monkeypatch,
):
    source = make_pdf(tmp_path / "Longo.pdf", 10)
    before = source.read_bytes()
    set_dialog(monkeypatch, [source], tmp_path)
    runner = workstation.media_tools.runner
    stopped = []

    def cancel():
        active = next(
            (r for r in runner.records() if r.state == TaskState.RUNNING and r.progress >= 10), None
        )
        if active and not stopped:
            stopped.append(active.task_id)
            dock = workstation.jobs_dock
            for row in range(dock.tree.topLevelItemCount()):
                item = dock.tree.topLevelItem(row)
                if item.data(0, Qt.ItemDataRole.UserRole) == active.task_id:
                    dock.tree.setCurrentItem(item)
                    assert dock.cancel_button.isEnabled()
                    dock.cancel_button.click()
                    break

    runner.changed.connect(cancel)
    (record,) = run_action(workstation, qtbot, "images")
    assert stopped and record.state == TaskState.CANCELLED
    assert record.result is None and list(tmp_path.glob("Longo - Páginas*")) == []
    assert no_stages(tmp_path) and source.read_bytes() == before


@pytest.mark.skipif(os.name != "nt", reason="Repetição específica para bloqueio no Windows")
def test_cleanup_retries_a_transient_windows_sharing_violation(monkeypatch, tmp_path):
    stage = media_output.MediaOutput.prepare(tmp_path, "QA")
    (stage.stage / "incompleto.png").touch()
    original = tmp_path / "entrada.pdf"
    original.write_bytes(b"arquivo de controle")
    remove = media_output.rmtree
    attempts = []

    def locked_once(path):
        attempts.append(path)
        if len(attempts) == 1:
            raise PermissionError("bloqueio temporário do arquivo de teste")
        remove(path)

    monkeypatch.setattr(media_output, "rmtree", locked_once)
    stage.cleanup()
    assert attempts == [stage.stage, stage.stage]
    assert not stage.stage.exists() and original.read_bytes() == b"arquivo de controle"


def test_images_to_pdf_keeps_order_orientation_and_tiff_frames(
    workstation, qtbot, tmp_path, monkeypatch
):
    png = tmp_path / "Paisagem.png"
    jpg = tmp_path / "Retrato.jpg"
    tiff = FIXTURES / "imagens-multiplas-m4.tif"
    with pymupdf.open() as doc:
        for path, dimensions, color in [(png, (130, 80), (1, 0, 0)), (jpg, (80, 130), (0, 0, 1))]:
            page = doc.new_page(width=dimensions[0], height=dimensions[1])
            page.draw_rect(page.rect, color=None, fill=color)
            page.get_pixmap(dpi=72).save(path)

    def reorder(dialog):
        dialog.files.setCurrentRow(1)
        dialog.up.click()
        assert dialog.paths() == (jpg, png, tiff)

    originals = {path: path.read_bytes() for path in (png, jpg, tiff)}
    set_dialog(monkeypatch, [png, jpg, tiff], tmp_path, configure=reorder)
    (record,) = run_action(workstation, qtbot, "images_pdf")
    assert record.state == TaskState.SUCCEEDED, record.error
    with pymupdf.open(record.result) as pdf:
        assert pdf.page_count == 4
        assert [(p.rect.width, p.rect.height) for p in pdf] == [
            (80, 130),
            (130, 80),
            (96, 60),
            (60, 96),
        ]

    def jpeg_options(dialog):
        dialog.ranges.setText("2,4")
        dialog.format.setCurrentIndex(dialog.format.findData("jpg"))
        dialog.dpi.setCurrentIndex(dialog.dpi.findData(150))

    set_dialog(monkeypatch, [record.result], tmp_path, configure=jpeg_options)
    (images,) = run_action(workstation, qtbot, "images")
    assert images.state == TaskState.SUCCEEDED, images.error
    assert sorted(path.name for path in images.result.iterdir()) == [
        "pagina-00002.jpg",
        "pagina-00004.jpg",
    ]
    with pymupdf.open(images.result / "pagina-00002.jpg") as image:
        assert image[0].rect.width > image[0].rect.height
    assert all(path.read_bytes() == content for path, content in originals.items())


def test_text_images_and_lossless_optimization_roundtrip(workstation, qtbot, tmp_path, monkeypatch):
    with pymupdf.open() as document:
        sample = document.new_page(width=320, height=320)
        sample.draw_rect(sample.rect, color=None, fill=(0.15, 0.25, 0.45))
        pixmap = sample.get_pixmap(dpi=320)
    source = make_pdf(tmp_path / "Entrada.pdf", image=pixmap)
    before = source.read_bytes()
    set_dialog(monkeypatch, [source], tmp_path)
    (text,) = run_action(workstation, qtbot, "extract_text")
    assert text.state == TaskState.SUCCEEDED, text.error
    content = text.result.read_text(encoding="utf-8")
    assert "Revisão técnica" in content and "--- Página 3 ---" in content
    assert "UTF-8" in text.detail
    (image,) = run_action(workstation, qtbot, "extract_images")
    assert image.state == TaskState.SUCCEEDED, image.error
    assert image.result.suffix == ".png" and "1 imagem" in image.detail
    assert pymupdf.Pixmap(image.result).samples == pixmap.samples
    (optimized,) = run_action(workstation, qtbot, "compress")
    assert optimized.state == TaskState.SUCCEEDED, optimized.error
    assert optimized.result.stat().st_size < len(before) and "bytes" in optimized.detail
    with pymupdf.open(optimized.result) as pdf, pymupdf.open(source) as original:
        assert pdf.page_count == original.page_count == 3
        assert pdf[0].get_pixmap().samples == original[0].get_pixmap().samples
        assert pdf[1].get_text() == original[1].get_text()
    set_dialog(
        monkeypatch, [source], tmp_path, configure=lambda dialog: dialog.reduce.setChecked(True)
    )
    (reduced,) = run_action(workstation, qtbot, "compress")
    assert reduced.state == TaskState.SUCCEEDED, reduced.error
    assert reduced.result.stat().st_size < len(before)
    assert "recompressão de imagens" in reduced.detail
    with pymupdf.open(reduced.result) as pdf:
        assert pdf.page_count == 3 and pdf[0].get_images()[0][2] < pixmap.width
        assert "Revisão técnica" in pdf[0].get_text()
    assert source.read_bytes() == before and no_stages(tmp_path)


def test_batch_merge_and_split_validate_every_output(workstation, qtbot, tmp_path, monkeypatch):
    one = make_pdf(tmp_path / "Um.pdf", 3)
    two = make_pdf(tmp_path / "Dois.pdf", 2)
    set_dialog(monkeypatch, [one, two], tmp_path, MediaOperation.MERGE)
    (merged,) = run_action(workstation, qtbot, "batch")
    assert merged.state == TaskState.SUCCEEDED, merged.error
    with pymupdf.open(merged.result) as pdf:
        assert pdf.page_count == 5
    set_dialog(
        monkeypatch,
        [merged.result],
        tmp_path,
        MediaOperation.SPLIT,
        lambda dialog: dialog.split_size.setValue(2),
    )
    (split,) = run_action(workstation, qtbot, "batch")
    assert split.state == TaskState.SUCCEEDED, split.error
    counts = []
    for path in sorted(split.result.glob("parte-*.pdf")):
        with pymupdf.open(path) as pdf:
            counts.append(pdf.page_count)
    assert counts == [2, 2, 1] and no_stages(tmp_path)


def test_mutating_batch_requires_acknowledgement_for_signed_pdf(
    workstation, qtbot, tmp_path, monkeypatch
):
    source = FIXTURES / "assinado-t15.pdf"
    before = source.read_bytes()
    set_dialog(monkeypatch, [source], tmp_path)
    (record,) = run_action(workstation, qtbot, "compress")
    assert record.state == TaskState.FAILED and "assinatura" in record.error
    assert record.result is None and no_stages(tmp_path)
    assert source.read_bytes() == before
