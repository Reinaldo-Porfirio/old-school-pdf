from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import QDialog, QMessageBox

from docforge.application.preferences import Preferences
from docforge.domain.errors import SettingsError
from docforge.ui.dialogs import PreferencesDialog


def test_preferences_accept_and_cancel_are_distinct(window, qtbot):
    dialog = PreferencesDialog(window.preferences, str(window.settings.path), window)
    qtbot.addWidget(dialog)
    dialog.theme_combo.setCurrentText("Graphite Pro")
    dialog.accept()
    assert dialog.result() == QDialog.DialogCode.Accepted
    assert dialog.preferences().theme == "Graphite Pro"
    assert window.preferences.theme == "Classic Light"
    rejected = PreferencesDialog(window.preferences, str(window.settings.path), window)
    qtbot.addWidget(rejected)
    rejected.reject()
    assert rejected.result() == QDialog.DialogCode.Rejected


def test_duplicate_shortcuts_prevent_acceptance(window, qtbot, monkeypatch):
    dialog = PreferencesDialog(Preferences(), str(window.settings.path), window)
    qtbot.addWidget(dialog)
    warnings = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *args: warnings.append(args))
    dialog.shortcut_editors["home"].setKeySequence(QKeySequence("F1"))
    dialog.accept()
    assert warnings
    assert dialog.result() != QDialog.DialogCode.Accepted
    dialog._reset_shortcuts()
    dialog.accept()
    assert dialog.result() == QDialog.DialogCode.Accepted


def test_preferences_action_commits_only_accepted_dialog(window, monkeypatch):
    def accept(dialog):
        dialog.theme_combo.setCurrentText("Graphite Pro")
        return QDialog.DialogCode.Accepted

    with monkeypatch.context() as patch:
        patch.setattr(PreferencesDialog, "exec", accept)
        window.actions["preferences"].trigger()
    assert window.preferences.theme == "Graphite Pro"
    assert window.settings.load_preferences().theme == "Graphite Pro"
    with monkeypatch.context() as patch:
        patch.setattr(PreferencesDialog, "exec", lambda dialog: QDialog.DialogCode.Rejected)
        window.show_preferences()
    assert window.preferences.theme == "Graphite Pro"


def test_save_error_is_shown_and_close_can_be_cancelled(window, monkeypatch):
    def fail(*args):
        raise SettingsError("Erro de gravação de teste")

    warnings = []
    with monkeypatch.context() as patch:
        patch.setattr(window.settings, "save", fail)
        patch.setattr(QMessageBox, "warning", lambda *args: warnings.append(args))
        window.change_theme("Graphite Pro")
        assert warnings
        patch.setattr(QMessageBox, "exec", lambda dialog: QMessageBox.StandardButton.Cancel)
        assert not window.close()
        assert window.isVisible()
    assert window.close()


def test_save_error_close_can_explicitly_discard_preferences(window, monkeypatch):
    def fail(*args):
        raise SettingsError("Erro de gravação de teste")

    with monkeypatch.context() as patch:
        patch.setattr(window.settings, "save", fail)
        patch.setattr(QMessageBox, "exec", lambda dialog: QMessageBox.StandardButton.Discard)
        assert window.close()
