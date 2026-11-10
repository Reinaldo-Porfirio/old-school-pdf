import ast
import os
import socket
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import QMimeData, QPointF, Qt, QUrl
from PySide6.QtGui import QDragEnterEvent
from PySide6.QtWidgets import QApplication

from oldschoolpdf.app import create_window
from oldschoolpdf.infrastructure.settings_repository import SettingsRepository


def test_runtime_sources_have_no_network_pdf_or_process_execution_in_ui():
    source = Path(__file__).resolve().parents[2] / "src" / "oldschoolpdf"
    banned = {"requests", "httpx", "urllib", "socket", "webbrowser", "subprocess"}
    for path in source.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name.split(".")[0] for alias in node.names)
            if isinstance(node, ast.ImportFrom) and node.module:
                imports.append(node.module.split(".")[0])
        assert not banned.intersection(imports), path
        if "ui" in path.parts:
            assert not {"pymupdf", "fitz", "pikepdf"}.intersection(imports), path
        if "domain" in path.parts:
            assert "PySide6" not in imports, path


def test_startup_diagnostics_and_remote_drops_do_not_use_network_or_spawn(
    qtbot, monkeypatch, tmp_path
):
    def forbidden(*args, **kwargs):
        raise AssertionError("Chamada externa não autorizada")

    with monkeypatch.context() as patch:
        patch.setattr(subprocess, "Popen", forbidden)
        patch.setattr(socket, "create_connection", forbidden)
        patch.setattr(socket, "getaddrinfo", forbidden)
        fresh = create_window(tmp_path / "isolated.ini")
        qtbot.addWidget(fresh)
        fresh.show()
        page = fresh.open_page("capabilities")
        page.refresh()
        assert page.tree.topLevelItemCount() == 7
        mime = QMimeData()
        mime.setUrls(
            [QUrl("https://example.invalid/remoto.pdf"), QUrl("file://servidor/pasta/remoto.pdf")]
        )
        event = QDragEnterEvent(
            QPointF(20, 20),
            Qt.DropAction.CopyAction,
            mime,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        QApplication.sendEvent(fresh, event)
        assert not event.isAccepted()
        assert fresh.close()


def test_module_entrypoint_version_runs_in_a_separate_process():
    environment = {**os.environ, "PYTHONUTF8": "1"}
    result = subprocess.run(
        [sys.executable, "-m", "oldschoolpdf", "--version"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=20,
        env=environment,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "0.6.1"
    assert result.stderr == ""


def test_module_starts_real_gui_and_saves_layout_in_separate_process(tmp_path):
    settings_path = tmp_path / "processo separado ç 漢字.ini"
    environment = {**os.environ, "PYTHONUTF8": "1"}
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "oldschoolpdf",
            "--settings-file",
            str(settings_path),
            "--smoke-test",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=20,
        env=environment,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout == result.stderr == ""
    assert SettingsRepository(settings_path).load_layout() is not None
