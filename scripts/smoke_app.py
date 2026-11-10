"""Smoke Qt nativo em processo separado com INI temporário e imagens do tema."""

import json
import platform
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

from PySide6.QtCore import QTimer, QtMsgType, qInstallMessageHandler, qVersion
from PySide6.QtWidgets import QApplication

from oldschoolpdf.app import configure_application, create_window
from oldschoolpdf.application.preferences import DEFAULT_THEME

evidence = Path(__file__).resolve().parents[1] / "docs" / "evidence"
evidence.mkdir(parents=True, exist_ok=True)
messages = []
failures = []
windows = []


def message_handler(kind, context, message):
    if kind in (QtMsgType.QtWarningMsg, QtMsgType.QtCriticalMsg, QtMsgType.QtFatalMsg):
        messages.append(message)


qInstallMessageHandler(message_handler)
app = QApplication([])
configure_application(app)
app.setQuitOnLastWindowClosed(False)
scratch = TemporaryDirectory(prefix="oldschoolpdf-m0-smoke-")
settings_path = Path(scratch.name) / "settings.ini"
first = create_window(settings_path)
windows.append(first)
first.show()


def restored_window():
    try:
        fresh = windows[-1]
        assert fresh.layout_restored
        assert fresh.preferences.theme == DEFAULT_THEME
        assert fresh.preferences.text_under_icons
        assert fresh.navigation_dock.isHidden()
        assert fresh.tabs.count() == 1
        assert fresh.jobs_dock.tree.topLevelItemCount() == 0
        assert fresh.close()
    except Exception as error:
        failures.append(repr(error))
    app.quit()


def text_under_icons():
    try:
        assert first.grab().save(str(evidence / "classico-2000-texto.png"))
        first.navigation_dock.hide()
        assert first.close()
        fresh = create_window(settings_path)
        windows.append(fresh)
        fresh.show()
        QTimer.singleShot(300, restored_window)
    except Exception as error:
        failures.append(repr(error))
        app.quit()


def classic():
    try:
        assert first.isVisible()
        assert app.property("oldschoolpdfTheme") == DEFAULT_THEME
        assert first.grab().save(str(evidence / "classico-2000.png"))
        first.open_page("guide")
        first.open_page("capabilities")
        first.open_page("home")
        first.text_action.trigger()
        QTimer.singleShot(300, text_under_icons)
    except Exception as error:
        failures.append(repr(error))
        app.quit()


QTimer.singleShot(300, classic)
QTimer.singleShot(15000, app.quit)
app.exec()
result = {
    "platform": platform.platform(),
    "python": sys.version,
    "qt": qVersion(),
    "platform_plugin": app.platformName(),
    "qt_warnings_or_errors": messages,
    "failures": failures,
    "round_trip_completed": len(windows) == 2 and windows[-1].layout_restored,
}
(evidence / "smoke.json").write_text(
    json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
)
print(json.dumps(result, ensure_ascii=False, indent=2))
scratch.cleanup()
raise SystemExit(0 if not failures and not messages and result["round_trip_completed"] else 1)
