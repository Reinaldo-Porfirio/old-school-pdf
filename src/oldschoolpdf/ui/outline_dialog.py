"""Editor dos marcadores (sumário) do PDF, com lista à esquerda e propriedades à direita."""

from contextlib import suppress

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from oldschoolpdf.application.pdf_viewer import PdfViewer
from oldschoolpdf.domain.editing import (
    MAX_OUTLINE_DEPTH,
    MAX_OUTLINE_ENTRIES,
    MAX_TITLE_LENGTH,
    OutlineEntry,
    normalize_levels,
)

INDENT = "      "


class OutlineDialog(QDialog):
    def __init__(self, viewer: PdfViewer, parent) -> None:
        super().__init__(parent)
        self.setObjectName("outline_dialog")
        self.setWindowTitle("Marcadores do PDF")
        self.resize(720, 500)
        self.viewer = viewer
        self.signature = viewer.outline_signature
        self.count = viewer.info.page_count
        self.entries: list[dict] = [
            {
                "level": entry.level,
                "title": entry.title,
                "page": entry.page,
                "source": index,
                "external": entry.external,
            }
            for index, entry in enumerate(viewer.outline)
        ]
        self.modified = False
        root = QVBoxLayout(self)
        intro = QLabel(
            "Os marcadores formam o sumário que aparece nos leitores de PDF. Organize a lista, "
            "use Recuar e Avançar para montar os níveis e aplique quando terminar."
        )
        intro.setWordWrap(True)
        root.addWidget(intro)
        body = QHBoxLayout()
        self.list = QListWidget()
        self.list.setObjectName("outline_list")
        self.list.setAccessibleName("Marcadores")
        self.list.currentRowChanged.connect(self._selected)
        self.list.itemDoubleClicked.connect(self._go_to)
        body.addWidget(self.list, 3)
        side = QVBoxLayout()
        props = QGroupBox("Marcador selecionado")
        form = QFormLayout(props)
        self.title = QLineEdit()
        self.title.setObjectName("outline_title")
        self.title.setMaxLength(MAX_TITLE_LENGTH)
        self.title.textEdited.connect(self._title_edited)
        form.addRow("Título:", self.title)
        self.page = QSpinBox()
        self.page.setObjectName("outline_page")
        self.page.setRange(1, self.count)
        self.page.valueChanged.connect(self._page_edited)
        form.addRow("Página:", self.page)
        self.kind = QLabel()
        self.kind.setProperty("role", "muted")
        self.kind.setWordWrap(True)
        form.addRow(self.kind)
        side.addWidget(props)
        self.buttons: dict[str, QPushButton] = {}
        for key, label, handler in (
            ("add", "Adicionar marcador da página atual", self._add),
            ("remove", "Excluir", self._remove),
            ("up", "Subir", lambda: self._move(-1)),
            ("down", "Descer", lambda: self._move(1)),
            ("outdent", "← Recuar nível", lambda: self._indent(-1)),
            ("indent", "Avançar nível →", lambda: self._indent(1)),
            ("suggest", "Sugerir pelos títulos do texto…", self._suggest),
            ("clear", "Excluir todos", self._clear),
        ):
            button = QPushButton(label)
            button.setObjectName("outline_" + key)
            button.clicked.connect(handler)
            side.addWidget(button)
            self.buttons[key] = button
        side.addStretch()
        body.addLayout(side, 2)
        root.addLayout(body, 1)
        self.status = QLabel()
        self.status.setWordWrap(True)
        root.addWidget(self.status)
        box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.apply = box.button(QDialogButtonBox.StandardButton.Ok)
        self.apply.setText("Aplicar ao PDF")
        box.accepted.connect(self.accept)
        box.rejected.connect(self.reject)
        root.addWidget(box)
        viewer.outline_suggested.connect(self._suggested)
        viewer.outline_suggest_failed.connect(self._suggest_failed)
        viewer.changed.connect(self._refresh_buttons)
        self.finished.connect(self._disconnect)
        self._rebuild(0)

    # Lista
    def _label(self, entry: dict) -> str:
        page = (
            "link externo"
            if entry["external"]
            else (f"pág. {entry['page'] + 1}" if entry["page"] >= 0 else "sem destino")
        )
        return f"{INDENT * (entry['level'] - 1)}{entry['title']}    ({page})"

    def _rebuild(self, row: int) -> None:
        self.list.blockSignals(True)
        self.list.clear()
        for entry in self.entries:
            item = QListWidgetItem(self._label(entry))
            item.setToolTip(entry["title"])
            self.list.addItem(item)
        self.list.blockSignals(False)
        if self.entries:
            self.list.setCurrentRow(max(0, min(row, len(self.entries) - 1)))
        self._selected(self.list.currentRow())

    def _current(self) -> dict | None:
        row = self.list.currentRow()
        return self.entries[row] if 0 <= row < len(self.entries) else None

    def _selected(self, _row: int) -> None:
        entry = self._current()
        self.title.blockSignals(True)
        self.page.blockSignals(True)
        self.title.setText(entry["title"] if entry else "")
        if entry and entry["page"] >= 0:
            self.page.setValue(entry["page"] + 1)
        self.title.blockSignals(False)
        self.page.blockSignals(False)
        self.title.setEnabled(entry is not None)
        self.page.setEnabled(bool(entry and not entry["external"]))
        if entry is None:
            self.kind.setText("")
        elif entry["external"]:
            self.kind.setText("Este marcador abre um link ou arquivo externo; o destino é mantido.")
        elif entry["page"] < 0:
            self.kind.setText("A página de destino foi removida. Escolha uma página nova.")
        else:
            self.kind.setText("Clique duas vezes na lista para ver a página.")
        self._refresh_buttons()

    def _refresh_buttons(self) -> None:
        row = self.list.currentRow()
        has = 0 <= row < len(self.entries)
        idle = not self.viewer.busy
        level = self.entries[row]["level"] if has else 1
        previous = self.entries[row - 1]["level"] if has and row > 0 else 0
        self.buttons["add"].setEnabled(idle and len(self.entries) < MAX_OUTLINE_ENTRIES)
        self.buttons["remove"].setEnabled(idle and has)
        self.buttons["up"].setEnabled(idle and has and row > 0)
        self.buttons["down"].setEnabled(idle and has and row < len(self.entries) - 1)
        self.buttons["outdent"].setEnabled(idle and has and level > 1)
        self.buttons["indent"].setEnabled(
            idle and has and row > 0 and level <= previous and level < MAX_OUTLINE_DEPTH
        )
        self.buttons["suggest"].setEnabled(idle and self.viewer.info.copy_allowed)
        self.buttons["clear"].setEnabled(idle and bool(self.entries))
        broken = sum(1 for entry in self.entries if entry["page"] < 0 and not entry["external"])
        empty = sum(1 for entry in self.entries if not entry["title"].strip())
        if self.viewer.busy:
            text = self.viewer.busy
        elif broken:
            text = f"{broken} marcador(es) sem página de destino. Escolha uma página ou exclua."
        elif empty:
            text = "Todo marcador precisa de um título."
        else:
            text = f"{len(self.entries)} marcador(es)."
        self.status.setText(text)
        self.apply.setEnabled(idle and self.modified and not broken and not empty)

    def _changed(self, row: int) -> None:
        levels = normalize_levels([entry["level"] for entry in self.entries])
        for entry, level in zip(self.entries, levels, strict=True):
            entry["level"] = level
        self.modified = True
        self._rebuild(row)

    # Ações
    def _title_edited(self, text: str) -> None:
        entry = self._current()
        if entry is not None:
            entry["title"] = text
            self.modified = True
            item = self.list.currentItem()
            item.setText(self._label(entry))
            self._refresh_buttons()

    def _page_edited(self, value: int) -> None:
        entry = self._current()
        if entry is not None and not entry["external"]:
            entry["page"] = value - 1
            self.modified = True
            self.list.currentItem().setText(self._label(entry))
            self._selected(self.list.currentRow())

    def _add(self) -> None:
        row = self.list.currentRow()
        level = self.entries[row]["level"] if 0 <= row < len(self.entries) else 1
        entry = {
            "level": level,
            "title": f"Página {self.viewer.page + 1}",
            "page": self.viewer.page,
            "source": None,
            "external": False,
        }
        self.entries.insert(row + 1, entry)
        self._changed(row + 1)
        self.title.setFocus()
        self.title.selectAll()

    def _remove(self) -> None:
        row = self.list.currentRow()
        if 0 <= row < len(self.entries):
            del self.entries[row]
            self._changed(row)

    def _move(self, delta: int) -> None:
        row = self.list.currentRow()
        target = row + delta
        if 0 <= row < len(self.entries) and 0 <= target < len(self.entries):
            self.entries[row], self.entries[target] = self.entries[target], self.entries[row]
            self._changed(target)

    def _indent(self, delta: int) -> None:
        row = self.list.currentRow()
        if 0 <= row < len(self.entries):
            self.entries[row]["level"] = max(1, self.entries[row]["level"] + delta)
            self._changed(row)

    def _clear(self) -> None:
        if self.entries:
            self.entries.clear()
            self._changed(0)

    def _go_to(self, _item) -> None:
        entry = self._current()
        if entry and entry["page"] >= 0:
            self.viewer.go_to(entry["page"])

    def _suggest(self) -> None:
        self.viewer.suggest_outline()

    def _suggested(self, entries: tuple[OutlineEntry, ...]) -> None:
        if not entries:
            self.status.setText("Nenhum título com fonte maior que o texto foi encontrado.")
            return
        choice = self.ask_merge(len(entries)) if self.entries else "replace"
        if choice is None:
            return
        replace = choice == "replace"
        fresh = [
            {
                "level": entry.level,
                "title": entry.title,
                "page": entry.page,
                "source": None,
                "external": False,
            }
            for entry in entries
        ]
        self.entries = fresh if replace else self.entries + fresh
        self.entries = self.entries[:MAX_OUTLINE_ENTRIES]
        self._changed(0)

    def ask_merge(self, count: int) -> str | None:
        """Pergunta se a sugestão substitui ou completa a lista atual."""
        box = QMessageBox(
            QMessageBox.Icon.Question,
            "Sugestão de marcadores",
            f"Foram encontrados {count} título(s). O que fazer com os marcadores atuais?",
            parent=self,
        )
        swap = box.addButton("Substituir", QMessageBox.ButtonRole.AcceptRole)
        append = box.addButton("Acrescentar ao final", QMessageBox.ButtonRole.ActionRole)
        box.addButton(QMessageBox.StandardButton.Cancel)
        box.exec()
        return {swap: "replace", append: "append"}.get(box.clickedButton())

    def _suggest_failed(self, message: str) -> None:
        self.status.setText(message)

    def _disconnect(self) -> None:
        for signal, slot in (
            (self.viewer.outline_suggested, self._suggested),
            (self.viewer.outline_suggest_failed, self._suggest_failed),
            (self.viewer.changed, self._refresh_buttons),
        ):
            with suppress(RuntimeError, TypeError):
                signal.disconnect(slot)

    def reject(self) -> None:
        if self.modified:
            choice = QMessageBox.question(
                self,
                "Descartar alterações",
                "Descartar as mudanças feitas nos marcadores?",
                QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Cancel,
            )
            if choice != QMessageBox.StandardButton.Discard:
                return
        super().reject()

    def payload(self) -> dict:
        return {
            "signature": self.signature,
            "entries": [
                {
                    "level": entry["level"],
                    "title": entry["title"].strip(),
                    "page": entry["page"],
                    "source": entry["source"],
                }
                for entry in self.entries
            ],
        }


def outline_tree_rows(entries: tuple[OutlineEntry, ...]) -> list[tuple[int, int]]:
    """Índice do pai de cada marcador (-1 na raiz), na ordem da lista."""
    parents: list[int] = []
    stack: list[int] = []
    for index, entry in enumerate(entries):
        while len(stack) >= entry.level:
            stack.pop()
        parents.append(stack[-1] if stack else -1)
        stack.append(index)
    return list(enumerate(parents))
