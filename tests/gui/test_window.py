from dataclasses import replace

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import QDockWidget, QLabel, QMainWindow, QTabWidget, QToolBar

from docforge.app import create_window
from docforge.ui.main_window import FUTURE_COMMANDS


def test_real_window_has_classic_widgets_and_portuguese_menus(window):
    assert isinstance(window, QMainWindow)
    assert isinstance(window.centralWidget(), QTabWidget)
    assert len(window.findChildren(QDockWidget)) == 3
    assert len(window.findChildren(QToolBar)) == 3
    titles = [action.text().replace("&", "") for action in window.menuBar().actions()]
    assert titles == [
        "Arquivo",
        "Editar",
        "Exibir",
        "Documento",
        "Ferramentas",
        "OCR",
        "Segurança",
        "Janela",
        "Ajuda",
    ]
    assert window.tabs.tabText(0) == "Início"
    assert window.jobs_dock.tree.topLevelItemCount() == 0
    assert not window.jobs_dock.cancel_button.isEnabled()
    assert window.findChild(QLabel, "offline_status").text() == "Local / Offline"


@pytest.mark.parametrize("command", FUTURE_COMMANDS, ids=lambda command: command.key)
def test_every_future_action_is_disabled_and_explained(window, command):
    action = window.actions[command.key]
    assert not action.isEnabled()
    assert "futuro" in action.text()
    assert "Recurso futuro" in action.toolTip()
    before = window.tabs.count()
    action.trigger()
    assert window.tabs.count() == before


def test_tabs_open_once_close_reorder_and_window_menu_selects_widget(window, qtbot):
    guide = window.open_page("guide")
    capabilities = window.open_page("capabilities")
    window.open_page("guide")
    assert window.tabs.count() == 3
    window.tabs.tabBar().moveTab(2, 0)
    window._populate_window_menu()
    menu_action = next(a for a in window.window_menu.actions() if a.text() == "Recursos locais")
    menu_action.trigger()
    assert window.tabs.currentWidget() is capabilities
    window.tabs.setCurrentWidget(guide)
    qtbot.keyClick(window, Qt.Key.Key_W, Qt.KeyboardModifier.ControlModifier)
    qtbot.waitUntil(lambda: window.tabs.count() == 2)
    window.close_tab(window.tabs.indexOf(capabilities))
    window.close_current_tab()
    assert window.tabs.count() == 0
    assert not window.actions["close_tab"].isEnabled()
    window.actions["home"].trigger()
    assert window.tabs.count() == 1


def test_keyboard_shortcuts_work_with_toolbars_hidden(window, qtbot):
    for toolbar in window.toolbars:
        toolbar.hide()
    window.activateWindow()
    window.setFocus()
    qtbot.keyClick(window, Qt.Key.Key_F1)
    qtbot.waitUntil(lambda: window.tabs.currentWidget().property("page_key") == "guide")
    qtbot.keyClick(window, Qt.Key.Key_1, Qt.KeyboardModifier.ControlModifier)
    qtbot.waitUntil(lambda: window.tabs.currentWidget().property("page_key") == "home")
    qtbot.keyClick(window, Qt.Key.Key_Tab, Qt.KeyboardModifier.ControlModifier)
    qtbot.waitUntil(lambda: window.tabs.currentWidget().property("page_key") == "guide")


def test_themes_change_immediately_and_persist(window, qapp):
    before = qapp.palette().window().color().name()
    window.theme_actions["Graphite Pro"].trigger()
    assert qapp.property("docforgeTheme") == "Graphite Pro"
    assert qapp.palette().window().color().name() != before
    assert window.settings.load_preferences().theme == "Graphite Pro"
    window.theme_actions["Classic Light"].trigger()
    assert qapp.property("docforgeTheme") == "Classic Light"


def test_close_reopen_restores_geometry_docks_and_toolbar_visibility(window, qtbot):
    path = window.settings.path
    available = window.screen().availableGeometry()
    window.resize(
        max(window.minimumWidth(), min(1160, available.width() - 80)),
        max(window.minimumHeight(), min(780, available.height() - 80)),
    )
    window.move(35, 45)
    window.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, window.properties_dock)
    window.navigation_dock.hide()
    window.toolbars[1].hide()
    window.change_theme("Graphite Pro")
    original_size = window.size()
    assert window.close()
    fresh = create_window(path)
    qtbot.addWidget(fresh)
    fresh.show()
    qtbot.waitUntil(fresh.isVisible)
    assert fresh.layout_restored
    assert fresh.size() == original_size
    assert fresh.dockWidgetArea(fresh.properties_dock) == Qt.DockWidgetArea.LeftDockWidgetArea
    assert fresh.navigation_dock.isHidden()
    assert fresh.toolbars[1].isHidden()
    assert fresh.preferences.theme == "Graphite Pro"


def test_opt_out_of_layout_restore_and_reset_layout_are_real(window, qtbot):
    path = window.settings.path
    window.navigation_dock.hide()
    window.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, window.properties_dock)
    window.actions["reset_layout"].trigger()
    assert not window.navigation_dock.isHidden()
    assert not window.properties_dock.isFloating()
    assert window.dockWidgetArea(window.properties_dock) == Qt.DockWidgetArea.RightDockWidgetArea
    window.navigation_dock.hide()
    window.apply_preferences(replace(window.preferences, restore_layout=False))
    window.save_settings()
    fresh = create_window(path)
    qtbot.addWidget(fresh)
    fresh.show()
    assert not fresh.layout_restored
    assert not fresh.navigation_dock.isHidden()


def test_text_and_icon_size_preferences_apply_to_all_toolbars(window):
    window.apply_preferences(replace(window.preferences, icon_size=32, text_under_icons=True))
    assert all(bar.iconSize().width() == 32 for bar in window.toolbars)
    assert all(
        bar.toolButtonStyle() == Qt.ToolButtonStyle.ToolButtonTextUnderIcon
        for bar in window.toolbars
    )
    window.text_action.trigger()
    assert all(
        bar.toolButtonStyle() == Qt.ToolButtonStyle.ToolButtonTextBesideIcon
        for bar in window.toolbars
    )


def test_configurable_shortcut_is_installed_and_saved(window):
    prefs = replace(window.preferences, shortcuts={**window.preferences.shortcuts, "home": "Alt+H"})
    window.apply_preferences(prefs)
    window.save_settings()
    assert window.actions["home"].shortcut() == QKeySequence("Alt+H")
    assert window.settings.load_preferences().shortcuts["home"] == "Alt+H"


def test_native_floating_dock_restores_without_losing_it(window, qtbot, qapp):
    if qapp.platformName() == "offscreen":
        pytest.skip("Janelas flutuantes verificadas separadamente no plugin nativo do Windows")
    window.properties_dock.setFloating(True)
    assert window.properties_dock.isFloating()
    path = window.settings.path
    assert window.close()
    fresh = create_window(path)
    qtbot.addWidget(fresh)
    fresh.show()
    qtbot.waitUntil(fresh.isVisible)
    assert fresh.properties_dock.isFloating()
    fresh.actions["reset_layout"].trigger()
    assert not fresh.properties_dock.isFloating()
