"""Preferências de aparência, leitura e atalhos."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QKeySequenceEdit,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from oldschoolpdf.application.preferences import DEFAULT_SHORTCUTS, THEME_NAMES, Preferences

ACTION_LABELS = {
    "home": "Página inicial",
    "guide": "Guia do aplicativo",
    "capabilities": "Recursos locais",
    "preferences": "Preferências",
    "close_tab": "Fechar aba",
    "next_tab": "Próxima aba",
    "previous_tab": "Aba anterior",
    "help": "Ajuda offline",
    "quit": "Sair",
    "open": "Abrir PDF",
    "find": "Buscar texto",
    "copy": "Copiar texto",
    "zoom_in": "Ampliar",
    "zoom_out": "Reduzir",
    "page_next": "Próxima página",
    "page_previous": "Página anterior",
    "hit_next": "Próxima ocorrência",
    "hit_previous": "Ocorrência anterior",
    "save_as": "Salvar como",
    "undo": "Desfazer edição do PDF",
    "redo": "Refazer edição do PDF",
    "redact": "Marcar área para redação",
}


class PreferencesDialog(QDialog):
    def __init__(self, preferences: Preferences, settings_path: str, parent: QWidget) -> None:
        super().__init__(parent)
        self.setObjectName("preferences_dialog")
        self.setWindowTitle(self.tr("Preferências — Old School PDF"))
        self.resize(620, 540)
        self.setMinimumSize(540, 420)
        self._preferences = preferences
        root = QVBoxLayout(self)
        self.tabs = QTabWidget()
        root.addWidget(self.tabs)

        appearance = QWidget()
        form = QFormLayout(appearance)
        self.theme_combo = QComboBox()
        self.theme_combo.setObjectName("theme_combo")
        self.theme_combo.addItems(THEME_NAMES)
        self.theme_combo.setCurrentText(preferences.theme)
        form.addRow(self.tr("&Tema:"), self.theme_combo)
        self.icon_combo = QComboBox()
        self.icon_combo.setObjectName("icon_size_combo")
        for size in (20, 24, 32):
            self.icon_combo.addItem(f"{size} × {size} px", size)
        self.icon_combo.setCurrentIndex(self.icon_combo.findData(preferences.icon_size))
        form.addRow(self.tr("Tamanho dos í&cones:"), self.icon_combo)
        self.text_under = QCheckBox(self.tr("Mostrar texto sob os ícones"))
        self.text_under.setChecked(preferences.text_under_icons)
        form.addRow(self.text_under)
        self.restore = QCheckBox(self.tr("Restaurar geometria e painéis ao iniciar"))
        self.restore.setChecked(preferences.restore_layout)
        form.addRow(self.restore)
        note = QLabel(
            self.tr(
                "As alterações são aplicadas ao confirmar. Os temas também podem ser "
                "alternados imediatamente pelo menu Exibir > Tema."
            )
        )
        note.setWordWrap(True)
        form.addRow(note)
        self.tabs.addTab(appearance, self.tr("Aparência e janela"))

        reader = QWidget()
        reader_form = QFormLayout(reader)
        self.cache_size = QSpinBox()
        self.cache_size.setRange(16, 256)
        self.cache_size.setSingleStep(16)
        self.cache_size.setSuffix(" MiB")
        self.cache_size.setValue(preferences.pdf_cache_mib)
        reader_form.addRow(self.tr("&Cache de páginas"), self.cache_size)
        self.parallelism = QSpinBox()
        self.parallelism.setRange(1, 4)
        self.parallelism.setValue(preferences.pdf_parallelism)
        reader_form.addRow(self.tr("&Operações PDF simultâneas"), self.parallelism)
        reader_note = QLabel(
            self.tr(
                "O cache guarda imagens de páginas na memória. Abertura, renderização e busca "
                "compartilham o limite de operações. A leitura tem prazo de 20 segundos por "
                "operação. Edição e exportação têm prazo de 120 segundos."
            )
        )
        reader_note.setWordWrap(True)
        reader_form.addRow(reader_note)
        self.tabs.addTab(reader, self.tr("Visualizador"))

        shortcuts_page = QWidget()
        shortcuts_layout = QVBoxLayout(shortcuts_page)
        shortcuts_layout.addWidget(
            QLabel(
                self.tr(
                    "Clique no campo e pressione o atalho desejado. Um campo vazio remove o atalho."
                )
            )
        )
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        shortcut_form = QFormLayout(container)
        self.shortcut_editors: dict[str, QKeySequenceEdit] = {}
        for key, label in ACTION_LABELS.items():
            editor = QKeySequenceEdit(QKeySequence(preferences.shortcuts.get(key, "")))
            editor.setMaximumSequenceLength(1)
            editor.setClearButtonEnabled(True)
            editor.setAccessibleName(self.tr("Atalho: ") + label)
            self.shortcut_editors[key] = editor
            shortcut_form.addRow(label + ":", editor)
        scroll.setWidget(container)
        shortcuts_layout.addWidget(scroll)
        reset = QPushButton(self.tr("Restaurar atalhos padrão"))
        reset.clicked.connect(self._reset_shortcuts)
        shortcuts_layout.addWidget(reset)
        self.tabs.addTab(shortcuts_page, self.tr("Atalhos"))

        local = QWidget()
        local_form = QFormLayout(local)
        local_form.addRow(self.tr("Idioma:"), QLabel(self.tr("Português (Brasil)")))
        path = QLabel(settings_path)
        path.setWordWrap(True)
        path.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        local_form.addRow(self.tr("Arquivo local:"), path)
        privacy = QLabel(
            self.tr(
                "O aplicativo não faz chamadas de rede, não envia documentos e não "
                "possui telemetria. O histórico de edição usa arquivos temporários locais "
                "enquanto a aba está aberta. Senhas ficam na memória durante a sessão."
            )
        )
        privacy.setWordWrap(True)
        local_form.addRow(privacy)
        self.tabs.addTab(local, self.tr("Local e privacidade"))

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText(self.tr("Aplicar e fechar"))
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(self.tr("Cancelar"))
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def _reset_shortcuts(self) -> None:
        for key, editor in self.shortcut_editors.items():
            editor.setKeySequence(QKeySequence(DEFAULT_SHORTCUTS[key]))

    def accept(self) -> None:
        seen: dict[str, str] = {}
        for key, editor in self.shortcut_editors.items():
            value = editor.keySequence().toString(QKeySequence.SequenceFormat.PortableText)
            if value and value in seen:
                QMessageBox.warning(
                    self,
                    self.tr("Atalho duplicado"),
                    self.tr("Escolha atalhos diferentes para ")
                    + ACTION_LABELS[seen[value]]
                    + self.tr(" e ")
                    + ACTION_LABELS[key]
                    + ".",
                )
                return
            if value:
                seen[value] = key
        super().accept()

    def preferences(self) -> Preferences:
        return Preferences(
            theme=self.theme_combo.currentText(),
            icon_size=self.icon_combo.currentData(),
            text_under_icons=self.text_under.isChecked(),
            restore_layout=self.restore.isChecked(),
            shortcuts={
                key: edit.keySequence().toString(QKeySequence.SequenceFormat.PortableText)
                for key, edit in self.shortcut_editors.items()
            },
            pdf_cache_mib=self.cache_size.value(),
            pdf_parallelism=self.parallelism.value(),
            ocr_tessdata=self._preferences.ocr_tessdata,
            ocr_languages=self._preferences.ocr_languages,
        )
