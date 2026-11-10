"""Janela desktop clássica. Widgets não acessam bibliotecas PDF."""

from collections.abc import Callable, Iterable
from dataclasses import dataclass, replace
from html import escape
from os.path import abspath, normcase
from pathlib import Path

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import (
    QAction,
    QActionGroup,
    QCloseEvent,
    QDragEnterEvent,
    QDragMoveEvent,
    QDropEvent,
    QKeySequence,
)
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QFileDialog,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QToolBar,
    QWidget,
)

from oldschoolpdf import __version__
from oldschoolpdf.application.capability_service import CapabilitiesService
from oldschoolpdf.application.contracts import JobService
from oldschoolpdf.application.pdf_viewer import PdfWorkspace
from oldschoolpdf.application.preferences import THEME_NAMES, Preferences
from oldschoolpdf.domain.errors import SettingsError
from oldschoolpdf.infrastructure.settings_repository import (
    LAYOUT_VERSION,
    SettingsRepository,
    WindowLayout,
)
from oldschoolpdf.ui.dialogs import PreferencesDialog
from oldschoolpdf.ui.docks import JobsDock, NavigationDock, PropertiesDock
from oldschoolpdf.ui.document_tools import DocumentTools
from oldschoolpdf.ui.edit_dialogs import local_pdf_drops
from oldschoolpdf.ui.icons import command_icon
from oldschoolpdf.ui.media_tools import MEDIA_ACTIONS, MediaTools
from oldschoolpdf.ui.pages import CapabilitiesPage, GuidePage, HomePage
from oldschoolpdf.ui.pdf_tab import ZOOM_LEVELS, PdfTab
from oldschoolpdf.ui.security_tools import SecurityTools
from oldschoolpdf.ui.themes import apply_theme


@dataclass(frozen=True, slots=True)
class FutureCommand:
    key: str
    label: str
    icon: str
    milestone: str
    shortcut: str = ""


FUTURE_COMMANDS = (
    FutureCommand("print", "Imprimir…", "print", "posterior", "Ctrl+P"),
    FutureCommand(
        "office", "Converter via LibreOffice…", "document", "opcional · validação pendente"
    ),
)

PAGE_COMMANDS = ("split", "extract", "reorder", "rotate_pages", "delete_pages")
ANNOTATION_COMMANDS = (
    ("highlight", "Destacar texto", "highlight", "highlight"),
    ("underline", "Sublinhar texto", "underline", "underline"),
    ("comment", "Adicionar comentário", "comment", "comment"),
    ("text", "Inserir caixa de texto", "text", "text"),
    ("stamp", "Aplicar carimbo", "stamp", "stamp"),
    ("rectangle", "Inserir retângulo", "rectangle", "rectangle"),
    ("ellipse", "Inserir elipse", "ellipse", "ellipse"),
    ("insert_image", "Inserir imagem", "image", "image"),
)


class MainWindow(QMainWindow):
    def __init__(
        self,
        settings: SettingsRepository,
        capabilities: CapabilitiesService,
        jobs: JobService,
        pdf_workspace: PdfWorkspace,
    ) -> None:
        super().__init__()
        self.setObjectName("oldschoolpdf_main_window")
        self.settings = settings
        self.capabilities = capabilities
        self.jobs = jobs
        self.pdf_workspace = pdf_workspace
        self.pdf_workspace.setParent(self)
        self.document_tools = DocumentTools(self)
        self.media_tools = MediaTools(self)
        self.security_tools = SecurityTools(self)
        self._active_pdf: PdfTab | None = None
        self.setAcceptDrops(True)
        self.preferences = settings.load_preferences()
        self.actions: dict[str, QAction] = {}
        self.menus: dict[str, QMenu] = {}
        self.toolbars: list[QToolBar] = []
        self.resize(1320, 880)
        self.setMinimumSize(1040, 700)
        self.setWindowIcon(command_icon("document"))
        self.setDockOptions(
            QMainWindow.DockOption.AnimatedDocks
            | QMainWindow.DockOption.AllowNestedDocks
            | QMainWindow.DockOption.AllowTabbedDocks
        )
        self._create_actions()
        self._create_workspace()
        self._create_docks()
        self._create_toolbars()
        self._create_menus()
        self._create_statusbar()
        self.resizeDocks(
            [self.navigation_dock, self.properties_dock], [205, 280], Qt.Orientation.Horizontal
        )
        self.resizeDocks([self.jobs_dock], [178], Qt.Orientation.Vertical)
        self._default_state = self.saveState(LAYOUT_VERSION)
        self.apply_preferences(self.preferences)
        self.open_page("home")
        self.layout_restored = False
        if self.preferences.restore_layout:
            layout = self.settings.load_layout()
            if layout:
                geometry_ok = self.restoreGeometry(layout.geometry)
                state_ok = self.restoreState(layout.state, LAYOUT_VERSION)
                self.layout_restored = geometry_ok and state_ok
                if not state_ok:
                    self.restore_default_layout(persist=False)
        if self.settings.warnings:
            self.statusBar().showMessage(self.settings.warnings[0])

    def _action(self, key: str, label: str, icon: str, callback) -> QAction:
        action = QAction(command_icon(icon), label, self)
        action.setObjectName("action_" + key)
        action.triggered.connect(callback)
        self.actions[key] = action
        # Ações também funcionam quando suas barras estão ocultas.
        self.addAction(action)
        return action

    def _create_actions(self) -> None:
        for key, (label, icon, mode) in MEDIA_ACTIONS.items():
            self._action(
                key,
                self.tr(label),
                icon,
                lambda checked=False, operation=mode: self.media_tools.show_batch(operation),
            )
        security = self.security_tools
        for key, label, icon, handler in (
            ("metadata", "Remover metadados…", "shield", security.metadata),
            ("password", "Proteger cópia com senha…", "shield", security.protect),
            ("redact", "Marcar área para redação", "redaction", security.mark),
            ("unmark_redaction", "Desmarcar última área", "undo", security.unmark),
            ("export_redaction", "Exportar redação rasterizada…", "save", security.redact),
            ("visual_sign", "Inserir assinatura visual…", "signature", security.visual),
            ("digital_sign", "Assinar digitalmente uma cópia…", "shield", security.sign),
            ("verify_signatures", "Verificar assinaturas digitais…", "shield", security.verify),
        ):
            action = self._action(
                key,
                self.tr(label),
                icon,
                lambda checked=False, callback=handler: self._with_pdf(callback),
            )
            action.setEnabled(False)
        self._action(
            "ocr_setup", self.tr("Configurar OCR local…"), "settings", self.media_tools.show_setup
        )
        self._action(
            "batch_report", self.tr("Relatório do lote…"), "info", self.media_tools.show_report
        )
        self._action(
            "batch_cancel", self.tr("Cancelar lote"), "close", self.media_tools.runner.cancel_all
        )
        self._action("home", self.tr("Página &inicial"), "home", lambda: self.open_page("home"))
        self._action(
            "guide", self.tr("&Guia do aplicativo"), "info", lambda: self.open_page("guide")
        )
        self._action("open", self.tr("&Abrir PDF…"), "open", self._open_pdf_dialog)
        self._action(
            "capabilities",
            self.tr("&Recursos locais"),
            "shield",
            lambda: self.open_page("capabilities"),
        )
        self._action("preferences", self.tr("&Preferências…"), "settings", self.show_preferences)
        self._action("close_tab", self.tr("Fechar &aba"), "close", self.close_current_tab)
        self._action("next_tab", self.tr("&Próxima aba"), "document", lambda: self.cycle_tab(1))
        self._action(
            "previous_tab", self.tr("Aba a&nterior"), "document", lambda: self.cycle_tab(-1)
        )
        self._action("help", self.tr("A&juda offline"), "info", lambda: self.open_page("guide"))
        self._action("quit", self.tr("&Sair"), "close", self.close)
        self._action("about", self.tr("&Sobre o Old School PDF…"), "info", self.show_about)
        self._action(
            "reset_layout",
            self.tr("Restaurar organização &padrão"),
            "settings",
            self.restore_default_layout,
        )
        for key, title, icon, callback in (
            ("find", self.tr("Buscar &texto…"), "search", PdfTab.show_search),
            ("copy", self.tr("&Copiar texto"), "document", PdfTab.copy_text),
            ("page_next", self.tr("Próxima página"), "next", lambda tab: tab.navigate(1)),
            ("page_previous", self.tr("Página anterior"), "previous", lambda tab: tab.navigate(-1)),
            ("hit_next", self.tr("Próxima ocorrência"), "next", lambda tab: tab.viewer.move_hit(1)),
            (
                "hit_previous",
                self.tr("Ocorrência anterior"),
                "previous",
                lambda tab: tab.viewer.move_hit(-1),
            ),
            ("zoom_in", self.tr("Ampliar"), "zoom_in", lambda tab: tab.step_zoom(1)),
            ("zoom_out", self.tr("Reduzir"), "zoom_out", lambda tab: tab.step_zoom(-1)),
            ("fit", self.tr("Ajustar à página"), "document", lambda tab: tab.set_zoom("page")),
            (
                "fit_width",
                self.tr("Ajustar à largura"),
                "document",
                lambda tab: tab.set_zoom("width"),
            ),
            ("rotate", self.tr("Girar visualização 90°"), "redo", lambda tab: tab.viewer.turn()),
            ("save_as", self.tr("Salvar &como…"), "save", self.document_tools.save),
            ("undo", self.tr("&Desfazer"), "undo", lambda tab: tab.viewer.step(-1)),
            ("redo", self.tr("&Refazer"), "redo", lambda tab: tab.viewer.step(1)),
            (
                "split",
                self.tr("Dividir PDF…"),
                "split",
                lambda tab: self.document_tools.ranges(tab, "split"),
            ),
            (
                "extract",
                self.tr("Extrair páginas…"),
                "document",
                lambda tab: self.document_tools.ranges(tab, "extract"),
            ),
            ("reorder", self.tr("Reordenar páginas…"), "reorder", self.document_tools.choose_move),
            (
                "rotate_pages",
                self.tr("Girar páginas do PDF…"),
                "redo",
                lambda tab: self.document_tools.ranges(tab, "rotate"),
            ),
            (
                "delete_pages",
                self.tr("Excluir páginas…"),
                "close",
                lambda tab: self.document_tools.ranges(tab, "delete"),
            ),
            ("move_object", self.tr("Mover objeto"), "select", self.document_tools.move_object),
            (
                "change_object",
                self.tr("Editar texto da anotação…"),
                "text",
                self.document_tools.change_object_text,
            ),
            (
                "remove_object",
                self.tr("Excluir anotação…"),
                "close",
                self.document_tools.remove_object,
            ),
            ("forms", self.tr("Preencher formulário…"), "form", self.document_tools.forms),
        ):
            action = self._action(
                key, title, icon, lambda checked=False, handler=callback: self._with_pdf(handler)
            )
            action.setEnabled(False)
        self._action("merge", self.tr("Mesclar PDFs…"), "merge", self.document_tools.merge)
        continuous = self._action(
            "continuous", self.tr("Rolagem contínua"), "continuous", self._continuous
        )
        continuous.setCheckable(True)
        continuous.setEnabled(False)
        for key, label, icon, kind in ANNOTATION_COMMANDS:
            action = self._action(
                key,
                self.tr(label),
                icon,
                lambda checked=False, tool=kind: self._with_pdf(
                    lambda tab: self.document_tools.place(tab, tool)
                ),
            )
            action.setEnabled(False)
        self.actions["copy"].setShortcutContext(Qt.ShortcutContext.WidgetShortcut)
        selection = self._action(
            "select", self.tr("Selecionar área de texto"), "select", self._select_text
        )
        selection.setCheckable(True)
        selection.setEnabled(False)
        for command in FUTURE_COMMANDS:
            action = QAction(
                command_icon(command.icon), f"{command.label}  [{command.milestone} · futuro]", self
            )
            action.setObjectName("action_" + command.key)
            action.setIconText(
                command.label.replace("…", "") + " · " + command.milestone.split(" · ")[0]
            )
            reason = self.tr("Recurso futuro: ") + command.milestone + "."
            action.setToolTip(command.label + " — " + reason)
            action.setStatusTip(reason)
            if command.shortcut:
                action.setShortcut(QKeySequence(command.shortcut))
            action.setEnabled(False)
            self.actions[command.key] = action

    def _create_workspace(self) -> None:
        self.tabs = QTabWidget()
        self.tabs.setObjectName("workspace_tabs")
        self.tabs.setAccessibleName(self.tr("Abas da área de trabalho"))
        self.tabs.setDocumentMode(True)
        self.tabs.setTabsClosable(True)
        self.tabs.setMovable(True)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.tabs.currentChanged.connect(self._update_tab_actions)
        home = QPushButton(command_icon("home"), self.tr("Início"))
        home.setToolTip(self.tr("Abrir página inicial"))
        home.clicked.connect(lambda: self.open_page("home"))
        self.tabs.setCornerWidget(home)
        self.setCentralWidget(self.tabs)

    def _create_docks(self) -> None:
        self.navigation_dock = NavigationDock(self)
        self.navigation_dock.model.move_requested.connect(
            lambda source, target: self._with_pdf(
                lambda tab: self.document_tools.move_page(tab, source, target)
            )
        )
        self.properties_dock = PropertiesDock(self.actions, self)
        self.jobs_dock = JobsDock(self.jobs, self.actions["batch_report"], self)
        self.pdf_workspace.jobs_changed.connect(self.jobs_dock.refresh)
        self.jobs_dock.cancel_requested.connect(self.pdf_workspace.cancel_job)
        self.jobs_dock.cancel_requested.connect(self.document_tools.cancel_merge)
        self.jobs_dock.cancel_requested.connect(self.media_tools.runner.cancel)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.navigation_dock)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.properties_dock)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.jobs_dock)
        self.docks = [self.navigation_dock, self.properties_dock, self.jobs_dock]

    def _toolbar(self, title: str, name: str, keys: tuple[str, ...]) -> QToolBar:
        toolbar = QToolBar(title, self)
        toolbar.setObjectName(name)
        toolbar.setMovable(True)
        toolbar.setFloatable(True)
        toolbar.setAttribute(Qt.WidgetAttribute.WA_AlwaysShowToolTips, True)
        for key in keys:
            if key == "|":
                toolbar.addSeparator()
            else:
                toolbar.addAction(self.actions[key])
        self.addToolBar(toolbar)
        self.toolbars.append(toolbar)
        return toolbar

    def _create_toolbars(self) -> None:
        self._toolbar(
            self.tr("Arquivo e sessão"),
            "file_toolbar",
            (
                "home",
                "|",
                "open",
                "save_as",
                "print",
                "|",
                "preferences",
            ),
        )
        self.addToolBarBreak()
        annotation = self._toolbar(
            self.tr("Edição e visualização"),
            "edit_toolbar",
            (
                "undo",
                "redo",
                "|",
                "select",
                "find",
                "|",
                "zoom_out",
            ),
        )
        self.zoom_combo = QComboBox()
        self.zoom_combo.setAccessibleName(self.tr("Zoom do PDF"))
        self.zoom_combo.addItem(self.tr("Ajustar página"), "page")
        self.zoom_combo.addItem(self.tr("Ajustar largura"), "width")
        for zoom in ZOOM_LEVELS:
            self.zoom_combo.addItem(f"{zoom:.0%}", zoom)
        self.zoom_combo.setEnabled(False)
        self.zoom_combo.setToolTip(self.tr("Escala de visualização da página"))
        self.zoom_combo.activated.connect(self._set_pdf_zoom)
        annotation.addWidget(self.zoom_combo)
        annotation.addAction(self.actions["zoom_in"])
        annotation.addAction(self.actions["rotate"])
        annotation.addAction(self.actions["continuous"])
        self.addToolBarBreak()
        self._toolbar(
            self.tr("Ferramentas de documentos"),
            "tools_toolbar",
            (
                "merge",
                "split",
                "extract",
                "|",
                "highlight",
                "underline",
                "comment",
                "text",
                "forms",
                "|",
                "ocr",
                "batch",
                "|",
                "redact",
                "visual_sign",
            ),
        )

    def _menu(self, key: str, title: str, keys: tuple[str, ...] = ()) -> QMenu:
        menu = self.menuBar().addMenu(title)
        menu.setObjectName("menu_" + key)
        menu.setToolTipsVisible(True)
        self.menus[key] = menu
        for action in keys:
            if action == "|":
                menu.addSeparator()
            else:
                menu.addAction(self.actions[action])
        return menu

    def _create_menus(self) -> None:
        self._menu(
            "file",
            self.tr("&Arquivo"),
            (
                "home",
                "open",
                "save_as",
                "print",
                "|",
                "merge",
                "split",
                "|",
                "close_tab",
                "quit",
            ),
        )
        edit = self._menu(
            "edit",
            self.tr("&Editar"),
            (
                "undo",
                "redo",
                "|",
                "find",
                "hit_previous",
                "hit_next",
                "copy",
                "|",
                "select",
            ),
        )
        annotations = edit.addMenu(self.tr("&Anotações"))
        for key, *_ in ANNOTATION_COMMANDS:
            annotations.addAction(self.actions[key])
        annotations.addSeparator()
        for key in ("move_object", "change_object", "remove_object"):
            annotations.addAction(self.actions[key])
        view = self._menu("view", self.tr("E&xibir"))
        panels = view.addMenu(self.tr("&Painéis"))
        for dock in self.docks:
            panels.addAction(dock.toggleViewAction())
        bars = view.addMenu(self.tr("&Barras de ferramentas"))
        for toolbar in self.toolbars:
            bars.addAction(toolbar.toggleViewAction())
        theme_menu = view.addMenu(self.tr("&Tema"))
        self.theme_group = QActionGroup(self)
        self.theme_group.setExclusive(True)
        self.theme_actions: dict[str, QAction] = {}
        for name in THEME_NAMES:
            action = theme_menu.addAction(name)
            action.setCheckable(True)
            self.theme_group.addAction(action)
            action.triggered.connect(lambda checked=False, theme=name: self.change_theme(theme))
            self.theme_actions[name] = action
        self.text_action = view.addAction(self.tr("Texto sob os ícones"))
        self.text_action.setCheckable(True)
        self.text_action.triggered.connect(self._toggle_toolbar_text)
        view.addSeparator()
        for key in (
            "zoom_in",
            "zoom_out",
            "fit",
            "fit_width",
            "continuous",
            "rotate",
            "reset_layout",
        ):
            view.addAction(self.actions[key])
        self._menu(
            "document",
            self.tr("&Documento"),
            (
                "page_previous",
                "page_next",
                "|",
                "merge",
                *PAGE_COMMANDS,
                "|",
                "stamp",
                "forms",
            ),
        )
        self._menu(
            "tools",
            self.tr("&Ferramentas"),
            (
                "preferences",
                "capabilities",
                "|",
                "images",
                "images_pdf",
                "extract_text",
                "extract_images",
                "office",
                "compress",
                "|",
                "batch",
                "batch_report",
                "batch_cancel",
            ),
        )
        ocr = self._menu("ocr", self.tr("&OCR"), ("ocr", "ocr_setup", "|", "capabilities"))
        ocr.aboutToShow.connect(self.media_tools.update_controls)
        self._menu(
            "security",
            self.tr("&Segurança"),
            (
                "metadata",
                "password",
                "|",
                "redact",
                "unmark_redaction",
                "export_redaction",
                "|",
                "visual_sign",
                "digital_sign",
                "verify_signatures",
            ),
        )
        self.window_menu = self._menu("window", self.tr("&Janela"))
        self.window_menu.aboutToShow.connect(self._populate_window_menu)
        self._menu("help", self.tr("Aj&uda"), ("help", "guide", "capabilities", "|", "about"))

    def _create_statusbar(self) -> None:
        bar = self.statusBar()
        bar.setObjectName("main_statusbar")
        self.document_status = QLabel(self.tr("Sem documento  |  Página —/—  |  Zoom —"))
        self.document_status.setObjectName("document_status")
        bar.addPermanentWidget(self.document_status)
        offline = QLabel(self.tr("Local / Offline"))
        offline.setObjectName("offline_status")
        offline.setProperty("role", "badge")
        offline.setAccessibleName(self.tr("Modo local e offline"))
        bar.addPermanentWidget(offline)
        bar.showMessage(self.tr("Pronto para abrir um PDF"))

    def open_page(self, key: str) -> QWidget:
        for index in range(self.tabs.count()):
            page = self.tabs.widget(index)
            if page.property("page_key") == key:
                if isinstance(page, CapabilitiesPage):
                    page.refresh()
                self.tabs.setCurrentIndex(index)
                return page
        if key == "home":
            page = HomePage()
            page.open_requested.connect(self._open_pdf_dialog)
            page.guide_requested.connect(lambda: self.open_page("guide"))
            page.preferences_requested.connect(self.show_preferences)
            page.capabilities_requested.connect(lambda: self.open_page("capabilities"))
            title = self.tr("Início")
        elif key == "guide":
            page = GuidePage()
            title = self.tr("Guia do aplicativo")
        elif key == "capabilities":
            page = CapabilitiesPage(self.capabilities)
            title = self.tr("Recursos locais")
        else:
            raise ValueError("Página interna desconhecida.")
        page.setProperty("page_key", key)
        index = self.tabs.addTab(page, command_icon("document" if key == "home" else "info"), title)
        self.tabs.setTabToolTip(index, self.tr("Ajuda local · ") + title)
        self.tabs.setCurrentIndex(index)
        return page

    def close_tab(self, index: int) -> None:
        page = self.tabs.widget(index)
        if page is not None:
            if isinstance(page, PdfTab):
                if not self.document_tools.may_close_tab(page):
                    return
                page.viewer.close()
            self.tabs.removeTab(index)
            self._update_tab_actions()
            page.deleteLater()

    def close_current_tab(self) -> None:
        self.close_tab(self.tabs.currentIndex())

    def cycle_tab(self, direction: int) -> None:
        if self.tabs.count():
            self.tabs.setCurrentIndex((self.tabs.currentIndex() + direction) % self.tabs.count())

    def _update_tab_actions(self) -> None:
        self.actions["close_tab"].setEnabled(self.tabs.count() > 0)
        self.actions["next_tab"].setEnabled(self.tabs.count() > 1)
        self.actions["previous_tab"].setEnabled(self.tabs.count() > 1)
        title = (
            self.tabs.tabText(self.tabs.currentIndex())
            if self.tabs.count()
            else self.tr("Área de trabalho")
        )
        current = self.tabs.currentWidget()
        current_pdf = current if isinstance(current, PdfTab) else None
        if current_pdf is not self._active_pdf:
            if self._active_pdf:
                self._active_pdf.set_active(False)
            self._active_pdf = current_pdf
            self.statusBar().clearMessage()
            if current_pdf:
                current_pdf.set_active(True)
        self.setWindowTitle(f"{title} — Old School PDF")
        self._update_pdf_controls()

    def _open_pdf_dialog(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self, self.tr("Abrir PDFs locais"), "", self.tr("Arquivos PDF (*.pdf)")
        )
        self.open_pdfs(Path(path) for path in paths)

    def open_pdfs(self, paths: Iterable[Path]) -> list[PdfTab]:
        opened = []
        for path in paths:
            absolute = Path(abspath(path))
            existing = next(
                (
                    tab
                    for tab in self._pdf_tabs()
                    if normcase(tab.viewer.session.source_path) == normcase(absolute)
                ),
                None,
            )
            if existing:
                self.tabs.setCurrentWidget(existing)
                opened.append(existing)
                continue
            tab = PdfTab(self.pdf_workspace.open(absolute))
            tab.canvas.addAction(self.actions["copy"])
            tab.updated.connect(self._update_pdf_controls)
            tab.close_requested.connect(
                lambda widget=tab: self.close_tab(self.tabs.indexOf(widget))
            )
            tab.feedback.connect(lambda message, widget=tab: self._pdf_feedback(widget, message))
            tab.placement_ready.connect(
                lambda kind, region, widget=tab: self._apply_placement(widget, kind, region)
            )
            tab.viewer.signatures_ready.connect(
                lambda reports, widget=tab: self.security_tools.report(widget, reports)
            )
            tab.viewer.thumbnail_ready.connect(
                lambda page, frame, widget=tab: self.navigation_dock.show_thumbnail(
                    widget, page, frame
                )
            )
            tab.viewer.search_changed.connect(self._update_pdf_controls)
            index = self.tabs.addTab(
                tab, command_icon("document"), absolute.name.replace("&", "&&")
            )
            self.tabs.setTabToolTip(index, escape(absolute.name))
            self.tabs.setCurrentIndex(index)
            opened.append(tab)
        return opened

    def _pdf_tabs(self) -> Iterable[PdfTab]:
        return (
            tab
            for index in range(self.tabs.count())
            if isinstance(tab := self.tabs.widget(index), PdfTab)
        )

    def _pdf_feedback(self, tab: PdfTab, message: str) -> None:
        if tab is self._active_pdf:
            self.statusBar().showMessage(message, 8000)

    def _apply_placement(self, tab: PdfTab, kind: str, region) -> None:
        if kind in {"redact", "visual_signature"}:
            self.security_tools.placed(tab, kind, region)
        else:
            self.document_tools.placed(tab, kind, region)

    def _with_pdf(self, callback: Callable[[PdfTab], None]) -> None:
        if self._active_pdf and self._active_pdf.viewer.info and not self._active_pdf.viewer.busy:
            callback(self._active_pdf)

    def _select_text(self, checked: bool) -> None:
        self._with_pdf(lambda tab: tab.set_selection_enabled(checked))

    def _continuous(self, checked: bool) -> None:
        self._with_pdf(lambda tab: tab.set_continuous(checked))

    def _set_pdf_zoom(self, index: int) -> None:
        self._with_pdf(lambda tab: tab.set_zoom(self.zoom_combo.itemData(index)))

    def _update_pdf_controls(self) -> None:
        tab = self._active_pdf
        viewer = tab.viewer if tab else None
        info = viewer.info if viewer else None
        ready = bool(info and not viewer.busy)
        continuous = bool(info and tab.continuous_enabled)
        annotating = bool(ready and info.can_annotate and (tab.canvas.has_page or continuous))
        obj = tab.annotation() if annotating else None
        self.security_tools.update_controls(tab)
        for key in (
            "find",
            "zoom_in",
            "zoom_out",
            "fit",
            "fit_width",
            "continuous",
            "rotate",
            "save_as",
        ):
            self.actions[key].setEnabled(ready)
        for key in PAGE_COMMANDS:
            self.actions[key].setEnabled(bool(ready and info.can_organize))
        for key, *_ in ANNOTATION_COMMANDS:
            self.actions[key].setEnabled(annotating)
        self.actions["continuous"].setChecked(continuous)
        self.actions["forms"].setEnabled(
            bool(ready and info.can_fill and any(f.editable for f in viewer.fields))
        )
        self.actions["move_object"].setEnabled(bool(obj and obj.movable))
        self.actions["change_object"].setEnabled(
            bool(obj and obj.editable and obj.kind in {"comment", "text", "highlight", "underline"})
        )
        self.actions["remove_object"].setEnabled(bool(obj and obj.editable))
        self.actions["undo"].setEnabled(bool(ready and viewer.can_undo))
        self.actions["redo"].setEnabled(bool(ready and viewer.can_redo))
        self.actions["copy"].setEnabled(bool(ready and info.copy_allowed and not continuous))
        self.actions["select"].setEnabled(
            bool(ready and info.copy_allowed and tab.canvas.has_page and not continuous)
        )
        self.actions["select"].setChecked(
            bool(info and info.copy_allowed and tab.selection_enabled and not continuous)
        )
        self.actions["page_previous"].setEnabled(bool(ready and viewer.page > 0))
        self.actions["page_next"].setEnabled(bool(ready and viewer.page + 1 < info.page_count))
        for key in ("hit_next", "hit_previous"):
            self.actions[key].setEnabled(
                bool(ready and len(viewer.hits) > 1 and not tab.search.isHidden())
            )
        self.zoom_combo.setEnabled(ready)
        for document in self._pdf_tabs():
            name = document.viewer.session.source_path.name.replace("&", "&&")
            if document.viewer.session.dirty:
                name += " *"
            self.tabs.setTabText(self.tabs.indexOf(document), name)
        if tab:
            title = viewer.session.source_path.name + (" *" if viewer.session.dirty else "")
            self.setWindowTitle(f"{title} — Old School PDF")
        if info:
            self.zoom_combo.setCurrentIndex(
                self.zoom_combo.findData(tab.fit or viewer.session.zoom)
            )
            zoom = f"{tab.actual_zoom:.0%}" if tab.actual_zoom is not None else "—"
            if continuous:
                zoom = self.tr("Ajuste contínuo")
            self.document_status.setText(
                self.tr("Página %1/%2  |  Zoom %3  |  %4")
                .replace("%1", str(viewer.page + 1))
                .replace("%2", str(info.page_count))
                .replace("%3", zoom)
                .replace("%4", viewer.busy or tab.document_status())
            )
        else:
            self.document_status.setText(viewer.notice if viewer else self.tr("Sem documento"))
        self.navigation_dock.show_document(tab)
        self.properties_dock.show_document(tab)

    def _populate_window_menu(self) -> None:
        self.window_menu.clear()
        for key in ("close_tab", "next_tab", "previous_tab"):
            self.window_menu.addAction(self.actions[key])
        self.window_menu.addSeparator()
        for index in range(self.tabs.count()):
            page = self.tabs.widget(index)
            action = self.window_menu.addAction(self.tabs.tabText(index))
            action.setCheckable(True)
            action.setChecked(index == self.tabs.currentIndex())
            action.triggered.connect(
                lambda checked=False, widget=page: self.tabs.setCurrentWidget(widget)
            )

    def apply_preferences(self, preferences: Preferences) -> None:
        self.preferences = preferences
        self.pdf_workspace.configure(preferences.pdf_cache_mib, preferences.pdf_parallelism)
        app = QApplication.instance()
        assert isinstance(app, QApplication)
        apply_theme(app, preferences.theme)
        self.theme_actions[preferences.theme].setChecked(True)
        self.text_action.setChecked(preferences.text_under_icons)
        style = (
            Qt.ToolButtonStyle.ToolButtonTextUnderIcon
            if preferences.text_under_icons
            else Qt.ToolButtonStyle.ToolButtonTextBesideIcon
        )
        for toolbar in self.toolbars:
            toolbar.setIconSize(QSize(preferences.icon_size, preferences.icon_size))
            toolbar.setToolButtonStyle(style)
        for key, shortcut in preferences.shortcuts.items():
            if key in self.actions:
                self.actions[key].setShortcut(QKeySequence(shortcut))
        self.media_tools.update_controls()
        if isinstance(page := self.tabs.currentWidget(), CapabilitiesPage):
            page.refresh()

    def change_theme(self, name: str) -> None:
        self.apply_preferences(replace(self.preferences, theme=name))
        self._save_or_warn()
        self.statusBar().showMessage(self.tr("Tema aplicado: ") + name, 5000)

    def _toggle_toolbar_text(self, checked: bool) -> None:
        self.apply_preferences(replace(self.preferences, text_under_icons=checked))
        self._save_or_warn()

    def show_preferences(self) -> None:
        dialog = PreferencesDialog(self.preferences, str(self.settings.path), self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.apply_preferences(dialog.preferences())
            self._save_or_warn()

    def restore_default_layout(self, checked: bool = False, *, persist: bool = True) -> None:
        self.restoreState(self._default_state, LAYOUT_VERSION)
        self.resizeDocks(
            [self.navigation_dock, self.properties_dock], [205, 280], Qt.Orientation.Horizontal
        )
        self.resizeDocks([self.jobs_dock], [178], Qt.Orientation.Vertical)
        if persist:
            self._save_or_warn()

    def save_settings(self) -> None:
        self.settings.save(
            self.preferences,
            WindowLayout(self.saveGeometry(), self.saveState(LAYOUT_VERSION)),
        )

    def _save_or_warn(self) -> bool:
        try:
            self.save_settings()
            return True
        except SettingsError as error:
            QMessageBox.warning(self, self.tr("Preferências não salvas"), str(error))
            return False

    def show_about(self) -> None:
        QMessageBox.about(
            self,
            self.tr("Sobre o Old School PDF"),
            f"<h2>Old School PDF {__version__}</h2>"
            + self.tr(
                "<p><b>M5 · Segurança e assinaturas locais</b></p>"
                "<p>Leitura, edição, OCR local e operações de segurança com PyMuPDF.</p>"
                "<p>Sem login, mensalidade, marca-d'água ou "
                "telemetria. Código sob AGPL-3.0-or-later.</p>"
                "<p>Interface: PySide6 / Qt, opção LGPLv3. "
                "Ícones originais do projeto. Consulte LICENSE e THIRD_PARTY_NOTICES.md.</p>"
            ),
        )

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            if local_pdf_drops(event):
                event.setDropAction(Qt.DropAction.CopyAction)
                event.accept()
            else:
                event.ignore()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event: QDragMoveEvent) -> None:
        if event.mimeData().hasUrls():
            if local_pdf_drops(event):
                event.setDropAction(Qt.DropAction.CopyAction)
                event.accept()
            else:
                event.ignore()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event: QDropEvent) -> None:
        if event.mimeData().hasUrls():
            if paths := local_pdf_drops(event):
                event.setDropAction(Qt.DropAction.CopyAction)
                event.accept()
                self.open_pdfs(paths)
            else:
                event.ignore()
        else:
            super().dropEvent(event)

    def closeEvent(self, event: QCloseEvent) -> None:
        if self.media_tools.runner.active:
            self.statusBar().showMessage(
                self.tr("Aguarde o lote ou cancele pela fila de tarefas."), 8000
            )
            event.ignore()
            return
        if not self.document_tools.may_close_window():
            event.ignore()
            return
        while True:
            try:
                self.save_settings()
                self.pdf_workspace.close()
                event.accept()
                return
            except SettingsError as error:
                dialog = QMessageBox(
                    QMessageBox.Icon.Warning,
                    self.tr("Preferências não salvas"),
                    str(error),
                    QMessageBox.StandardButton.Retry
                    | QMessageBox.StandardButton.Discard
                    | QMessageBox.StandardButton.Cancel,
                    self,
                )
                dialog.button(QMessageBox.StandardButton.Retry).setText(self.tr("Tentar novamente"))
                dialog.button(QMessageBox.StandardButton.Discard).setText(
                    self.tr("Sair sem salvar preferências")
                )
                dialog.button(QMessageBox.StandardButton.Cancel).setText(self.tr("Cancelar"))
                dialog.setDefaultButton(QMessageBox.StandardButton.Cancel)
                result = dialog.exec()
                if result == QMessageBox.StandardButton.Retry:
                    continue
                if result == QMessageBox.StandardButton.Discard:
                    self.pdf_workspace.close()
                    event.accept()
                else:
                    event.ignore()
                return
