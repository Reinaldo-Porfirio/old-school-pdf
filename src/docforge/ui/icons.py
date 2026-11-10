"""Ícones originais, vetoriais via QPainter; sem assets externos."""

from functools import lru_cache

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap, QPolygonF


@lru_cache(maxsize=128)
def command_icon(kind: str, color: str = "#2876bd") -> QIcon:
    icon = QIcon()
    for size in (20, 24, 32, 48, 64):
        image = QPixmap(size, size)
        image.fill(Qt.GlobalColor.transparent)
        p = QPainter(image)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.scale(size / 24, size / 24)
        p.setPen(QPen(QColor(color), 1.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.setBrush(QColor(color).lighter(185))
        if kind in ("open", "merge", "split"):
            p.drawRoundedRect(QRectF(2, 7, 20, 14), 2, 2)
            p.drawPolyline(QPolygonF([QPointF(3, 7), QPointF(3, 4), QPointF(9, 4), QPointF(12, 7)]))
            if kind == "merge":
                p.drawLine(8, 11, 8, 18)
                p.drawLine(16, 11, 16, 18)
                p.drawLine(8, 15, 16, 15)
            elif kind == "split":
                p.drawLine(12, 10, 12, 18)
        elif kind in ("home", "document", "save", "print"):
            p.drawRoundedRect(QRectF(5, 2, 15, 20), 1, 1)
            p.drawLine(8, 8, 16, 8)
            p.drawLine(8, 12, 16, 12)
            p.drawLine(8, 16, 13, 16)
            if kind == "save":
                p.drawRect(10, 15, 10, 7)
            if kind == "print":
                p.drawRoundedRect(QRectF(2, 9, 20, 10), 2, 2)
        elif kind in ("undo", "redo"):
            if kind == "redo":
                p.translate(24, 0)
                p.scale(-1, 1)
            p.drawArc(QRectF(5, 7, 15, 14), -25 * 16, 225 * 16)
            p.drawPolyline(QPolygonF([QPointF(3, 4), QPointF(3, 12), QPointF(11, 12)]))
        elif kind in ("zoom_in", "zoom_out", "search"):
            p.drawEllipse(QRectF(3, 2, 13, 13))
            p.drawLine(15, 14, 22, 21)
            if kind != "search":
                p.drawLine(6, 8, 13, 8)
                if kind == "zoom_in":
                    p.drawLine(10, 5, 10, 12)
        elif kind == "settings":
            for x, y in ((5, 8), (12, 16), (19, 10)):
                p.drawLine(x, 3, x, 21)
                p.drawRoundedRect(QRectF(x - 2.5, y - 2, 5, 4), 1, 1)
        elif kind == "select":
            p.drawPolygon(
                QPolygonF([QPointF(5, 2), QPointF(6, 21), QPointF(12, 16), QPointF(20, 15)])
            )
        elif kind == "highlight":
            p.drawPolygon(
                QPolygonF([QPointF(13, 3), QPointF(21, 9), QPointF(11, 20), QPointF(4, 14)])
            )
            p.drawLine(3, 22, 17, 22)
        elif kind in ("text", "underline"):
            p.drawLine(5, 5, 19, 5)
            p.drawLine(12, 5, 12, 17)
            if kind == "underline":
                p.drawLine(5, 21, 19, 21)
        elif kind == "rectangle":
            p.drawRect(QRectF(4, 6, 16, 12))
        elif kind == "redaction":
            p.setBrush(QColor(color))
            p.drawRect(QRectF(3, 8, 18, 8))
            p.drawLine(3, 19, 21, 19)
        elif kind == "signature":
            p.drawPolyline(
                QPolygonF(
                    [
                        QPointF(3, 15),
                        QPointF(9, 5),
                        QPointF(7, 16),
                        QPointF(13, 11),
                        QPointF(16, 15),
                        QPointF(21, 12),
                    ]
                )
            )
            p.drawLine(3, 20, 21, 20)
        elif kind == "ellipse":
            p.drawEllipse(QRectF(4, 6, 16, 12))
        elif kind == "image":
            p.drawRect(QRectF(3, 4, 18, 16))
            p.drawEllipse(QRectF(6, 7, 3, 3))
            p.drawPolyline(QPolygonF([QPointF(5, 17), QPointF(13, 10), QPointF(19, 17)]))
        elif kind == "stamp":
            p.drawRoundedRect(QRectF(8, 3, 8, 10), 2, 2)
            p.drawRoundedRect(QRectF(4, 12, 16, 5), 1, 1)
            p.drawLine(4, 21, 20, 21)
        elif kind == "form":
            p.drawRect(QRectF(4, 3, 16, 18))
            p.drawPolyline(QPolygonF([QPointF(7, 10), QPointF(10, 13), QPointF(16, 7)]))
            p.drawLine(7, 17, 17, 17)
        elif kind in ("reorder", "continuous"):
            p.drawRoundedRect(QRectF(4, 3, 11, 7), 1, 1)
            p.drawRoundedRect(QRectF(4, 14, 11, 7), 1, 1)
            p.drawLine(19, 5, 19, 19)
            p.drawLine(17, 16, 19, 19)
            p.drawLine(21, 16, 19, 19)
            if kind == "reorder":
                p.drawLine(17, 8, 19, 5)
                p.drawLine(21, 8, 19, 5)
        elif kind == "comment":
            p.drawRoundedRect(QRectF(2, 3, 20, 14), 3, 3)
            p.drawPolyline(QPolygonF([QPointF(6, 17), QPointF(6, 22), QPointF(12, 17)]))
        elif kind == "ocr":
            p.drawRect(3, 3, 18, 18)
            p.drawLine(7, 7, 17, 7)
            p.drawLine(12, 7, 12, 18)
        elif kind == "shield":
            p.drawPolygon(
                QPolygonF(
                    [
                        QPointF(12, 2),
                        QPointF(21, 6),
                        QPointF(19, 16),
                        QPointF(12, 22),
                        QPointF(5, 16),
                        QPointF(3, 6),
                    ]
                )
            )
            p.drawLine(8, 12, 11, 15)
            p.drawLine(11, 15, 17, 8)
        elif kind == "close":
            p.drawLine(5, 5, 19, 19)
            p.drawLine(19, 5, 5, 19)
        elif kind in ("next", "previous"):
            x = (8, 16) if kind == "next" else (16, 8)
            p.drawPolyline(QPolygonF([QPointF(x[0], 5), QPointF(x[1], 12), QPointF(x[0], 19)]))
        else:
            p.drawEllipse(QRectF(3, 3, 18, 18))
            p.drawLine(12, 10, 12, 17)
            p.drawPoint(12, 7)
        p.end()
        icon.addPixmap(image)
    return icon
