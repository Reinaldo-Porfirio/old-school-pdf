"""Preferências e layout locais, em INI; leitura defensiva e sync atômico."""

import json
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QByteArray, QSettings, QStandardPaths
from PySide6.QtGui import QKeySequence

from oldschoolpdf.application.preferences import (
    DEFAULT_SHORTCUTS,
    DEFAULT_THEME,
    EDITOR_SHORTCUTS,
    THEME_NAMES,
    VIEWER_SHORTCUTS,
    Preferences,
)
from oldschoolpdf.domain.errors import SettingsError
from oldschoolpdf.domain.media import OCR_LANGUAGES

LAYOUT_VERSION = 1
SETTINGS_ID = "old-school-pdf"


@dataclass(frozen=True, slots=True)
class WindowLayout:
    geometry: QByteArray
    state: QByteArray


class SettingsRepository:
    def __init__(self, path: Path | None = None) -> None:
        if path is None:
            path = Path(QStandardPaths.writableLocation(QStandardPaths.AppConfigLocation))
            path /= "settings.ini"
        self.path = path.resolve()
        self.warnings: list[str] = []

    def _open(self) -> QSettings:
        settings = QSettings(str(self.path), QSettings.Format.IniFormat)
        settings.setFallbacksEnabled(False)
        settings.setAtomicSyncRequired(True)
        return settings

    def load_preferences(self) -> Preferences:
        self.warnings.clear()
        settings = self._open()
        if self.path.exists() and settings.value("application/id", "") != SETTINGS_ID:
            self.warnings.append(
                "O arquivo de configurações não pertence ao Old School PDF; "
                "ele será preservado. Escolha outro caminho com --settings-file."
            )
            return Preferences()
        try:
            theme = settings.value("preferences/theme", DEFAULT_THEME, type=str)
            size = settings.value("preferences/icon_size", 24, type=int)
            under = settings.value("preferences/text_under_icons", False, type=bool)
            restore = settings.value("preferences/restore_layout", True, type=bool)
            cache_mib = settings.value("viewer/cache_mib", 64, type=int)
            parallelism = settings.value("viewer/parallelism", 2, type=int)
            tessdata = settings.value("ocr/tessdata", "", type=str)
            validated = settings.value("ocr/languages", "", type=str).split("+")
            shortcuts = json.loads(settings.value("preferences/shortcuts", "{}", type=str))
            if not isinstance(shortcuts, dict) or any(
                not isinstance(k, str) or not isinstance(v, str) for k, v in shortcuts.items()
            ):
                raise ValueError("Atalhos inválidos")
            if settings.status() != QSettings.Status.NoError:
                raise ValueError("Formato INI inválido")
            if theme not in THEME_NAMES:
                # Temas antigos ou removidos voltam ao padrão sem descartar o resto.
                theme = DEFAULT_THEME
            if size not in (20, 24, 32):
                raise ValueError("Preferências desconhecidas")
            if not 16 <= cache_mib <= 256 or not 1 <= parallelism <= 4:
                raise ValueError("Limites do visualizador inválidos")
            resolved = {key: shortcuts.get(key, value) for key, value in DEFAULT_SHORTCUTS.items()}
            # Atalhos definidos pelo usuário têm prioridade sobre novos padrões.
            order = sorted(resolved, key=lambda key: key not in shortcuts)
            seen: set[str] = set()
            for key in order:
                value = resolved[key]
                sequence = QKeySequence.fromString(value, QKeySequence.SequenceFormat.PortableText)
                normalized = sequence.toString(QKeySequence.SequenceFormat.PortableText)
                if (
                    normalized in seen
                    and key in (VIEWER_SHORTCUTS | EDITOR_SHORTCUTS)
                    and key not in shortcuts
                ):
                    resolved[key] = ""
                    continue
                if value and (not normalized or sequence.count() != 1 or normalized in seen):
                    raise ValueError("Atalhos inválidos ou duplicados")
                if normalized:
                    seen.add(normalized)
                resolved[key] = normalized
            return Preferences(
                theme,
                size,
                under,
                restore,
                resolved,
                cache_mib,
                parallelism,
                tessdata,
                tuple(language for language in OCR_LANGUAGES if language in validated),
            )
        except (ValueError, TypeError, OverflowError):
            self.warnings.append("Preferências inválidas; os valores padrão foram carregados.")
            return Preferences()

    def load_layout(self) -> WindowLayout | None:
        settings = self._open()
        if settings.value("application/id", "") != SETTINGS_ID:
            return None
        try:
            version = settings.value("layout/version", 0, type=int)
        except (ValueError, TypeError, OverflowError):
            return None
        if version != LAYOUT_VERSION:
            return None
        geometry = settings.value("layout/geometry")
        state = settings.value("layout/state")
        if not isinstance(geometry, QByteArray) or not isinstance(state, QByteArray):
            return None
        return WindowLayout(geometry, state)

    def save(self, preferences: Preferences, layout: WindowLayout) -> None:
        settings = self._open()
        # Nunca transformar um PDF ou um INI de outro programa em preferências.
        if self.path.exists() and settings.value("application/id", "") != SETTINGS_ID:
            raise SettingsError(
                "O arquivo escolhido não pertence ao Old School PDF e foi preservado. "
                "Inicie com --settings-file apontando para um novo arquivo INI."
            )
        settings.setValue("application/id", SETTINGS_ID)
        settings.setValue("preferences/theme", preferences.theme)
        settings.setValue("preferences/icon_size", preferences.icon_size)
        settings.setValue("preferences/text_under_icons", preferences.text_under_icons)
        settings.setValue("preferences/restore_layout", preferences.restore_layout)
        settings.setValue("preferences/shortcuts", json.dumps(preferences.shortcuts))
        settings.setValue("viewer/cache_mib", preferences.pdf_cache_mib)
        settings.setValue("viewer/parallelism", preferences.pdf_parallelism)
        settings.setValue("ocr/tessdata", preferences.ocr_tessdata)
        settings.setValue("ocr/languages", "+".join(preferences.ocr_languages))
        settings.setValue("layout/version", LAYOUT_VERSION)
        settings.setValue("layout/geometry", layout.geometry)
        settings.setValue("layout/state", layout.state)
        settings.sync()
        if settings.status() != QSettings.Status.NoError:
            raise SettingsError(
                "Não foi possível gravar as preferências locais. "
                "Verifique a permissão e o espaço na pasta de configurações."
            )
