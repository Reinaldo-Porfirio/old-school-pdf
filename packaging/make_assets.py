"""Gera o ícone .ico e as imagens do assistente de instalação a partir do logo SVG.

Uso: python packaging/make_assets.py <pasta-de-saída>
"""

import struct
import sys
from pathlib import Path

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QGuiApplication, QImage, QLinearGradient, QPainter
from PySide6.QtSvg import QSvgRenderer

from oldschoolpdf.ui.icon_art import LOGO

ICON_SIZES = (16, 20, 24, 32, 40, 48, 64, 128, 256)
NAVY = "#0a246a"
SKY = "#a6caf0"


def render_logo(size: int) -> QImage:
    image = QImage(size, size, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    QSvgRenderer(QByteArray(LOGO.encode("utf-8"))).render(painter)
    painter.end()
    return image


def png_bytes(image: QImage) -> bytes:
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buffer, "PNG")
    return bytes(buffer.data())


def write_ico(path: Path) -> None:
    # ICO com entradas PNG, aceito pelo Windows desde o Vista.
    images = [(size, png_bytes(render_logo(size))) for size in ICON_SIZES]
    header = struct.pack("<HHH", 0, 1, len(images))
    offset = len(header) + 16 * len(images)
    directory = b""
    payload = b""
    for size, data in images:
        side = 0 if size >= 256 else size
        directory += struct.pack("<BBBBHHII", side, side, 0, 0, 1, 32, len(data), offset)
        offset += len(data)
        payload += data
    path.write_bytes(header + directory + payload)


def gradient_painter(image: QImage, vertical: bool) -> QPainter:
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    end = (0, image.height()) if vertical else (image.width(), 0)
    gradient = QLinearGradient(0, 0, *end)
    gradient.setColorAt(0, QColor(NAVY))
    gradient.setColorAt(1, QColor(SKY))
    painter.fillRect(image.rect(), gradient)
    return painter


def write_wizard_images(folder: Path) -> None:
    # Imagem lateral do assistente clássico (164x314) e a pequena do cabeçalho (55x58).
    side = QImage(164, 314, QImage.Format.Format_RGB32)
    painter = gradient_painter(side, vertical=True)
    painter.drawImage(QRectF(34, 40, 96, 96), render_logo(192))
    painter.setPen(QColor("#ffffff"))
    painter.setFont(QFont("Tahoma", 15, QFont.Weight.Bold))
    painter.drawText(QRectF(0, 150, 164, 60), Qt.AlignmentFlag.AlignCenter, "Old School\nPDF")
    painter.setFont(QFont("Tahoma", 8))
    painter.drawText(
        QRectF(10, 230, 144, 60),
        Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,
        "Grátis, local e sem assinatura.",
    )
    painter.end()
    side.save(str(folder / "wizard.bmp"), "BMP")

    small = QImage(55, 58, QImage.Format.Format_RGB32)
    small.fill(QColor("#ffffff"))
    painter = QPainter(small)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.drawImage(QRectF(3, 4, 50, 50), render_logo(100))
    painter.end()
    small.save(str(folder / "wizard-small.bmp"), "BMP")


def main() -> None:
    folder = Path(sys.argv[1]).resolve()
    folder.mkdir(parents=True, exist_ok=True)
    app = QGuiApplication([])
    write_ico(folder / "oldschoolpdf.ico")
    write_wizard_images(folder)
    del app
    print(f"Ícone e imagens gravados em {folder}")


if __name__ == "__main__":
    main()
