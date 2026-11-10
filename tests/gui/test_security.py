import socket
from datetime import UTC, datetime, timedelta

import pymupdf as pdf
import pytest
from PySide6.QtCore import QPointF, Qt
from PySide6.QtWidgets import QDialog, QFileDialog, QLabel, QLineEdit, QPlainTextEdit

from oldschoolpdf.app import create_window
from oldschoolpdf.domain.security import REDACTION_DPI
from oldschoolpdf.domain.tasks import TaskState
from oldschoolpdf.domain.viewer import rotate_rect
from oldschoolpdf.infrastructure.pdf_engine import PdfEngine
from oldschoolpdf.infrastructure.pdf_security import PERMISSION_BITS
from oldschoolpdf.infrastructure.pdf_signatures import signature_report
from oldschoolpdf.ui.security_dialogs import (
    MetadataDialog,
    ProtectionDialog,
    RedactionReviewDialog,
    SignatureReportDialog,
    SignDialog,
    TrustDialog,
    VisualSignatureDialog,
)

XMP = (
    '<x:xmpmeta xmlns:x="adobe:ns:meta/"><rdf:RDF '
    'xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
    '<rdf:Description rdf:about="" xmlns:df="urn:oldschoolpdf:qa">'
    "<df:private>XMP_QA_ONLY</df:private></rdf:Description></rdf:RDF></x:xmpmeta>"
)


@pytest.fixture
def workspace(qtbot, tmp_path):
    def clear(window):
        for tab in window._pdf_tabs():
            tab.viewer.session.dirty = False
            tab.viewer.busy = ""
        window.pdf_workspace.close()

    window = create_window(tmp_path / "m5-sintetico.ini")
    qtbot.addWidget(window, before_close_func=clear)
    window.show()
    qtbot.waitUntil(window.isVisible)
    return window


@pytest.fixture
def sample(tmp_path):
    path = tmp_path / "Dossiê de QA ç.pdf"
    with pdf.open() as document:
        first = document.new_page(width=360, height=280)
        first.insert_text((40, 58), "SEGREDO_VISIVEL_QA", fontsize=16)
        first.insert_text((170, 210), "SEGREDO_OCULTO_QA", render_mode=3)
        layer = document.add_ocg("CAMADA_OCULTA_QA", on=False)
        first.insert_text((130, 175), "SEGREDO_CAMADA_QA", oc=layer)
        image = pdf.Pixmap(pdf.csRGB, pdf.IRect(0, 0, 24, 20), False)
        image.set_rect(image.irect, (246, 98, 21))
        first.insert_image(pdf.Rect(40, 65, 100, 107), pixmap=image)
        first.draw_rect(pdf.Rect(270, 190, 343, 268), color=None, fill=(0, 0.75, 0))
        first.add_text_annot((230, 69), "COMENTARIO_QA", icon="Note")
        first.insert_link(
            {
                "kind": pdf.LINK_URI,
                "from": pdf.Rect(140, 98, 200, 112),
                "uri": "https://example.invalid/qa",
            }
        )
        widget = pdf.Widget()
        widget.field_name = "FORM_QA"
        widget.field_type = pdf.PDF_WIDGET_TYPE_TEXT
        widget.field_value = "CAMPO_QA"
        widget.rect = pdf.Rect(40, 111, 160, 134)
        first.add_widget(widget)
        first_xref = first.xref
        second = document.new_page(width=360, height=280)
        second.insert_text((70, 90), "ROTACAO_QA", fontsize=14)
        second.set_cropbox(pdf.Rect(25, 30, 326, 250))
        second.set_rotation(90)
        document.set_toc([[1, "INDICE_QA", 1]])
        document.xref_set_key(document.pdf_catalog(), "OpenAction", f"[{first_xref} 0 R /Fit]")
        document.embfile_add("anexo-qa.txt", b"SEGREDO_ANEXO_QA")
        document.set_xml_metadata(XMP)
        document.set_metadata({"title": "TITULO_REMOVER_QA", "author": "AUTOR_PRESERVAR_QA"})
        document.save(path, deflate=True)
    with pdf.open(path) as document:
        document.set_metadata({"subject": "REVISAO_QA"})
        document.saveIncr()
    return path


def _tab(window, qtbot, path, password=None):
    tab = window.open_pdfs([path])[0]
    if password is not None:
        qtbot.waitUntil(lambda: tab.viewer.state == "password", timeout=12000)
        tab.password.setText(password)
        qtbot.keyClick(tab.password, Qt.Key.Key_Return)
    qtbot.waitUntil(lambda: tab.canvas.has_page, timeout=12000)
    return tab


def _export(window, qtbot, monkeypatch, tab, action, path, *, success=True):
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, **k: (str(path), ""))
    with qtbot.waitSignal(tab.viewer.export_completed, timeout=20000) as result:
        assert window.actions[action].isEnabled()
        window.actions[action].trigger()
    assert result.args[0] is success, result.args[1]
    assert path.exists() is success
    return result.args[1]


def _select(qtbot, tab, region):
    canvas = tab.canvas
    x0, y0, x1, y1 = rotate_rect(region, canvas.rotation)

    def point(x, y):
        return canvas.mapFromScene(QPointF(x * canvas.bounds.width(), y * canvas.bounds.height()))

    start, end = point(x0, y0), point(x1, y1)
    qtbot.mousePress(canvas.viewport(), Qt.MouseButton.LeftButton, pos=start)
    qtbot.mouseMove(canvas.viewport(), end)
    qtbot.mouseRelease(canvas.viewport(), Qt.MouseButton.LeftButton, pos=end)


def test_m5_metadata_selective_xmp_and_original(workspace, qtbot, monkeypatch, sample, tmp_path):
    original = sample.read_bytes()
    tab = _tab(workspace, qtbot, sample)

    def choose(dialog):
        for key, field in dialog.fields.items():
            field.setChecked(key == "title")
        assert dialog.xml.isChecked() and dialog.proceed.isEnabled()
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(MetadataDialog, "exec", choose)
    output = tmp_path / "Sem título nem XMP.pdf"
    _export(workspace, qtbot, monkeypatch, tab, "metadata", output)
    with pdf.open(output) as copy:
        assert not copy.metadata["title"] and not copy.get_xml_metadata()
        assert copy.metadata["author"] == "AUTOR_PRESERVAR_QA"
        assert copy.metadata["subject"] == "REVISAO_QA"
        assert copy.embfile_get(0) == b"SEGREDO_ANEXO_QA"
        assert copy[0].first_widget.field_value == "CAMPO_QA"
        assert copy.xref_get_key(-1, "Prev")[0] == "null"
    assert b"TITULO_REMOVER_QA" not in output.read_bytes()
    assert sample.read_bytes() == original and tab.viewer.revision == 0


def test_m5_protection_auth_permissions_and_owner_gate(
    workspace, qtbot, monkeypatch, sample, tmp_path
):
    original = sample.read_bytes()
    tab = _tab(workspace, qtbot, sample)
    user = "m5-usuário-QA"
    owner = "m5-proprietário-QA"

    def choose(dialog):
        assert all(
            field.echoMode() == QLineEdit.EchoMode.Password
            for field in (dialog.user, dialog.user_check, dialog.owner, dialog.owner_check)
        )
        for field, value in (
            (dialog.user, user),
            (dialog.user_check, "diferente"),
            (dialog.owner, owner),
            (dialog.owner_check, owner),
        ):
            field.setText(value)
        dialog.accept()
        assert dialog.error.text() and dialog.result() != QDialog.DialogCode.Accepted
        dialog.user_check.setText(user)
        dialog.allowed["print"].setChecked(True)
        dialog.allowed["modify"].setChecked(True)
        dialog.accept()
        assert dialog.result() == QDialog.DialogCode.Accepted
        return dialog.result()

    monkeypatch.setattr(ProtectionDialog, "exec", choose)
    protected = tmp_path / "AES protegido.pdf"
    _export(workspace, qtbot, monkeypatch, tab, "password", protected)
    protected_bytes = protected.read_bytes()
    with pdf.open(protected) as locked:
        assert locked.needs_pass and not locked.authenticate("inválida")
        assert locked.authenticate(user) == 2
        assert "256-bit AES" in locked.metadata["encryption"]
        assert [key for key, bit in PERMISSION_BITS.items() if locked.permissions & bit] == [
            "print",
            "modify",
        ]
        assert locked.permissions & pdf.PDF_PERM_PRINT_HQ
    with pdf.open(protected) as locked:
        assert locked.authenticate(owner) & 4
        assert locked.page_count == 2
    locked_tab = _tab(workspace, qtbot, protected, user)
    assert not locked_tab.viewer.info.copy_allowed
    assert not workspace.actions["rotate_pages"].isEnabled()
    assert not workspace.actions["redact"].isEnabled()
    assert not workspace.actions["digital_sign"].isEnabled()

    def remove_metadata(dialog):
        assert dialog.owner.echoMode() == QLineEdit.EchoMode.Password
        dialog.owner.setText(supplied_owner)
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(MetadataDialog, "exec", remove_metadata)
    supplied_owner = user
    failed = tmp_path / "Bloqueado.pdf"
    message = _export(workspace, qtbot, monkeypatch, locked_tab, "metadata", failed, success=False)
    assert "senha de proprietário" in message and not list(tmp_path.glob("*.part.pdf"))
    supplied_owner = owner
    sanitized = tmp_path / "Protegido sem metadados.pdf"
    _export(workspace, qtbot, monkeypatch, locked_tab, "metadata", sanitized)
    with pdf.open(sanitized) as locked:
        assert locked.authenticate(user) == 2
        assert not locked.metadata["title"] and not locked.get_xml_metadata()
        assert locked.permissions & pdf.PDF_PERM_PRINT
        assert not locked.permissions & pdf.PDF_PERM_COPY
    assert protected.read_bytes() == protected_bytes and sample.read_bytes() == original
    workspace.save_settings()
    log = workspace.settings.path.read_bytes().decode("utf-8")
    details = " ".join(
        record.detail + (record.error or "") for record in workspace.jobs.list_tasks()
    )
    assert all(secret not in log and secret not in details for secret in (user, owner))


@pytest.mark.parametrize("permission", [0, pdf.PDF_PERM_MODIFY | pdf.PDF_PERM_ANNOTATE])
def test_legacy_encryption_uses_r2_edit_permissions(sample, tmp_path, permission):
    source = tmp_path / "PDF legado.pdf"
    with pdf.open(sample) as document:
        document.save(
            source,
            encryption=pdf.PDF_ENCRYPT_RC4_40,
            permissions=permission,
            user_pw="leitura-qa",
            owner_pw="proprietario-qa",
        )
    engine = PdfEngine()
    try:
        assert engine.open(str(source))["state"] == "password"
        info = engine.authenticate("leitura-qa")
        assert info["state"] == "open"
        assert info["can_organize"] is bool(permission)
        assert info["can_fill"] is bool(permission)
    finally:
        engine.close()


def test_t16_redaction_removes_pixels_text_and_original_objects(
    workspace, qtbot, monkeypatch, sample, tmp_path
):
    original = sample.read_bytes()
    tab = _tab(workspace, qtbot, sample)
    with pdf.open(sample) as source:
        page = source[1]
        rect = pdf.Rect(page.get_text("words")[0][:4]) * page.rotation_matrix
        second_area = (
            (rect.x0 - 7) / page.rect.width,
            (rect.y0 - 7) / page.rect.height,
            (rect.x1 + 7) / page.rect.width,
            (rect.y1 + 7) / page.rect.height,
        )
    first_area = (0.08, 0.11, 0.73, 0.52)
    assert not workspace.actions["export_redaction"].isEnabled()
    workspace.actions["redact"].trigger()
    _select(qtbot, tab, first_area)
    assert len(tab.redactions) == 1 and "prévia" in tab.redaction_note.text()
    workspace.actions["unmark_redaction"].trigger()
    assert not tab.redactions
    workspace.actions["redact"].trigger()
    _select(qtbot, tab, first_area)
    tab.navigate(1)
    qtbot.waitUntil(lambda: tab.canvas.page == 1 and tab.canvas.has_page, timeout=12000)
    workspace.actions["rotate"].trigger()
    qtbot.waitUntil(lambda: tab.canvas.rotation == 90, timeout=12000)
    workspace.actions["redact"].trigger()
    _select(qtbot, tab, second_area)
    assert [mark.page for mark in tab.redactions] == [0, 1]

    def review(dialog):
        assert not dialog.proceed.isEnabled()
        assert dialog.findChild(QPlainTextEdit).toPlainText() == "1, 2"
        assert any("150 DPI" in label.text() for label in dialog.findChildren(QLabel))
        dialog.acknowledge.setChecked(True)
        assert dialog.proceed.isEnabled()
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(RedactionReviewDialog, "exec", review)
    destination = tmp_path / "Redação final.pdf"
    _export(workspace, qtbot, monkeypatch, tab, "export_redaction", destination)
    report = workspace.jobs.list_tasks()[-1]
    assert report.state is TaskState.SUCCEEDED and "auditada" in report.detail

    with pdf.open(sample) as before, pdf.open(destination) as after:
        assert len(after) == 2
        assert not after.get_xml_metadata() and not after.is_form_pdf and not after.embfile_count()
        assert not after.get_toc() and after.xref_get_key(-1, "Prev")[0] == "null"
        assert after.xref_get_key(-1, "Info")[0] == "null"
        for index, mark in enumerate(tab.redactions):
            page = after[index]
            assert page.rect == before[index].rect
            assert not page.get_text() and not page.get_fonts() and not page.get_links()
            assert page.first_annot is None and page.first_widget is None
            [(xref, *_)] = page.get_images()
            bitmap = pdf.Pixmap(after, xref)
            rendered = page.get_pixmap(dpi=REDACTION_DPI)
            width, height = bitmap.width, bitmap.height
            x0, y0, x1, y1 = mark.region
            left, right = round(width * x0), round(width * x1)
            top, bottom = round(height * y0), round(height * y1)
            for raster in (bitmap, rendered):
                pixels = raster.samples
                for y in range(top, bottom):
                    assert not pixels[
                        y * raster.stride + left * 3 : y * raster.stride + right * 3
                    ].strip(b"\0")
            source_pixmap = before[index].get_pixmap(dpi=REDACTION_DPI)
            assert source_pixmap.pixel((left + right) // 2, (top + bottom) // 2) != (0, 0, 0)
        assert after[0].get_pixmap(dpi=150).pixel(620, 450) == (0, 191, 0)
        decoded = b" ".join(
            after.xref_stream(xref) or b"" for xref in range(1, after.xref_length())
        )
        for marker in (b"SEGREDO", b"_QA", b"OpenAction", b"/EmbeddedFiles", b"/JavaScript"):
            assert marker not in destination.read_bytes() and marker not in decoded
    assert sample.read_bytes() == original and tab.viewer.revision == 0


def test_m5_redaction_cancels_publication_and_clears_marks_after_edit(
    workspace, qtbot, monkeypatch, sample, tmp_path
):
    tab = _tab(workspace, qtbot, sample)
    workspace.actions["redact"].trigger()
    _select(qtbot, tab, (0.1, 0.1, 0.7, 0.45))
    assert tab.redactions
    cancelled = []

    def cancel_at_progress():
        task = tab.viewer.output
        if (
            task
            and not cancelled
            and task.jobs.status(task.task_id).detail.startswith("Rasterizando")
        ):
            cancelled.append(task.task_id)
            tab.viewer.cancel_export()

    monkeypatch.setattr(RedactionReviewDialog, "exec", lambda self: QDialog.DialogCode.Accepted)
    workspace.pdf_workspace.jobs_changed.connect(cancel_at_progress)
    destination = tmp_path / "Cancelado.pdf"
    message = _export(
        workspace, qtbot, monkeypatch, tab, "export_redaction", destination, success=False
    )
    assert "cancelada" in message.lower() and cancelled and not list(tmp_path.glob("*.part.pdf"))
    assert tab.redactions
    tab.viewer.change("rotate_pages", {"ranges": [(0, 0)], "angle": 90})
    qtbot.waitUntil(lambda: tab.viewer.revision == 1 and not tab.viewer.busy, timeout=12000)
    assert not tab.redactions and not workspace.actions["export_redaction"].isEnabled()


@pytest.mark.parametrize("input_type", ["drawing", "image"])
def test_t17_visual_signature_keeps_warning_and_appearance(
    workspace, qtbot, monkeypatch, sample, tmp_path, input_type
):
    tab = _tab(workspace, qtbot, sample)
    assert "não tem verificação criptográfica" in workspace.actions["visual_sign"].toolTip()

    def sign(dialog):
        assert (
            "não tem verificação criptográfica"
            in dialog.findChild(QLabel, "visual_signature_warning").text()
        )
        assert not dialog.proceed.isEnabled()
        if input_type == "drawing":
            qtbot.mousePress(dialog.pad, Qt.MouseButton.LeftButton, pos=QPointF(30, 80).toPoint())
            qtbot.mouseMove(dialog.pad, QPointF(110, 40).toPoint())
            qtbot.mouseRelease(
                dialog.pad, Qt.MouseButton.LeftButton, pos=QPointF(205, 90).toPoint()
            )
        else:
            image = pdf.Pixmap(pdf.csRGB, pdf.IRect(0, 0, 100, 30), False)
            image.set_rect(image.irect, (5, 38, 90))
            path = tmp_path / "assinatura fictícia.png"
            image.save(path)
            monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a, **k: (str(path), ""))
            dialog.tabs.setCurrentIndex(1)
            dialog._choose()
        assert dialog.proceed.isEnabled()
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(VisualSignatureDialog, "exec", sign)
    workspace.actions["visual_sign"].trigger()
    _select(qtbot, tab, (0.19, 0.62, 0.58, 0.76))
    qtbot.waitUntil(lambda: tab.viewer.revision == 1 and not tab.viewer.busy, timeout=12000)
    qtbot.waitUntil(lambda: any(a.kind == "visual_signature" for a in tab.viewer.annotations))
    output = tmp_path / f"Assinatura visual {input_type}.pdf"
    _export(workspace, qtbot, monkeypatch, tab, "save_as", output)
    with pdf.open(output) as result:
        assert result.get_sigflags() <= 0
        first = result[0]
        signature = next(
            a
            for a in first.annots()
            if a.info.get("subject") == "Old School PDF: assinatura visual"
        )
        area = signature.rect
        assert not area.is_empty
        assert (
            first.get_pixmap(clip=area).samples != first.get_pixmap(clip=area, annots=False).samples
        )


@pytest.fixture
def signing_files(tmp_path):
    pytest.importorskip("pyhanko")
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives.serialization import pkcs12

    now = datetime.now(UTC)
    ca_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    user_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    root_name = x509.Name(
        [x509.NameAttribute(x509.NameOID.COMMON_NAME, "Raiz fictícia Old School PDF QA")]
    )
    user_name = x509.Name([x509.NameAttribute(x509.NameOID.COMMON_NAME, "Pessoa fictícia QA")])

    def builder(name, public_key, *, ca):
        return (
            x509.CertificateBuilder()
            .subject_name(name)
            .issuer_name(root_name)
            .public_key(public_key)
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - timedelta(days=2))
            .not_valid_after(now + timedelta(days=2))
            .add_extension(x509.BasicConstraints(ca=ca, path_length=None), critical=True)
        )

    root = builder(root_name, ca_key.public_key(), ca=True).sign(ca_key, hashes.SHA256())
    certificate = (
        builder(user_name, user_key.public_key(), ca=False)
        .add_extension(
            x509.KeyUsage(True, True, False, False, False, False, False, False, False),
            critical=True,
        )
        .add_extension(
            x509.AuthorityInformationAccess(
                [
                    x509.AccessDescription(
                        x509.AuthorityInformationAccessOID.OCSP,
                        x509.UniformResourceIdentifier("https://example.invalid/ocsp"),
                    ),
                ]
            ),
            critical=False,
        )
        .sign(ca_key, hashes.SHA256())
    )
    p12, cer = tmp_path / "assinante-teste.p12", tmp_path / "raiz-teste.cer"
    p12.write_bytes(
        pkcs12.serialize_key_and_certificates(
            b"QA", user_key, certificate, [root], serialization.BestAvailableEncryption(b"senha-qa")
        )
    )
    cer.write_bytes(root.public_bytes(serialization.Encoding.DER))
    return p12, cer


@pytest.mark.qt_log_ignore(r"^This plugin does not support propagateSizeHints\(\)$")
def test_m5_digital_signature_local_trust_coverage_and_tampering(
    workspace, qtbot, monkeypatch, sample, signing_files, tmp_path
):
    p12, root = signing_files
    original = sample.read_bytes()
    tab = _tab(workspace, qtbot, sample)

    def choose(dialog):
        monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a, **k: (str(p12), ""))
        dialog._choose()
        assert dialog.passphrase.echoMode() == QLineEdit.EchoMode.Password
        dialog.passphrase.setText(passphrase)
        assert dialog.proceed.isEnabled()
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(SignDialog, "exec", choose)
    passphrase = "incorreta"
    _export(
        workspace, qtbot, monkeypatch, tab, "digital_sign", tmp_path / "Inválido.pdf", success=False
    )
    passphrase = "senha-qa"
    signed = tmp_path / "Assinado localmente.pdf"
    _export(workspace, qtbot, monkeypatch, tab, "digital_sign", signed)
    signed_tab = _tab(workspace, qtbot, signed)
    assert signed_tab.viewer.info.signed and not workspace.actions["digital_sign"].isEnabled()

    def roots(dialog):
        monkeypatch.setattr(QFileDialog, "getOpenFileNames", lambda *a, **k: ([str(root)], ""))
        dialog._choose()
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(TrustDialog, "exec", roots)
    with qtbot.waitSignal(signed_tab.viewer.signatures_ready, timeout=20000) as result:
        workspace.actions["verify_signatures"].trigger()
    [trusted] = result.args[0]
    assert trusted["intact"] and trusted["valid"] and trusted["trusted"]
    assert trusted["coverage"] == "ENTIRE_FILE" and len(trusted["fingerprint"]) == 64
    report = workspace.findChild(SignatureReportDialog)
    assert "Arquivo completo" in report.findChild(QPlainTextEdit).toPlainText()
    report.close()

    real_connect = socket.socket.connect
    real_connect_ex = socket.socket.connect_ex
    attempts = []

    def offline(function):
        def connect(sock, address):
            # asyncio usa um par de sockets de loopback no Windows.
            if isinstance(address, tuple) and address[0] in {"127.0.0.1", "::1"}:
                return function(sock, address)
            attempts.append(address)
            raise AssertionError("Conexão externa bloqueada durante o teste")

        return connect

    def no_dns(*args, **kwargs):
        attempts.append(args)
        raise AssertionError("DNS bloqueado durante o teste")

    monkeypatch.setattr(socket.socket, "connect", offline(real_connect))
    monkeypatch.setattr(socket.socket, "connect_ex", offline(real_connect_ex))
    monkeypatch.setattr(socket, "getaddrinfo", no_dns)
    [unknown] = signature_report(signed, [])
    assert unknown["intact"] and unknown["valid"] and not unknown["trusted"]
    assert signature_report(signed, [str(root)])[0]["trusted"]
    changed = tmp_path / "Assinatura adulterada.pdf"
    signed_bytes = signed.read_bytes()
    assert b"AUTOR_PRESERVAR_QA" in signed_bytes
    changed.write_bytes(signed_bytes.replace(b"AUTOR_PRESERVAR_QA", b"AUTOR_ALTERADO__QA", 1))
    assert changed.stat().st_size == signed.stat().st_size
    [altered] = signature_report(changed, [str(root)])
    assert not altered["intact"]
    appended = tmp_path / "Revisão posterior.pdf"
    appended.write_bytes(signed_bytes)
    with pdf.open(appended) as copy:
        copy[0].insert_text((80, 150), "REVISÃO SINTÉTICA")
        copy.saveIncr()
    [updated] = signature_report(appended, [str(root)])
    assert updated["intact"] and updated["coverage"] == "ENTIRE_REVISION"
    assert sample.read_bytes() == original and signed.read_bytes() == signed_bytes
    assert not attempts


def test_m5_unavailable_signing_does_not_offer_an_unusable_action(
    qtbot, monkeypatch, tmp_path, sample
):
    from oldschoolpdf.infrastructure.dependency_probe import LocalDependencyProbe

    original = LocalDependencyProbe.package_version
    monkeypatch.setattr(
        LocalDependencyProbe,
        "package_version",
        lambda self, name: None if name == "pyhanko" else original(self, name),
    )
    window = create_window(tmp_path / "sem-extra.ini")
    qtbot.addWidget(window)
    window.show()
    _tab(window, qtbot, sample)
    for key in ("digital_sign", "verify_signatures"):
        assert not window.actions[key].isEnabled()
        assert "signing" in window.actions[key].toolTip()
    assert window.actions["visual_sign"].isEnabled()
    assert window.close()
