from dataclasses import replace

import pytest
from PySide6.QtCore import QByteArray, QSettings

from oldschoolpdf.application.preferences import DEFAULT_THEME, Preferences
from oldschoolpdf.domain.errors import SettingsError
from oldschoolpdf.infrastructure.settings_repository import (
    SETTINGS_ID,
    SettingsRepository,
    WindowLayout,
)


def test_preferences_and_binary_layout_survive_new_repository(tmp_path):
    path = tmp_path / "pasta com espaços 漢字" / "config.ini"
    prefs = replace(Preferences(), theme=DEFAULT_THEME, icon_size=32, text_under_icons=True)
    layout = WindowLayout(QByteArray(b"geometry\x00\xff"), QByteArray(b"state\x00\x80"))
    SettingsRepository(path).save(prefs, layout)
    fresh = SettingsRepository(path)
    assert fresh.load_preferences() == prefs
    assert fresh.load_layout() == layout


def test_first_start_has_defaults_and_does_not_create_a_file_on_read(tmp_path):
    repo = SettingsRepository(tmp_path / "new.ini")
    assert repo.load_preferences() == Preferences()
    assert repo.load_layout() is None
    assert not repo.path.exists()


@pytest.mark.parametrize(
    "key,value",
    [
        ("preferences/icon_size", "invalid-number"),
        ("preferences/shortcuts", "{not json}"),
        ("preferences/shortcuts", '["wrong-type"]'),
        ("preferences/shortcuts", '{"home":"F1"}'),
        ("preferences/shortcuts", '{"home":"Ctrl+NoSuchKey"}'),
        ("preferences/shortcuts", '{"home":"Ctrl+K, Ctrl+H"}'),
    ],
)
def test_bad_preferences_are_reported_with_safe_defaults(tmp_path, key, value):
    path = tmp_path / "invalid.ini"
    settings = QSettings(str(path), QSettings.Format.IniFormat)
    settings.setValue("application/id", SETTINGS_ID)
    settings.setValue(key, value)
    settings.sync()
    repo = SettingsRepository(path)
    assert repo.load_preferences() == Preferences()
    assert repo.warnings


@pytest.mark.parametrize("theme", ["Classic Light", "Graphite Pro", "unknown-theme"])
def test_removed_or_unknown_theme_falls_back_without_losing_other_preferences(tmp_path, theme):
    path = tmp_path / "old-theme.ini"
    settings = QSettings(str(path), QSettings.Format.IniFormat)
    settings.setValue("application/id", SETTINGS_ID)
    settings.setValue("preferences/theme", theme)
    settings.setValue("preferences/icon_size", 32)
    settings.sync()
    repo = SettingsRepository(path)
    loaded = repo.load_preferences()
    assert loaded.theme == DEFAULT_THEME
    assert loaded.icon_size == 32
    assert not repo.warnings


@pytest.mark.parametrize("version", ["invalid", 999, 0])
def test_invalid_or_future_layout_version_is_ignored(tmp_path, version):
    path = tmp_path / "layout.ini"
    settings = QSettings(str(path), QSettings.Format.IniFormat)
    settings.setValue("application/id", SETTINGS_ID)
    settings.setValue("layout/version", version)
    settings.sync()
    assert SettingsRepository(path).load_layout() is None


def test_real_write_failure_is_not_silent(tmp_path):
    parent_is_a_file = tmp_path / "not-a-directory"
    parent_is_a_file.write_bytes(b"Preserved parent file")
    repo = SettingsRepository(parent_is_a_file / "settings.ini")
    with pytest.raises(SettingsError, match="Não foi possível"):
        repo.save(Preferences(), WindowLayout(QByteArray(), QByteArray()))
    assert parent_is_a_file.read_bytes() == b"Preserved parent file"


@pytest.mark.parametrize("filename", ["documento.pdf", "outro-programa.ini"])
def test_settings_never_replaces_an_unowned_user_file(tmp_path, filename):
    path = tmp_path / filename
    content = b"%PDF-1.7\nUser-owned bytes: do not replace with settings.\n"
    path.write_bytes(content)
    repo = SettingsRepository(path)
    assert repo.load_preferences() == Preferences()
    assert repo.warnings
    assert repo.load_layout() is None
    with pytest.raises(SettingsError, match="foi preservado"):
        repo.save(Preferences(), WindowLayout(QByteArray(), QByteArray()))
    assert path.read_bytes() == content
