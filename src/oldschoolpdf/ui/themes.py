"""Paletas completas, estilo Fusion e foco visível para dois temas desktop."""

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

from oldschoolpdf.application.preferences import THEME_NAMES

COLORS = {
    "Classic Light": {
        "window": "#edf1f6",
        "base": "#ffffff",
        "alternate": "#f1f5fa",
        "text": "#17283d",
        "muted": "#4d5e73",
        "button": "#e6ecf4",
        "accent": "#185a9d",
        "header": "#174c80",
        "border": "#b8c7d8",
        "disabled": "#657184",
        "canvas": "#d5dfe9",
        "hover": "#d7e8fa",
    },
    "Graphite Pro": {
        "window": "#252b34",
        "base": "#1b2028",
        "alternate": "#252d38",
        "text": "#edf2f8",
        "muted": "#bbc9da",
        "button": "#343e4d",
        "accent": "#397ec4",
        "header": "#293e59",
        "border": "#526177",
        "disabled": "#a1afc0",
        "canvas": "#151a21",
        "hover": "#394e68",
    },
}


def apply_theme(app: QApplication, name: str) -> None:
    if name not in THEME_NAMES:
        raise ValueError("Tema desconhecido.")
    c = COLORS[name]
    app.setStyle("Fusion")
    palette = QPalette()
    roles = {
        QPalette.ColorRole.Window: c["window"],
        QPalette.ColorRole.WindowText: c["text"],
        QPalette.ColorRole.Base: c["base"],
        QPalette.ColorRole.AlternateBase: c["alternate"],
        QPalette.ColorRole.Text: c["text"],
        QPalette.ColorRole.Button: c["button"],
        QPalette.ColorRole.ButtonText: c["text"],
        QPalette.ColorRole.Highlight: c["accent"],
        QPalette.ColorRole.HighlightedText: "#ffffff",
        QPalette.ColorRole.ToolTipBase: c["base"],
        QPalette.ColorRole.ToolTipText: c["text"],
        QPalette.ColorRole.Link: "#2376c4" if name == "Classic Light" else "#9ccaff",
        QPalette.ColorRole.PlaceholderText: c["muted"],
        QPalette.ColorRole.Light: c["border"],
        QPalette.ColorRole.Mid: c["border"],
        QPalette.ColorRole.Dark: c["canvas"],
    }
    for role, color in roles.items():
        palette.setColor(role, QColor(color))
    for role in (
        QPalette.ColorRole.Text,
        QPalette.ColorRole.WindowText,
        QPalette.ColorRole.ButtonText,
    ):
        palette.setColor(QPalette.ColorGroup.Disabled, role, QColor(c["disabled"]))
    app.setPalette(palette)
    app.setStyleSheet(f"""
        QMainWindow {{ background: {c["canvas"]}; }}
        QGraphicsView#pdf_canvas {{ background: {c["canvas"]}; border: 1px solid {c["border"]}; }}
        QMenuBar {{ background: {c["header"]}; color: white; padding: 3px; }}
        QMenuBar::item {{ padding: 5px 10px; }}
        QMenuBar::item:selected {{ background: {c["accent"]}; }}
        QMenu {{ border: 1px solid {c["border"]}; padding: 4px; }}
        QMenu::item {{ padding: 6px 28px 6px 12px; }}
        QMenu::item:selected {{ background: {c["accent"]}; color: white; }}
        QToolBar {{ border: 1px solid {c["border"]}; spacing: 4px; padding: 4px; }}
        QToolButton {{ padding: 5px; border: 1px solid transparent; border-radius: 2px; }}
        QToolButton:hover {{ background: {c["hover"]}; border-color: {c["border"]}; }}
        QToolButton:checked {{ background: {c["hover"]}; border-color: {c["accent"]}; }}
        QDockWidget::title {{ background: {c["header"]}; color: white; padding: 7px; }}
        QDockWidget {{ font-weight: 600; color: white; }}
        QTabWidget::pane {{ border: 1px solid {c["border"]}; }}
        QTabBar::tab {{ padding: 7px 12px; background: {c["button"]};
                       border: 1px solid {c["border"]}; }}
        QTabBar::tab:selected {{ background: {c["base"]}; border-bottom: 2px solid {c["accent"]}; }}
        QHeaderView::section {{ background: {c["button"]}; padding: 6px;
                               border: 1px solid {c["border"]}; font-weight: 600; }}
        QTreeWidget, QTextBrowser {{ background: {c["base"]}; }}
        QTreeWidget::item {{ padding: 4px; }}
        QGroupBox {{ border: 1px solid {c["border"]}; margin-top: 12px;
                     padding: 12px 8px 8px; font-weight: 600; }}
        QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 4px; }}
        QPushButton {{ padding: 6px 12px; min-height: 20px; }}
        QPushButton:default {{ border: 2px solid {c["accent"]}; }}
        QPushButton:focus, QToolButton:focus, QComboBox:focus, QKeySequenceEdit:focus,
        QTabBar:focus, QTreeWidget:focus {{ border: 2px solid {c["accent"]}; }}
        QComboBox {{ padding: 4px; min-height: 22px; }}
        QStatusBar {{ background: {c["window"]}; border-top: 1px solid {c["border"]}; }}
        QStatusBar::item {{ border: none; }}
        QLabel[role='muted'] {{ color: {c["muted"]}; }}
        QFrame[role='workspaceHeader'] {{ background: {c["header"]}; }}
        QFrame[role='workspaceHeader'] QLabel {{ color: white; }}
        QLabel[role='badge'] {{ background: {c["accent"]}; color: white;
                              padding: 5px 9px; border-radius: 2px; }}
        QScrollArea {{ border: none; }}
    """)
    app.setProperty("oldschoolpdfTheme", name)
