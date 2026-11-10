"""Preferências locais da janela e do visualizador."""

from dataclasses import dataclass, field

VIEWER_SHORTCUTS = {
    "open": "Ctrl+O",
    "find": "Ctrl+F",
    "copy": "Ctrl+C",
    "zoom_in": "Ctrl++",
    "zoom_out": "Ctrl+-",
    "page_next": "PgDown",
    "page_previous": "PgUp",
    "hit_next": "F3",
    "hit_previous": "Shift+F3",
}

EDITOR_SHORTCUTS = {
    "save_as": "Ctrl+Shift+S",
    "undo": "Ctrl+Z",
    "redo": "Ctrl+Y",
    "redact": "Ctrl+Alt+R",
}

DEFAULT_SHORTCUTS = {
    "home": "Ctrl+1",
    "guide": "Ctrl+Shift+H",
    "capabilities": "Ctrl+Shift+D",
    "preferences": "Ctrl+,",
    "close_tab": "Ctrl+W",
    "next_tab": "Ctrl+Tab",
    "previous_tab": "Ctrl+Shift+Tab",
    "help": "F1",
    "quit": "Ctrl+Q",
    **VIEWER_SHORTCUTS,
    **EDITOR_SHORTCUTS,
}
DEFAULT_THEME = "Clássico 2000"
THEME_NAMES = (DEFAULT_THEME,)


@dataclass(frozen=True, slots=True)
class Preferences:
    theme: str = DEFAULT_THEME
    icon_size: int = 24
    text_under_icons: bool = False
    restore_layout: bool = True
    shortcuts: dict[str, str] = field(default_factory=lambda: dict(DEFAULT_SHORTCUTS))
    pdf_cache_mib: int = 64
    pdf_parallelism: int = 2
    ocr_tessdata: str = ""
    ocr_languages: tuple[str, ...] = ()
