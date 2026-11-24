"""Controles e tela de uma aba PDF. Recebe imagens e texto do serviço local."""

from PySide6.QtCore import QEvent, QPointF, QRectF, QSignalBlocker, Qt, QTimer, Signal
from PySide6.QtGui import QBrush, QColor, QIcon, QPainterPath, QPen, QPixmap, QTransform
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QGraphicsPathItem,
    QGraphicsPixmapItem,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from oldschoolpdf.application.pdf_viewer import PageFrame, PdfViewer
from oldschoolpdf.domain.editing import (
    MAX_STROKE_POINTS,
    PEN_COLORS,
    PEN_WIDTHS,
    STROKE_KINDS,
    STYLED_KINDS,
)
from oldschoolpdf.domain.security import RedactionArea
from oldschoolpdf.domain.viewer import (
    MAX_QUERY_LENGTH,
    FitMode,
    PdfRect,
    RasterRequest,
    rotate_rect,
)
from oldschoolpdf.ui.continuous import ContinuousView, frame_pixmap

ZOOM_LEVELS = (0.1, 0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 3.0, 4.0, 6.0, 8.0)
PAGE_MARGIN = 12
# Distância mínima, em pixels da tela, entre dois pontos gravados de um traço.
STROKE_STEP = 2.0
DEFAULT_PEN = {"color": "blue", "width": "medium"}


def _button(text: str, label: str, callback) -> QPushButton:
    button = QPushButton(text)
    button.setToolTip(label)
    button.setAccessibleName(label)
    button.clicked.connect(callback)
    return button


class PdfCanvas(QGraphicsView):
    viewport_changed = Signal()
    zoom_step = Signal(int)
    region_chosen = Signal(object)
    point_chosen = Signal(object)
    stroke_chosen = Signal(object)
    finish_requested = Signal()
    escape_pressed = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("pdf_canvas")
        self.setAccessibleName(self.tr("Página do PDF"))
        self.setAcceptDrops(False)
        self.viewport().setAcceptDrops(False)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setScene(QGraphicsScene(self))
        self.page_item = QGraphicsPixmapItem()
        self.page_item.setTransformationMode(Qt.TransformationMode.SmoothTransformation)
        self.scene().addItem(self.page_item)
        self.selection_item = self._overlay(QColor(22, 111, 190, 72), QColor("#226db2"))
        self.selection_item.setZValue(3)
        self.selection_item.hide()
        self.object_item = self._overlay(QColor(36, 137, 220, 28), QColor("#1684db"))
        self.object_item.setZValue(4)
        self.object_item.hide()
        self._object_region: PdfRect | None = None
        self._markers: list[QGraphicsRectItem] = []
        self._redaction_items: list[QGraphicsRectItem] = []
        self._last_matches: tuple | None = None
        self.bounds = QRectF()
        self.page = -1
        self.rotation = 0
        self._start: QPointF | None = None
        self._selection: PdfRect | None = None
        self.selecting = True
        # Traços da caneta, da linha e da seta, em coordenadas relativas da tela.
        self.stroke_mode = ""
        self._stroke: list[QPointF] | None = None
        self._strokes: list[list[QPointF]] = []
        self.stroke_item = QGraphicsPathItem()
        self.stroke_item.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        self.stroke_item.setZValue(5)
        self.scene().addItem(self.stroke_item)
        self.set_stroke_style(QColor.fromRgbF(*PEN_COLORS["blue"][1]), 2.0)

    def _overlay(self, fill: QColor, border: QColor) -> QGraphicsRectItem:
        pen = QPen(border)
        pen.setCosmetic(True)
        item = self.scene().addRect(QRectF(), pen, QBrush(fill))
        item.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        item.setZValue(2)
        return item

    @property
    def has_page(self) -> bool:
        return not self.page_item.pixmap().isNull()

    def set_selection_mode(self, enabled: bool) -> None:
        self.selecting = enabled
        self.setDragMode(
            QGraphicsView.DragMode.NoDrag if enabled else QGraphicsView.DragMode.ScrollHandDrag
        )
        self.viewport().setCursor(
            Qt.CursorShape.CrossCursor if enabled else Qt.CursorShape.OpenHandCursor
        )
        if not enabled:
            self.clear_selection()

    def set_stroke_style(self, color: QColor, width: float) -> None:
        pen = QPen(color, max(1.0, width * 1.4))
        pen.setCosmetic(True)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        self.stroke_item.setPen(pen)

    def set_stroke_mode(self, mode: str) -> None:
        """ "ink" guarda vários traços até gravar; "line" emite cada arraste; "" desliga."""
        self.stroke_mode = mode
        self._stroke = None
        self._strokes = []
        self._draw_strokes()
        if mode:
            self.clear_selection()
            self.setDragMode(QGraphicsView.DragMode.NoDrag)
            self.viewport().setCursor(Qt.CursorShape.CrossCursor)

    def take_strokes(self) -> list[list[tuple[float, float]]]:
        strokes = [[self._unrotated(point) for point in stroke] for stroke in self._strokes]
        self._strokes = []
        self._draw_strokes()
        return strokes

    def drop_last_stroke(self) -> None:
        if self._strokes:
            self._strokes.pop()
            self._draw_strokes()

    @property
    def stroke_count(self) -> int:
        return len(self._strokes)

    def _unrotated(self, point: QPointF) -> tuple[float, float]:
        x, y, _, _ = rotate_rect((point.x(), point.y(), point.x(), point.y()), -self.rotation)
        return round(x, 5), round(y, 5)

    def _scene_point(self, point: QPointF) -> QPointF:
        return QPointF(point.x() * self.bounds.width(), point.y() * self.bounds.height())

    def _draw_strokes(self) -> None:
        path = QPainterPath()
        current = [self._stroke] if self._stroke else []
        for stroke in [*self._strokes, *current]:
            first = self._scene_point(stroke[0])
            path.moveTo(first)
            for point in stroke[1:]:
                path.lineTo(self._scene_point(point))
            if len(stroke) == 1:
                path.lineTo(first + QPointF(0.5, 0.5))
        self.stroke_item.setPath(path)

    def _stroke_points(self) -> int:
        return sum(len(stroke) for stroke in self._strokes) + len(self._stroke or ())

    def release_raster(self) -> None:
        self.page_item.setPixmap(QPixmap())

    def clear_page(self) -> None:
        self.page = -1
        self.release_raster()
        self.clear_selection()
        self._stroke = None
        self._strokes = []
        self._draw_strokes()
        self.show_object(None)
        self.set_matches((), ())
        self.show_redactions(())

    def show_frame(self, page: int, frame: PageFrame, rotation: int) -> None:
        same_page = self.page == page and not self.bounds.isEmpty()
        anchor = (
            self._relative(self.mapToScene(self.viewport().rect().center())) if same_page else None
        )
        if self.rotation != rotation:
            if anchor is not None:
                x, y, _, _ = rotate_rect(
                    (anchor.x(), anchor.y(), anchor.x(), anchor.y()), rotation - self.rotation
                )
                anchor = QPointF(x, y)
            self.clear_selection()
        self.page, self.rotation = page, rotation
        self.bounds = QRectF(0, 0, frame.width_pt * frame.scale, frame.height_pt * frame.scale)
        pixmap = frame_pixmap(frame)
        self.page_item.setPixmap(pixmap)
        self.page_item.setTransform(
            QTransform.fromScale(
                self.bounds.width() / pixmap.width(), self.bounds.height() / pixmap.height()
            )
        )
        self.setSceneRect(
            self.bounds.adjusted(-PAGE_MARGIN, -PAGE_MARGIN, PAGE_MARGIN, PAGE_MARGIN)
        )
        if anchor is not None:
            self.centerOn(anchor.x() * self.bounds.width(), anchor.y() * self.bounds.height())
        else:
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().minimum())
            self.verticalScrollBar().setValue(self.verticalScrollBar().minimum())
        if self._selection:
            self.selection_item.setRect(self._absolute(self._selection))
        self.show_object(self._object_region)
        self._draw_strokes()

    def show_object(self, region: PdfRect | None) -> None:
        self._object_region = region
        self.object_item.setVisible(region is not None and self.has_page)
        if region is not None and self.has_page:
            self.object_item.setRect(self._absolute(rotate_rect(region, self.rotation)))

    def show_redactions(self, regions: tuple[PdfRect, ...]) -> None:
        for item in self._redaction_items:
            self.scene().removeItem(item)
        self._redaction_items.clear()
        if not self.has_page:
            return
        for region in regions:
            item = self._overlay(QColor(157, 26, 43, 95), QColor("#b91532"))
            pen = item.pen()
            pen.setStyle(Qt.PenStyle.DashLine)
            pen.setWidth(2)
            item.setPen(pen)
            item.setZValue(2.5)
            item.setRect(self._absolute(rotate_rect(region, self.rotation)))
            self._redaction_items.append(item)

    def _relative(self, point: QPointF) -> QPointF:
        return QPointF(
            min(1.0, max(0.0, point.x() / self.bounds.width())),
            min(1.0, max(0.0, point.y() / self.bounds.height())),
        )

    def _absolute(self, region: PdfRect) -> QRectF:
        x0, y0, x1, y1 = region
        return QRectF(
            x0 * self.bounds.width(),
            y0 * self.bounds.height(),
            (x1 - x0) * self.bounds.width(),
            (y1 - y0) * self.bounds.height(),
        )

    def set_matches(self, regions: tuple, selected: tuple, *, reveal: bool = False) -> None:
        key = (regions, selected, self.rotation, self.bounds, self.has_page)
        if key != self._last_matches:
            self._last_matches = key
            self._draw_matches(regions, selected)
        if self.has_page and reveal and selected:
            self.ensureVisible(self._absolute(rotate_rect(selected[0], self.rotation)), 20, 30)

    def _draw_matches(self, regions: tuple, selected: tuple) -> None:
        for marker in self._markers:
            self.scene().removeItem(marker)
        self._markers.clear()
        if not self.has_page:
            return
        for group, fill, border in (
            (regions, QColor(255, 209, 56, 74), QColor("#b97b00")),
            (selected, QColor(245, 147, 22, 100), QColor("#934409")),
        ):
            for region in group:
                marker = self._overlay(fill, border)
                marker.setRect(self._absolute(rotate_rect(region, self.rotation)))
                self._markers.append(marker)

    def clear_selection(self) -> None:
        self._start = self._selection = None
        self.selection_item.hide()

    def selected_region(self) -> PdfRect | None:
        return rotate_rect(self._selection, -self.rotation) if self._selection else None

    def _drag(self, position: QPointF) -> None:
        rectangle = QRectF(
            self._start, self._relative(self.mapToScene(position.toPoint()))
        ).normalized()
        self._selection = (rectangle.left(), rectangle.top(), rectangle.right(), rectangle.bottom())
        self.selection_item.setRect(self._absolute(self._selection))
        self.selection_item.show()

    def mousePressEvent(self, event) -> None:
        if self.stroke_mode and self.has_page and event.button() == Qt.MouseButton.LeftButton:
            self.setFocus()
            position = self.mapToScene(event.position().toPoint())
            if self.bounds.contains(position) and self._stroke_points() < MAX_STROKE_POINTS - 2:
                self._stroke = [self._relative(position)]
                self._draw_strokes()
            event.accept()
            return
        if self.selecting and self.has_page and event.button() == Qt.MouseButton.LeftButton:
            self.setFocus()
            self.clear_selection()
            position = self.mapToScene(event.position().toPoint())
            if self.bounds.contains(position):
                self._start = self._relative(position)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._stroke is not None:
            point = self._relative(self.mapToScene(event.position().toPoint()))
            if self.stroke_mode == "line":
                self._stroke = [self._stroke[0], point]
            else:
                last = self._scene_point(self._stroke[-1])
                step = self._scene_point(point) - last
                moved = abs(step.x()) + abs(step.y())
                # A escala da cena acompanha o zoom; o passo é medido na tela.
                scale = max(self.transform().m11(), 1e-6)
                if moved * scale >= STROKE_STEP and self._stroke_points() < MAX_STROKE_POINTS - 1:
                    self._stroke.append(point)
            self._draw_strokes()
            event.accept()
            return
        if self._start is not None:
            self._drag(event.position())
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if self._stroke is not None:
            stroke, self._stroke = self._stroke, None
            if self.stroke_mode == "line":
                if len(stroke) == 2:
                    step = self._scene_point(stroke[1]) - self._scene_point(stroke[0])
                    if abs(step.x()) + abs(step.y()) >= 6:
                        self.stroke_chosen.emit([[self._unrotated(p) for p in stroke]])
            else:
                if len(stroke) == 1:
                    # Um clique vira um ponto: dois pontos quase iguais.
                    stroke.append(QPointF(min(1.0, stroke[0].x() + 0.001), stroke[0].y()))
                self._strokes.append(stroke)
            self._draw_strokes()
            event.accept()
            return
        if self._start is not None:
            point = self._start
            self._drag(event.position())
            self._start = None
            rect = self.selection_item.rect()
            if rect.width() < 3 or rect.height() < 3:
                self.clear_selection()
                x, y, _, _ = rotate_rect(
                    (point.x(), point.y(), point.x(), point.y()), -self.rotation
                )
                self.point_chosen.emit((x, y))
            else:
                self.region_chosen.emit(self.selected_region())
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.clear_selection()
            self.escape_pressed.emit()
            event.accept()
        elif self.stroke_mode == "ink" and event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.finish_requested.emit()
            event.accept()
        else:
            super().keyPressEvent(event)

    def wheelEvent(self, event) -> None:
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier and event.angleDelta().y():
            self.zoom_step.emit(1 if event.angleDelta().y() > 0 else -1)
            event.accept()
        else:
            super().wheelEvent(event)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.viewport_changed.emit()

    def event(self, event) -> bool:
        result = super().event(event)
        if event.type() == QEvent.Type.DevicePixelRatioChange:
            self.viewport_changed.emit()
        return result


class PdfTab(QWidget):
    updated = Signal()
    close_requested = Signal()
    feedback = Signal(str)
    placement_ready = Signal(str, object)

    def __init__(self, viewer: PdfViewer, pen: dict | None = None) -> None:
        super().__init__()
        self.setObjectName("pdf_tab")
        self.viewer = viewer
        # Cor e espessura da barra de desenho; a janela compartilha o mesmo dicionário.
        self.pen = pen if pen is not None else dict(DEFAULT_PEN)
        self.fit: FitMode | None = "page"
        self.actual_zoom: float | None = None
        self.page_properties: tuple[float, float, int] | None = None
        self.selection_enabled = True
        self.selected_annotation: int | None = None
        self.placement = ""
        self.redactions: list[RedactionArea] = []
        self.continuous_enabled = False
        self._object_key: tuple[int, int] | None = None
        self._focus_hit = False
        self._render_failed = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.navigation = self._navigation()
        layout.addWidget(self.navigation)
        self.placement_note = QLabel()
        self.placement_note.setProperty("role", "badge")
        self.placement_note.setWordWrap(True)
        self.placement_note.setContentsMargins(8, 4, 8, 4)
        self.placement_note.hide()
        layout.addWidget(self.placement_note)
        self.drawing_bar = self._drawing_bar()
        layout.addWidget(self.drawing_bar)
        self.redaction_note = QLabel()
        self.redaction_note.setObjectName("redaction_preview")
        self.redaction_note.setProperty("role", "badge")
        self.redaction_note.setContentsMargins(8, 4, 8, 4)
        self.redaction_note.setWordWrap(True)
        self.redaction_note.hide()
        layout.addWidget(self.redaction_note)
        self.search = self._search_controls()
        layout.addWidget(self.search)
        self.stack = QStackedWidget()
        layout.addWidget(self.stack, 1)
        self.notice = self._notice_panel()
        self.stack.addWidget(self.notice)
        self.password_panel = self._password_panel()
        self.stack.addWidget(self.password_panel)
        self.canvas = PdfCanvas()
        self.stack.addWidget(self.canvas)
        self.continuous = ContinuousView(viewer)
        self.stack.addWidget(self.continuous)
        self.render_timer = QTimer(self)
        self.render_timer.setSingleShot(True)
        self.render_timer.timeout.connect(self._render)
        self.canvas.viewport_changed.connect(self._schedule_render)
        self.canvas.zoom_step.connect(self.step_zoom)
        self.canvas.region_chosen.connect(self._chosen_region)
        self.canvas.point_chosen.connect(self._chosen_point)
        self.canvas.stroke_chosen.connect(self._chosen_strokes)
        self.canvas.finish_requested.connect(self.finish_drawing)
        self.canvas.escape_pressed.connect(self._cancel_placement)
        viewer.changed.connect(self._sync)
        viewer.edited.connect(self._revision_edited)
        viewer.objects_changed.connect(self.updated.emit)
        viewer.frame_ready.connect(self._frame)
        viewer.search_changed.connect(self._sync_search)
        viewer.hit_selected.connect(self._select_hit)
        viewer.text_ready.connect(self._copied)
        viewer.message.connect(self._message)
        viewer.opening_cancelled.connect(self.close_requested)
        self._sync()

    def annotation(self):
        return next(
            (item for item in self.viewer.annotations if item.xref == self.selected_annotation),
            None,
        )

    def select_annotation(self, xref: int | None) -> None:
        if self.selected_annotation == xref:
            return
        self.selected_annotation = xref
        self._cancel_placement()
        obj = self.annotation()
        self.canvas.show_object(obj.region if obj else None)
        self.updated.emit()

    def _drawing_bar(self) -> QWidget:
        widget = QWidget()
        widget.setObjectName("drawing_bar")
        row = QHBoxLayout(widget)
        row.setContentsMargins(8, 2, 8, 4)
        row.addWidget(QLabel(self.tr("Cor:")))
        self.pen_color = QComboBox()
        self.pen_color.setObjectName("pen_color")
        self.pen_color.setAccessibleName(self.tr("Cor do desenho"))
        for key, (label, rgb) in PEN_COLORS.items():
            swatch = QPixmap(14, 14)
            swatch.fill(QColor.fromRgbF(*rgb))
            self.pen_color.addItem(QIcon(swatch), label, key)
        row.addWidget(self.pen_color)
        row.addWidget(QLabel(self.tr("Espessura:")))
        self.pen_width = QComboBox()
        self.pen_width.setObjectName("pen_width")
        self.pen_width.setAccessibleName(self.tr("Espessura do traço"))
        for key, (label, _width) in PEN_WIDTHS.items():
            self.pen_width.addItem(label, key)
        row.addWidget(self.pen_width)
        self.pen_color.currentIndexChanged.connect(self._pen_changed)
        self.pen_width.currentIndexChanged.connect(self._pen_changed)
        row.addStretch()
        self.undo_stroke = _button(
            self.tr("Apagar último traço"),
            self.tr("Apaga o último traço ainda não gravado"),
            self.canvas_drop_stroke,
        )
        self.finish_button = _button(
            self.tr("Gravar desenho"),
            self.tr("Grava os traços na página (Enter)"),
            self.finish_drawing,
        )
        cancel = _button(
            self.tr("Cancelar"), self.tr("Cancela o desenho (Esc)"), self._cancel_placement
        )
        for button in (self.undo_stroke, self.finish_button, cancel):
            row.addWidget(button)
        widget.hide()
        return widget

    def canvas_drop_stroke(self) -> None:
        self.canvas.drop_last_stroke()

    def _sync_pen(self) -> None:
        with QSignalBlocker(self.pen_color), QSignalBlocker(self.pen_width):
            self.pen_color.setCurrentIndex(max(0, self.pen_color.findData(self.pen["color"])))
            self.pen_width.setCurrentIndex(max(0, self.pen_width.findData(self.pen["width"])))
        self._apply_pen()

    def _pen_changed(self, _index: int = 0) -> None:
        self.pen["color"] = self.pen_color.currentData()
        self.pen["width"] = self.pen_width.currentData()
        self._apply_pen()
        self.canvas.setFocus()

    def _apply_pen(self) -> None:
        color = QColor.fromRgbF(*PEN_COLORS[self.pen["color"]][1])
        if self.pen["color"] == "yellow":
            color.setAlphaF(0.6)
        self.canvas.set_stroke_style(color, PEN_WIDTHS[self.pen["width"]][1])

    def prepare_placement(self, kind: str) -> None:
        self.set_continuous(False)
        self.set_selection_enabled(True)
        region = self.canvas.selected_region()
        self._cancel_placement()
        self.placement = kind
        if region and kind not in STROKE_KINDS and kind != "move":
            self._chosen_region(region)
            return
        self.drawing_bar.setVisible(kind in STYLED_KINDS)
        self.finish_button.setVisible(kind == "ink")
        self.undo_stroke.setVisible(kind == "ink")
        if kind in STYLED_KINDS:
            self._sync_pen()
        if kind in STROKE_KINDS:
            self.canvas.set_stroke_mode("ink" if kind == "ink" else "line")
        if kind == "ink":
            message = self.tr(
                "Desenhe com o mouse; pode fazer vários traços. Enter ou “Gravar desenho” "
                "grava. Esc cancela."
            )
        elif kind == "line":
            message = self.tr("Arraste do começo ao fim da linha. Esc cancela.")
        elif kind == "arrow":
            message = self.tr("Arraste do começo até a ponta da seta. Esc cancela.")
        elif kind == "move":
            message = self.tr("Clique no novo canto superior esquerdo do objeto. Esc cancela.")
        elif kind == "comment":
            message = self.tr("Clique onde deseja inserir o comentário. Esc cancela.")
        elif kind == "redact":
            message = self.tr("Arraste sobre toda a área sensível para marcá-la. Esc cancela.")
        elif kind == "visual_signature":
            message = self.tr("Arraste o retângulo onde ficará a assinatura visual. Esc cancela.")
        elif kind == "field":
            message = self.tr("Arraste o retângulo do novo campo de formulário. Esc cancela.")
        else:
            message = self.tr("Arraste uma área na página para aplicar a ferramenta. Esc cancela.")
        self.feedback.emit(message)
        self.placement_note.setText(message)
        self.placement_note.show()

    def _cancel_placement(self) -> None:
        if self.placement and not self.placement_note.isHidden():
            # A dica da ferramenta sai da barra de status junto com a ferramenta.
            self.feedback.emit("")
        self.placement = ""
        self.placement_note.hide()
        self.drawing_bar.hide()
        if self.canvas.stroke_mode:
            self.canvas.set_stroke_mode("")
            self.canvas.set_selection_mode(self.canvas.selecting)

    def _chosen_strokes(self, strokes) -> None:
        if self.placement in {"line", "arrow"} and strokes:
            kind = self.placement
            self._cancel_placement()
            self.placement_ready.emit(kind, {"points": strokes[0]})

    def finish_drawing(self) -> None:
        if self.placement != "ink":
            return
        strokes = self.canvas.take_strokes()
        if not strokes:
            self.feedback.emit(self.tr("Desenhe pelo menos um traço antes de gravar."))
            return
        self._cancel_placement()
        self.placement_ready.emit("ink", {"strokes": strokes})

    def _chosen_region(self, region) -> None:
        if self.placement:
            kind = self.placement
            self._cancel_placement()
            self.placement_ready.emit(kind, region)

    def _chosen_point(self, point) -> None:
        x, y = point
        if self.placement in {"comment", "move"}:
            x, y = min(x, 0.96), min(y, 0.96)
            self._chosen_region((x, y, x + 0.04, y + 0.04))
        elif not self.placement:
            for obj in reversed(self.viewer.annotations):
                x0, y0, x1, y1 = obj.region
                if x0 <= x <= x1 and y0 <= y <= y1:
                    self.select_annotation(obj.xref)
                    return
            self.select_annotation(None)

    def _reset_page(self) -> None:
        self._object_key = None
        self.selected_annotation = None
        self._cancel_placement()
        self.canvas.clear_page()
        self.page_properties = None
        self.actual_zoom = None
        self._render_failed = False

    def refresh_redactions(self) -> None:
        self.redaction_note.setText(
            f"Redação em prévia · {len(self.redactions)} área(s) · exporte pela aba Segurança"
        )
        self.redaction_note.setVisible(bool(self.redactions) and self.viewer.state == "ready")
        self._draw_redactions()
        self.updated.emit()

    def _draw_redactions(self) -> None:
        self.canvas.show_redactions(
            tuple(mark.region for mark in self.redactions if mark.page == self.viewer.page)
        )

    def _revision_edited(self) -> None:
        self._reset_page()
        if self.redactions:
            self.redactions.clear()
            self.refresh_redactions()
            self.feedback.emit(self.tr("As marcas de redação foram limpas após mudar a revisão."))

    def _navigation(self) -> QWidget:
        widget = QWidget()
        row = QHBoxLayout(widget)
        row.setContentsMargins(8, 4, 8, 4)
        self.previous = _button("‹", self.tr("Página anterior"), lambda: self.navigate(-1))
        self.next = _button("›", self.tr("Próxima página"), lambda: self.navigate(1))
        row.addWidget(self.previous)
        label = QLabel(self.tr("&Página"))
        self.page_number = QSpinBox()
        self.page_number.setObjectName("pdf_page_number")
        self.page_number.setKeyboardTracking(False)
        self.page_number.setAccessibleName(self.tr("Ir para a página"))
        self.page_number.valueChanged.connect(lambda number: self.viewer.go_to(number - 1))
        label.setBuddy(self.page_number)
        row.addWidget(label)
        row.addWidget(self.page_number)
        self.page_total = QLabel()
        row.addWidget(self.page_total)
        row.addWidget(self.next)
        row.addStretch()
        self.render_status = QLabel(self.tr("Somente leitura"))
        self.render_status.setProperty("role", "muted")
        row.addWidget(self.render_status)
        return widget

    def _search_controls(self) -> QWidget:
        widget = QWidget()
        root = QVBoxLayout(widget)
        root.setContentsMargins(8, 4, 8, 4)
        root.setSpacing(3)
        row = QHBoxLayout()
        self.query = QLineEdit()
        self.query.setObjectName("pdf_search_query")
        self.query.setAcceptDrops(False)
        self.query.setMaxLength(MAX_QUERY_LENGTH)
        self.query.setPlaceholderText(self.tr("Buscar texto neste PDF"))
        self.query.setAccessibleName(self.tr("Texto da busca"))
        self.query.returnPressed.connect(self._search_text)
        row.addWidget(self.query, 1)
        self.search_button = _button(
            self.tr("Buscar"), self.tr("Buscar em todas as páginas"), self._search_text
        )
        self.prev_hit = _button(
            "‹", self.tr("Ocorrência anterior"), lambda: self.viewer.move_hit(-1)
        )
        self.next_hit = _button("›", self.tr("Próxima ocorrência"), lambda: self.viewer.move_hit(1))
        self.stop_search = _button(
            self.tr("Parar"), self.tr("Cancelar busca"), self.viewer.cancel_search
        )
        for button in (self.search_button, self.prev_hit, self.next_hit, self.stop_search):
            row.addWidget(button)
        row.addWidget(_button("×", self.tr("Fechar busca"), self.hide_search))
        root.addLayout(row)
        self.search_status = QLabel()
        self.search_status.setObjectName("pdf_search_status")
        self.search_status.setWordWrap(True)
        root.addWidget(self.search_status)
        widget.hide()
        return widget

    def _notice_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.notice_text = QLabel()
        self.notice_text.setObjectName("pdf_notice")
        self.notice_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.notice_text.setWordWrap(True)
        self.notice_text.setMaximumWidth(380)
        layout.addWidget(self.notice_text)
        self.loading = QProgressBar()
        self.loading.setRange(0, 0)
        self.loading.setTextVisible(False)
        self.loading.setAccessibleName(self.tr("Carregando documento"))
        layout.addWidget(self.loading)
        self.notice_button = _button(
            self.tr("Cancelar abertura"), self.tr("Fechar esta aba"), self._abort_or_close
        )
        layout.addWidget(self.notice_button)
        self.recover_button = _button(
            self.tr("Recuperar revisão"),
            self.tr("Reabrir a última revisão validada nesta sessão"),
            self.viewer.recover,
        )
        layout.addWidget(self.recover_button)
        return panel

    def _abort_or_close(self) -> None:
        if self.viewer.state == "opening":
            self.viewer.cancel_open()
        else:
            self.close_requested.emit()

    def _password_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.password_notice = QLabel()
        self.password_notice.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.password_notice)
        label = QLabel(self.tr("&Senha do documento"))
        self.password = QLineEdit()
        self.password.setObjectName("pdf_password")
        self.password.setAcceptDrops(False)
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.password.setAccessibleName(self.tr("Senha do documento"))
        self.password.setMaxLength(1024)
        label.setBuddy(self.password)
        layout.addWidget(label)
        layout.addWidget(self.password)
        self.password.returnPressed.connect(self._submit_password)
        buttons = QHBoxLayout()
        buttons.addWidget(
            _button(self.tr("Abrir PDF"), self.tr("Confirmar senha"), self._submit_password)
        )
        buttons.addWidget(
            _button(self.tr("Cancelar"), self.tr("Cancelar abertura"), self.close_requested.emit)
        )
        layout.addLayout(buttons)
        return panel

    def _submit_password(self) -> None:
        password = self.password.text()
        self.password.clear()
        self.viewer.submit_password(password)

    def set_active(self, active: bool) -> None:
        if self.viewer.active == active:
            return
        self.viewer.set_active(active)
        if active:
            self._sync()
        else:
            self.render_timer.stop()
            self.canvas.release_raster()
            self.continuous.pause()

    def _sync(self) -> None:
        viewer = self.viewer
        ready = viewer.state == "ready"
        self.navigation.setVisible(ready)
        if not ready:
            self.redaction_note.hide()
            self.render_timer.stop()
            self.continuous.pause()
            self._reset_page()
        if ready:
            self.stack.setCurrentWidget(self.continuous if self.continuous_enabled else self.canvas)
            self.navigation.setEnabled(not viewer.busy)
            count = viewer.info.page_count
            with QSignalBlocker(self.page_number):
                self.page_number.setRange(1, count)
                self.page_number.setValue(viewer.page + 1)
            self.page_total.setText(self.tr("de %1").replace("%1", str(count)))
            self.previous.setEnabled(viewer.page > 0)
            self.next.setEnabled(viewer.page + 1 < count)
            self.canvas.setEnabled(not viewer.busy)
            self.continuous.setEnabled(not viewer.busy)
            self.canvas.set_selection_mode(
                self.selection_enabled and (viewer.info.copy_allowed or bool(self.placement))
            )
            if self._object_key != (viewer.revision, viewer.page):
                self._reset_page()
                self._object_key = (viewer.revision, viewer.page)
                viewer.request_objects()
            if self.continuous_enabled:
                self.continuous.sync()
            else:
                self._schedule_render()
            self.render_status.setText(viewer.busy or self.document_status())
        elif viewer.state == "password":
            self.stack.setCurrentWidget(self.password_panel)
            self.password_notice.setText(viewer.notice)
            if viewer.active:
                self.password.setFocus()
        else:
            self.stack.setCurrentWidget(self.notice)
            self.notice_text.setText(viewer.notice)
            self.loading.setVisible(viewer.state == "opening")
            self.recover_button.setVisible(viewer.can_recover)
            label = self.tr("Fechar aba")
            if viewer.state == "opening":
                label = (
                    self.tr("Cancelar recuperação")
                    if viewer.session.working_copy
                    else self.tr("Cancelar abertura")
                )
            self.notice_button.setText(label)
            self.search.hide()
        self.updated.emit()

    def _schedule_render(self) -> None:
        if self.viewer.active and self.viewer.info and not self.continuous_enabled:
            self.render_timer.start(50)

    def _render(self) -> None:
        if not self.viewer.active or not self.viewer.info or self.viewer.busy:
            return
        size = self.canvas.maximumViewportSize()
        zoom = self.fit or self.viewer.session.zoom
        width = height = 0
        if self.fit:
            width = size.width() - 2 * PAGE_MARGIN - 4
            if self.fit == "width":
                width -= self.canvas.verticalScrollBar().sizeHint().width()
            height = size.height() - 2 * PAGE_MARGIN - 4
        request = RasterRequest(
            self.viewer.page,
            self.viewer.rotation,
            zoom,
            max(1, width),
            max(1, height),
            round(min(4.0, self.canvas.devicePixelRatioF()), 2),
        )
        if not self.canvas.has_page and not self._render_failed:
            self.render_status.setText(self.tr("Renderizando página…"))
        self.viewer.render(request)

    def _frame(self, frame: PageFrame) -> None:
        if self.continuous_enabled:
            return
        self._render_failed = False
        self.actual_zoom = frame.scale
        self.page_properties = (frame.width_pt, frame.height_pt, frame.rotation)
        self.canvas.show_frame(self.viewer.page, frame, self.viewer.rotation)
        self._draw_redactions()
        status = self.viewer.busy or self.document_status()
        if frame.limited:
            status += self.tr(" · imagem limitada")
        if self.viewer.info.repaired:
            status += self.tr(" · estrutura reparada")
        self.render_status.setText(status)
        self._sync_search()
        self.updated.emit()

    def document_status(self) -> str:
        viewer = self.viewer
        if viewer.session.dirty:
            return self.tr("Alterações não gravadas")
        if viewer.has_saved_copy and viewer.saved_revision == viewer.revision:
            return self.tr("Versão gravada")
        return self.tr("Original preservado")

    def set_continuous(self, enabled: bool) -> None:
        if enabled == self.continuous_enabled or not self.viewer.info:
            return
        self.continuous_enabled = enabled
        self._cancel_placement()
        if enabled:
            self.render_timer.stop()
            self.canvas.release_raster()
            self.viewer.release_render()
            if not self.search.isHidden():
                self.hide_search()
        else:
            self.continuous.pause()
        self._sync()
        self.stack.currentWidget().setFocus()

    def navigate(self, direction: int) -> None:
        self.viewer.go_to(self.viewer.page + direction)

    def set_zoom(self, zoom: float | FitMode) -> None:
        self.set_continuous(False)
        if isinstance(zoom, str):
            self.fit = zoom
        else:
            self.fit = None
            self.viewer.session.zoom = zoom
        self._render_failed = False
        self._schedule_render()
        self.updated.emit()

    def step_zoom(self, step: int) -> None:
        current = (
            self.actual_zoom
            if self.fit and self.actual_zoom is not None
            else self.viewer.session.zoom
        )
        if step > 0:
            target = next(
                (level for level in ZOOM_LEVELS if level > current + 0.005), ZOOM_LEVELS[-1]
            )
        else:
            target = next(
                (level for level in reversed(ZOOM_LEVELS) if level < current - 0.005),
                ZOOM_LEVELS[0],
            )
        self.set_zoom(target)

    def show_search(self) -> None:
        if self.viewer.info:
            self.set_continuous(False)
            self.search.show()
            self.query.setFocus()
            self.query.selectAll()
            self._sync_search()
            self.updated.emit()

    def hide_search(self) -> None:
        self.search.hide()
        self.viewer.cancel_search()
        self.canvas.set_matches((), ())
        self.canvas.setFocus()
        self.updated.emit()

    def _search_text(self) -> None:
        self._focus_hit = False
        self.viewer.start_search(self.query.text())

    def _select_hit(self) -> None:
        self._focus_hit = True
        self._sync_search()

    def _sync_search(self) -> None:
        viewer = self.viewer
        count = len(viewer.hits)
        position = f"{viewer.selected_hit + 1}/{count} · " if count else ""
        self.search_status.setText(position + viewer.search_notice)
        self.prev_hit.setEnabled(count > 1)
        self.next_hit.setEnabled(count > 1)
        self.stop_search.setEnabled(viewer.searching)
        if self.search.isHidden() or self.canvas.page != viewer.page or not self.canvas.has_page:
            return
        selected = ()
        regions = []
        for index, hit in enumerate(viewer.hits):
            if hit.page == viewer.page:
                if index == viewer.selected_hit:
                    selected = hit.regions
                else:
                    regions.extend(hit.regions)
        self.canvas.set_matches(tuple(regions), selected, reveal=self._focus_hit)
        self._focus_hit = False

    def copy_text(self) -> None:
        self.viewer.copy(self.canvas.selected_region())

    def set_selection_enabled(self, enabled: bool) -> None:
        self.set_continuous(False)
        self.selection_enabled = enabled
        if not enabled:
            self._cancel_placement()
        self.canvas.set_selection_mode(enabled)
        self.canvas.setFocus()

    def _copied(self, text: str) -> None:
        QApplication.clipboard().setText(text)
        self.feedback.emit(self.tr("Texto copiado para a área de transferência."))

    def _message(self, message: str) -> None:
        if not self.canvas.has_page:
            self._render_failed = True
            self.render_status.setText(self.tr("Página indisponível"))
        self.feedback.emit(message)
