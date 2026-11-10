"""Cada janela usa INI temporário; nenhum teste altera preferências do usuário."""

import os
import sys
from pathlib import Path

import pytest

from oldschoolpdf.app import configure_application, create_window

# O plugin offscreen não usa o catálogo de fontes nativo do Windows.
# Usar fontes já instaladas, sem baixar ou redistribuir fontes do sistema.
if sys.platform == "win32" and os.environ.get("QT_QPA_PLATFORM", "").startswith("offscreen"):
    os.environ.setdefault(
        "QT_QPA_FONTDIR", str(Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts")
    )


@pytest.fixture(scope="session", autouse=True)
def application_metadata(qapp):
    configure_application(qapp)


@pytest.fixture
def window(qtbot, tmp_path):
    widget = create_window(tmp_path / "settings.ini")
    qtbot.addWidget(widget)
    widget.show()
    qtbot.waitUntil(widget.isVisible)
    return widget
