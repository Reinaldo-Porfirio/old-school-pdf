"""Ícones originais em SVG, renderizados localmente; sem assets externos."""

from functools import lru_cache

from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

from oldschoolpdf.ui.icon_art import LOGO, svg_for

SIZES = (16, 20, 24, 32, 48, 64)


def _render(svg: str, sizes: tuple[int, ...] = SIZES) -> QIcon:
    renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
    icon = QIcon()
    for size in sizes:
        image = QPixmap(size, size)
        image.fill(Qt.GlobalColor.transparent)
        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        renderer.render(painter)
        painter.end()
        icon.addPixmap(image)
    return icon


@lru_cache(maxsize=128)
def command_icon(kind: str, color: str = "") -> QIcon:
    # `color` é mantido por compatibilidade; a arte do Clássico 2000 tem cores próprias.
    del color
    return _render(svg_for(kind))


@lru_cache(maxsize=1)
def app_icon() -> QIcon:
    return _render(LOGO, (16, 24, 32, 48, 64, 128, 256))
