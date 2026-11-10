"""Painéis acopláveis de navegação, edição e tarefas."""

from PySide6.QtCore import (
    QAbstractListModel,
    QItemSelectionModel,
    QMimeData,
    QModelIndex,
    QPoint,
    QSignalBlocker,
    QSize,
    Qt,
    QTimer,
    Signal,
)
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDockWidget,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QListView,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QTabWidget,
    QToolButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from oldschoolpdf import __version__
from oldschoolpdf.application.contracts import JobService
from oldschoolpdf.application.pdf_viewer import PageFrame
from oldschoolpdf.domain.editing import ANNOTATION_LABELS
from oldschoolpdf.domain.tasks import TaskState
from oldschoolpdf.ui.continuous import frame_pixmap
from oldschoolpdf.ui.icons import command_icon
from oldschoolpdf.ui.pdf_tab import PdfTab

PAGE_MIME = "application/x-oldschoolpdf-page"


def empty_panel(title: str, explanation: str) -> QWidget:
    page = QWidget()
    root = QVBoxLayout(page)
    root.setContentsMargins(12, 20, 12, 20)
    label = QLabel(title)
    font = label.font()
    font.setBold(True)
    label.setFont(font)
    label.setWordWrap(True)
    root.addWidget(label)
    note = QLabel(explanation)
    note.setProperty("role", "muted")
    note.setWordWrap(True)
    root.addWidget(note)
    root.addStretch()
    return page


class ThumbnailModel(QAbstractListModel):
    move_requested = Signal(int, int)

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.count = 0
        self.moving = False
        self.images: dict[int, QIcon] = {}
        self.placeholder = command_icon("document")

    def rowCount(self, parent: QModelIndex | None = None) -> int:
        return 0 if parent is not None and parent.isValid() else self.count

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        page = index.row()
        if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.AccessibleTextRole):
            return self.tr("Página %1").replace("%1", str(page + 1))
        if role == Qt.ItemDataRole.DecorationRole:
            return self.images.get(page, self.placeholder)
        if role == Qt.ItemDataRole.SizeHintRole:
            return QSize(155, 116)
        return None

    def flags(self, index):
        flags = super().flags(index)
        if self.moving:
            flags |= Qt.ItemFlag.ItemIsDropEnabled
            if index.isValid():
                flags |= Qt.ItemFlag.ItemIsDragEnabled
        return flags

    def mimeTypes(self):
        return [PAGE_MIME]

    def mimeData(self, indexes):
        data = QMimeData()
        if self.moving and indexes:
            data.setData(PAGE_MIME, str(indexes[0].row()).encode("ascii"))
        return data

    def supportedDropActions(self):
        return Qt.DropAction.MoveAction

    def dropMimeData(self, data, action, row, column, parent):
        if not self.moving or not data.hasFormat(PAGE_MIME):
            return False
        if action == Qt.DropAction.IgnoreAction:
            return True
        if action != Qt.DropAction.MoveAction:
            return False
        try:
            source = int(bytes(data.data(PAGE_MIME)))
        except ValueError:
            return False
        if row >= 0:
            target = row - int(row > source)
        else:
            target = parent.row() if parent.isValid() else self.count - 1
        if not (0 <= source < self.count and 0 <= target < self.count and source != target):
            return False
        self.move_requested.emit(source, target)
        return True

    def reset(self, count: int) -> None:
        self.beginResetModel()
        self.count = count
        self.images.clear()
        self.endResetModel()

    def update_thumbnail(self, page: int, frame: PageFrame) -> None:
        self.images[page] = QIcon(frame_pixmap(frame))
        index = self.index(page)
        self.dataChanged.emit(index, index, [Qt.ItemDataRole.DecorationRole])


class ThumbnailView(QListView):
    viewport_changed = Signal()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.viewport_changed.emit()


class NavigationDock(QDockWidget):
    def __init__(self, parent: QWidget) -> None:
        super().__init__(self.tr("Páginas e índice"), parent)
        self.setObjectName("navigation_dock")
        self.setMinimumWidth(180)
        tabs = QTabWidget()
        self.document: PdfTab | None = None
        self.rotation = 0
        self.revision = -1
        self.page = -1
        self.visible_pages: set[int] = set()
        self.stack = QStackedWidget()
        self.empty = empty_panel(
            self.tr("Nenhum PDF aberto"), self.tr("Abra um PDF para navegar pelas miniaturas.")
        )
        self.stack.addWidget(self.empty)
        self.thumbnails = ThumbnailView()
        self.thumbnails.setObjectName("pdf_thumbnails")
        self.thumbnails.setAccessibleName(self.tr("Miniaturas das páginas"))
        self.thumbnails.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.thumbnails.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.thumbnails.setDropIndicatorShown(True)
        self.thumbnails.setToolTip(
            self.tr("Selecione uma página ou arraste uma miniatura para reordenar.")
        )
        self.thumbnails.setIconSize(QSize(90, 104))
        self.thumbnails.setUniformItemSizes(True)
        self.thumbnails.setLayoutMode(QListView.LayoutMode.Batched)
        self.thumbnails.setVerticalScrollMode(QListView.ScrollMode.ScrollPerPixel)
        self.thumbnails.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.model = ThumbnailModel(self.thumbnails)
        self.thumbnails.setModel(self.model)
        self.thumbnails.selectionModel().currentChanged.connect(self._go_to)
        self.stack.addWidget(self.thumbnails)
        tabs.addTab(self.stack, self.tr("Páginas"))
        tabs.addTab(
            empty_panel(
                self.tr("Índice do documento"),
                self.tr("A leitura de marcadores do PDF está prevista para uma etapa posterior."),
            ),
            self.tr("Índice"),
        )
        self.setWidget(tabs)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self._request_visible)
        self.thumbnails.viewport_changed.connect(self._schedule)
        self.thumbnails.verticalScrollBar().valueChanged.connect(self._schedule)
        self.thumbnails.verticalScrollBar().rangeChanged.connect(self._schedule)
        tabs.currentChanged.connect(self._schedule)
        self.visibilityChanged.connect(self._schedule)

    def show_document(self, document: PdfTab | None) -> None:
        viewer = document.viewer if document else None
        info = viewer.info if viewer else None
        count = info.page_count if info else 0
        rotation = viewer.rotation if viewer else 0
        revision = viewer.revision if viewer else -1
        page = viewer.page if count else -1
        self.model.moving = bool(info and info.can_organize and not viewer.busy)
        self.thumbnails.setEnabled(not (viewer and viewer.busy))
        if document is not self.document or (count, rotation, revision) != (
            self.model.count,
            self.rotation,
            self.revision,
        ):
            self.document, self.rotation = document, rotation
            self.revision = revision
            self.page = -1
            self.visible_pages.clear()
            with QSignalBlocker(self.thumbnails.selectionModel()):
                self.model.reset(count)
            self.stack.setCurrentWidget(self.thumbnails if count else self.empty)
        if count and page != self.page:
            self.page = page
            index = self.model.index(page)
            self.thumbnails.selectionModel().setCurrentIndex(
                index, QItemSelectionModel.SelectionFlag.ClearAndSelect
            )
            self.thumbnails.scrollTo(index)
        if count:
            self._schedule()

    def _schedule(self, *args) -> None:
        self.timer.start(35)

    def _request_visible(self) -> None:
        doc = self.document
        if not doc or not doc.viewer.info:
            return
        if not self.thumbnails.isVisible():
            doc.viewer.thumbnails([], 1.0)
            return
        viewport = self.thumbnails.viewport()
        rows = set()
        for y in range(2, viewport.height(), 28):
            index = self.thumbnails.indexAt(QPoint(8, y))
            if index.isValid():
                rows.add(index.row())
        self.visible_pages = rows
        self.model.images = {page: icon for page, icon in self.model.images.items() if page in rows}
        dpr = round(min(4.0, viewport.devicePixelRatioF()), 2)
        doc.viewer.thumbnails(sorted(rows.difference(self.model.images)), dpr)

    def _go_to(self, index, _previous) -> None:
        if self.document and index.isValid():
            self.document.viewer.go_to(index.row())

    def show_thumbnail(self, doc: PdfTab, page: int, frame: PageFrame) -> None:
        if doc is self.document and page in self.visible_pages:
            self.model.update_thumbnail(page, frame)


class EditorPane(QWidget):
    def __init__(self, actions: dict[str, QAction]) -> None:
        super().__init__()
        self.document: PdfTab | None = None
        self._entries: tuple = ()
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        self.state = QLabel()
        self.state.setWordWrap(True)
        self.state.setProperty("role", "muted")
        root.addWidget(self.state)

        def add_tools(label, keys):
            heading = QLabel(label)
            font = heading.font()
            font.setBold(True)
            heading.setFont(font)
            root.addWidget(heading)
            for key in keys:
                button = QToolButton()
                button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
                button.setDefaultAction(actions[key])
                root.addWidget(button)

        add_tools(
            self.tr("Adicionar à página"),
            (
                "highlight",
                "underline",
                "comment",
                "text",
                "stamp",
                "rectangle",
                "ellipse",
                "insert_image",
            ),
        )
        self.objects = QComboBox()
        self.objects.setObjectName("pdf_annotation_selector")
        self.objects.setAccessibleName(self.tr("Anotações da página"))
        self.objects.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self.objects.setMinimumContentsLength(14)
        self.objects.currentIndexChanged.connect(self._select)
        root.addWidget(self.objects)
        add_tools(self.tr("Objeto selecionado"), ("move_object", "change_object", "remove_object"))
        add_tools(self.tr("Formulários"), ("forms",))
        root.addStretch()

    def _select(self, _index: int) -> None:
        if self.document:
            self.document.select_annotation(self.objects.currentData())

    def show_document(self, document: PdfTab | None) -> None:
        viewer = document.viewer if document else None
        info = viewer.info if viewer else None
        entries = viewer.annotations if info else ()
        status = self.tr("Abra um PDF para usar as ferramentas de edição.")
        if info:
            status = self.tr("Página %1 · %2 anotação(ões) · %3 campo(s)")
            status = status.replace("%1", str(viewer.page + 1)).replace("%2", str(len(entries)))
            status = status.replace("%3", str(len(viewer.fields)))
        self.state.setText(status)
        with QSignalBlocker(self.objects):
            if entries != self._entries or self.document is not document:
                self._entries = entries
                self.objects.clear()
                self.objects.addItem(self.tr("Selecionar anotação"), None)
                for number, entry in enumerate(entries, 1):
                    self.objects.addItem(f"{number}. {ANNOTATION_LABELS[entry.kind]}", entry.xref)
            xref = document.selected_annotation if info else None
            self.objects.setCurrentIndex(max(0, self.objects.findData(xref)))
        self.document = document
        self.objects.setEnabled(bool(entries and not viewer.busy))


class PropertiesDock(QDockWidget):
    def __init__(self, actions: dict[str, QAction], parent: QWidget) -> None:
        super().__init__(self.tr("Propriedades e ferramentas"), parent)
        self.setObjectName("properties_dock")
        self.setMinimumWidth(230)
        tabs = QTabWidget()
        properties = QWidget()
        form = QFormLayout(properties)
        self.fields = {}
        for key, title in (
            ("file", "Documento:"),
            ("title", "Título:"),
            ("author", "Autor:"),
            ("page", "Página:"),
            ("size", "Dimensões:"),
            ("format", "Formato:"),
            ("rotation", "Rotação:"),
            ("access", "Acesso:"),
            ("signature", "Assinatura:"),
        ):
            label = QLabel()
            label.setTextFormat(Qt.TextFormat.PlainText)
            label.setWordWrap(True)
            label.setMaximumWidth(225)
            label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            self.fields[key] = label
            form.addRow(title, label)
        form.addRow(self.tr("Aplicativo:"), QLabel(__version__))
        form.addRow(self.tr("Modo:"), QLabel(self.tr("Local / Offline")))
        tabs.addTab(properties, self.tr("Propriedades"))
        self.editor = EditorPane(actions)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.editor)
        tabs.addTab(scroll, self.tr("Edição"))
        processing = QWidget()
        processing_layout = QVBoxLayout(processing)
        processing_layout.addWidget(QLabel(self.tr("Processamento local")))
        for key in (
            "ocr",
            "ocr_setup",
            "images",
            "images_pdf",
            "compress",
            "batch",
            "batch_report",
        ):
            button = QToolButton()
            button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
            button.setDefaultAction(actions[key])
            processing_layout.addWidget(button)
        tools = QTreeWidget()
        tools.setRootIsDecorated(False)
        tools.setHeaderLabels([self.tr("Ferramenta futura"), self.tr("Marco")])
        for name, milestone in (("LibreOffice", "Opcional"),):
            item = QTreeWidgetItem(tools, [name, milestone])
            item.setDisabled(True)
            item.setToolTip(0, self.tr("Disponível em um marco posterior."))
        tools.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        tools.header().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        processing_layout.addWidget(tools, 1)
        tabs.addTab(processing, self.tr("Ferramentas"))
        security = QWidget()
        security_layout = QVBoxLayout(security)
        for label, keys in (
            (self.tr("Proteção e privacidade"), ("metadata", "password")),
            (self.tr("Redação irreversível"), ("redact", "unmark_redaction", "export_redaction")),
            (self.tr("Assinaturas"), ("visual_sign", "digital_sign", "verify_signatures")),
        ):
            security_layout.addWidget(QLabel(label))
            for key in keys:
                button = QToolButton()
                button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
                button.setDefaultAction(actions[key])
                security_layout.addWidget(button)
        security_layout.addStretch()
        security_scroll = QScrollArea()
        security_scroll.setWidgetResizable(True)
        security_scroll.setWidget(security)
        tabs.addTab(security_scroll, self.tr("Segurança"))
        self.setWidget(tabs)
        self.show_document(None)

    def show_document(self, document: PdfTab | None) -> None:
        values = dict.fromkeys(self.fields, "—")
        values["file"] = document.viewer.session.source_path.name if document else self.tr("Nenhum")
        if document and (info := document.viewer.info):
            values.update(
                title=info.title or "—",
                author=info.author or "—",
                page=f"{document.viewer.page + 1} / {info.page_count}",
                format=info.format,
                access=self.tr("Protegido") if info.protected else self.tr("Cópia de trabalho"),
                signature=self.tr("Indicada · não verificada") if info.signed else "—",
            )
            if not info.copy_allowed:
                values["access"] += self.tr(" · cópia restrita")
            if document.viewer.signatures_checked:
                values["signature"] = self.tr("Verificação local concluída")
            if document.page_properties and document.canvas.rotation == document.viewer.rotation:
                width, height, rotation = document.page_properties
                values["size"] = f"{width * 25.4 / 72:.1f} × {height * 25.4 / 72:.1f} mm".replace(
                    ".", ","
                )
                values["rotation"] = f"{rotation}°"
        for key, value in values.items():
            self.fields[key].setText(value)
        self.editor.show_document(document)


STATE_LABELS = {
    TaskState.PENDING: "Na fila",
    TaskState.RUNNING: "Em execução",
    TaskState.CANCELLING: "Cancelamento solicitado",
    TaskState.CANCELLED: "Cancelada",
    TaskState.SUCCEEDED: "Concluída",
    TaskState.FAILED: "Falhou",
}


class JobsDock(QDockWidget):
    cancel_requested = Signal(object)

    def __init__(self, service: JobService, report: QAction, parent: QWidget) -> None:
        super().__init__(self.tr("Fila de tarefas"), parent)
        self.setObjectName("jobs_dock")
        self.service = service
        body = QWidget()
        root = QVBoxLayout(body)
        root.setContentsMargins(8, 6, 8, 6)
        row = QHBoxLayout()
        self.summary = QLabel()
        self.summary.setWordWrap(True)
        row.addWidget(self.summary, 1)
        report_button = QToolButton()
        report_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        report_button.setDefaultAction(report)
        row.addWidget(report_button)
        self.cancel_button = QPushButton(self.tr("Cancelar tarefa"))
        self.cancel_button.setToolTip(
            self.tr("Selecione uma tarefa na fila ou em andamento para cancelar.")
        )
        self.cancel_button.clicked.connect(self._cancel_selected)
        row.addWidget(self.cancel_button)
        root.addLayout(row)
        self.tree = QTreeWidget()
        self.tree.setObjectName("jobs_tree")
        self.tree.setRootIsDecorated(False)
        self.tree.setAlternatingRowColors(True)
        self.tree.setHeaderLabels(
            [
                self.tr("Tarefa"),
                self.tr("Estado"),
                self.tr("Progresso"),
                self.tr("Início"),
                self.tr("Resultado"),
            ]
        )
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tree.setMinimumHeight(60)
        self.tree.itemSelectionChanged.connect(self._selection_changed)
        root.addWidget(self.tree)
        self.setWidget(body)
        self.refresh()

    def refresh(self) -> None:
        selected = self.tree.currentItem()
        selected_id = selected.data(0, Qt.ItemDataRole.UserRole) if selected else None
        records = self.service.list_tasks()
        with QSignalBlocker(self.tree):
            self.tree.clear()
            for record in records:
                item = QTreeWidgetItem(
                    self.tree,
                    [
                        record.spec.description,
                        STATE_LABELS[record.state],
                        f"{record.progress}%",
                        record.started_at.astimezone().strftime("%H:%M:%S")
                        if record.started_at
                        else "—",
                        record.result.name if record.result else record.detail or "—",
                    ],
                )
                item.setData(0, Qt.ItemDataRole.UserRole, record.task_id)
                if record.error:
                    item.setToolTip(1, record.error)
                if record.result or record.detail:
                    item.setToolTip(
                        4,
                        "\n".join(
                            part for part in (str(record.result or ""), record.detail) if part
                        ),
                    )
                if record.task_id == selected_id:
                    self.tree.setCurrentItem(item)
        self.summary.setText(
            self.tr("Nenhuma tarefa nesta sessão")
            if not records
            else self.tr("Tarefas registradas: ") + str(len(records))
        )
        self._selection_changed()

    def _selection_changed(self) -> None:
        item = self.tree.currentItem()
        enabled = False
        if item:
            record = self.service.status(item.data(0, Qt.ItemDataRole.UserRole))
            enabled = record.state in (TaskState.PENDING, TaskState.RUNNING)
        self.cancel_button.setEnabled(enabled)

    def _cancel_selected(self) -> None:
        item = self.tree.currentItem()
        if item:
            task_id = item.data(0, Qt.ItemDataRole.UserRole)
            self.service.cancel(task_id)
            self.cancel_requested.emit(task_id)
            self.refresh()
