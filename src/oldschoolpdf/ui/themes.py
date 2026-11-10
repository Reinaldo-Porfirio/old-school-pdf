"""Tema Clássico 2000: estilo nativo "Windows" do Qt, paleta cinza e relevo 3D."""

from PySide6.QtGui import QColor, QFont, QPalette
from PySide6.QtWidgets import QApplication

from oldschoolpdf.application.preferences import THEME_NAMES

# Cores do sistema no visual clássico do Windows 2000.
CLASSIC = {
    "face": "#d4d0c8",
    "highlight_3d": "#ffffff",
    "light_3d": "#e4e1da",
    "mid": "#b0aca4",
    "shadow": "#808080",
    "dark_shadow": "#404040",
    "base": "#ffffff",
    "alternate": "#f4f3ee",
    "text": "#000000",
    "disabled": "#808080",
    "selection": "#0a246a",
    "caption_start": "#0a246a",
    "caption_end": "#a6caf0",
    "inactive_start": "#808080",
    "inactive_end": "#c0c0c0",
    "tooltip": "#ffffe1",
    "link": "#0000ee",
    "canvas": "#808080",
}

STYLE_NAME = "Windows"
FONT_FAMILY = "Tahoma"
FONT_POINTS = 8


def classic_palette() -> QPalette:
    c = CLASSIC
    palette = QPalette()
    roles = {
        QPalette.ColorRole.Window: c["face"],
        QPalette.ColorRole.WindowText: c["text"],
        QPalette.ColorRole.Base: c["base"],
        QPalette.ColorRole.AlternateBase: c["alternate"],
        QPalette.ColorRole.Text: c["text"],
        QPalette.ColorRole.Button: c["face"],
        QPalette.ColorRole.ButtonText: c["text"],
        QPalette.ColorRole.BrightText: "#ffffff",
        QPalette.ColorRole.Highlight: c["selection"],
        QPalette.ColorRole.HighlightedText: "#ffffff",
        QPalette.ColorRole.ToolTipBase: c["tooltip"],
        QPalette.ColorRole.ToolTipText: c["text"],
        QPalette.ColorRole.Link: c["link"],
        QPalette.ColorRole.LinkVisited: "#551a8b",
        QPalette.ColorRole.PlaceholderText: c["disabled"],
        QPalette.ColorRole.Light: c["highlight_3d"],
        QPalette.ColorRole.Midlight: c["light_3d"],
        QPalette.ColorRole.Mid: c["mid"],
        QPalette.ColorRole.Dark: c["shadow"],
        QPalette.ColorRole.Shadow: c["dark_shadow"],
    }
    for role, color in roles.items():
        palette.setColor(role, QColor(color))
    for role in (
        QPalette.ColorRole.Text,
        QPalette.ColorRole.WindowText,
        QPalette.ColorRole.ButtonText,
    ):
        # O estilo Windows desenha o texto desabilitado em baixo-relevo com a cor Light.
        palette.setColor(QPalette.ColorGroup.Disabled, role, QColor(c["disabled"]))
    palette.setColor(
        QPalette.ColorGroup.Inactive, QPalette.ColorRole.Highlight, QColor(c["selection"])
    )
    return palette


def classic_stylesheet() -> str:
    c = CLASSIC
    caption = (
        f"qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {c['caption_start']}, "
        f"stop:1 {c['caption_end']})"
    )
    # Só o que o estilo nativo não desenha: títulos de painéis, tela do PDF e etiquetas.
    return f"""
        QGraphicsView#pdf_canvas {{ background: {c["canvas"]}; }}
        QDockWidget {{ font-weight: bold; color: #ffffff; }}
        QDockWidget::title {{ background: {caption}; padding: 3px 4px; text-align: left; }}
        QToolTip {{ background: {c["tooltip"]}; color: #000000; border: 1px solid #000000;
                    padding: 2px; }}
        QLabel[role='muted'] {{ color: #404040; }}
        QFrame[role='workspaceHeader'] {{ background: {caption}; }}
        QFrame[role='workspaceHeader'] QLabel {{ color: #ffffff; background: transparent; }}
        QLabel[role='badge'] {{ background: {c["selection"]}; color: #ffffff; padding: 2px 7px;
                               font-weight: bold; }}
    """


def apply_theme(app: QApplication, name: str) -> None:
    if name not in THEME_NAMES:
        raise ValueError("Tema desconhecido.")
    # O estilo "Windows" do Qt é o visual clássico; Fusion fica como reserva.
    style = app.setStyle(STYLE_NAME) or app.setStyle("Fusion")
    app.setProperty("oldschoolpdfStyle", style.name() if style else "")
    app.setFont(QFont(FONT_FAMILY, FONT_POINTS))
    app.setPalette(classic_palette())
    app.setStyleSheet(classic_stylesheet())
    app.setProperty("oldschoolpdfTheme", name)
