"""Rolagem virtualizada, com imagens apenas nas páginas visíveis."""

from PySide6.QtCore import QAbstractListModel, QModelIndex, QPoint, QRect, QSize, Qt, QTimer
from PySide6.QtGui import QImage, QPalette, QPixmap
from PySide6.QtWidgets import QListView, QStyledItemDelegate

from oldschoolpdf.application.pdf_viewer import PageFrame, PdfViewer
from oldschoolpdf.domain.viewer import RasterRequest


def frame_pixmap(frame: PageFrame) -> QPixmap:
    image = frame.image
    qt_image = QImage(
        image.data, image.width, image.height, image.stride, QImage.Format.Format_RGB888
    )
    return QPixmap.fromImage(qt_image.copy())


class ContinuousModel(QAbstractListModel):
    def __init__(self, parent) -> None:
        super().__init__(parent)
        self.count = 0
        self.height = 300
        self.images: dict[int, QPixmap] = {}

    def rowCount(self, parent: QModelIndex | None = None) -> int:
        return 0 if parent is not None and parent.isValid() else self.count

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.AccessibleTextRole):
            return self.tr("Página %1").replace("%1", str(index.row() + 1))
        if role == Qt.ItemDataRole.SizeHintRole:
            return QSize(1, self.height)
        return None

    def reset(self, count: int) -> None:
        self.beginResetModel()
        self.count = count
        self.images.clear()
        self.endResetModel()


class ContinuousDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index) -> None:
        rect = option.rect.adjusted(12, 4, -12, -8)
        area = rect.adjusted(0, 23, 0, 0)
        painter.save()
        painter.setPen(option.palette.color(QPalette.ColorRole.Text))
        painter.drawText(
            QRect(rect.x(), rect.y(), rect.width(), 21),
            Qt.AlignmentFlag.AlignCenter,
            index.data(),
        )
        pixmap = index.model().images.get(index.row())
        if pixmap is not None:
            size = pixmap.size().scaled(area.size(), Qt.AspectRatioMode.KeepAspectRatio)
            target = QRect(QPoint(), size)
            target.moveCenter(area.center())
            painter.drawPixmap(target, pixmap)
        else:
            painter.fillRect(area, option.palette.color(QPalette.ColorRole.AlternateBase))
        painter.restore()


class ContinuousView(QListView):
    def __init__(self, viewer: PdfViewer) -> None:
        super().__init__()
        self.setObjectName("pdf_continuous")
        self.setAccessibleName(self.tr("Páginas em rolagem contínua"))
        self.viewer = viewer
        self.pages = ContinuousModel(self)
        self.setModel(self.pages)
        self.setItemDelegate(ContinuousDelegate(self))
        self.setAcceptDrops(False)
        self.setSelectionMode(QListView.SelectionMode.NoSelection)
        self.setUniformItemSizes(True)
        self.setLayoutMode(QListView.LayoutMode.Batched)
        self.setVerticalScrollMode(QListView.ScrollMode.ScrollPerPixel)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._page = -1
        self._revision = -1
        self._rotation = -1
        self._specs: dict[int, RasterRequest] = {}
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self._request_visible)
        self.verticalScrollBar().valueChanged.connect(self._schedule)
        self.verticalScrollBar().rangeChanged.connect(self._schedule)
        viewer.continuous_frame_ready.connect(self._frame)

    def sync(self) -> None:
        viewer = self.viewer
        count = viewer.info.page_count
        if (count, viewer.revision, viewer.rotation) != (
            self.pages.count,
            self._revision,
            self._rotation,
        ):
            self._revision, self._rotation = viewer.revision, viewer.rotation
            self._specs.clear()
            self.pages.reset(count)
            self._page = -1
        if viewer.page != self._page:
            self._page = viewer.page
            self.scrollTo(self.pages.index(self._page), QListView.ScrollHint.PositionAtCenter)
        self._schedule()

    def pause(self) -> None:
        self.timer.stop()
        self._specs.clear()
        self.pages.images.clear()
        self.viewer.continuous_pages([])

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        height = max(260, int(self.viewport().height() * 0.88))
        if self.pages.height != height:
            self.pages.height = height
            self.doItemsLayout()
            if self._page >= 0:
                self.scrollTo(self.pages.index(self._page), QListView.ScrollHint.PositionAtCenter)
        self._schedule()

    def _schedule(self, *args) -> None:
        if self.isVisible() and self.viewer.active:
            self.timer.start(40)

    def _request_visible(self) -> None:
        if not self.isVisible() or not self.viewer.active or self.viewer.busy:
            return
        viewport = self.viewport()
        middle = self.indexAt(viewport.rect().center())
        if middle.isValid() and middle.row() != self._page:
            self._page = middle.row()
            self.viewer.go_to(self._page)
        rows = {
            index.row()
            for y in range(1, viewport.height(), 70)
            if (index := self.indexAt(QPoint(8, y))).isValid()
        }
        if middle.isValid():
            rows.add(middle.row())
        specs = {
            page: RasterRequest(
                page,
                self.viewer.rotation,
                "continuous",
                max(1, viewport.width() - 24),
                self.pages.height - 35,
                round(min(4.0, viewport.devicePixelRatioF()), 2),
            )
            for page in rows
        }
        self.pages.images = {
            page: pixmap
            for page, pixmap in self.pages.images.items()
            if page in specs and specs[page] == self._specs.get(page)
        }
        self._specs = specs
        self.viewer.continuous_pages(
            [
                specs[page]
                for page in sorted(rows, key=lambda page: abs(page - self._page))
                if page not in self.pages.images
            ]
        )

    def _frame(self, spec: RasterRequest, frame: PageFrame) -> None:
        if self._specs.get(spec.page) == spec and self.isVisible():
            self.pages.images[spec.page] = frame_pixmap(frame)
            self.viewport().update(self.visualRect(self.pages.index(spec.page)))
