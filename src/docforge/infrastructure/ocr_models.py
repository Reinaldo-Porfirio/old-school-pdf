"""Descoberta passiva de modelos Tesseract escolhidos pelo usuário."""

from pathlib import Path

from docforge.domain.errors import DocForgeError
from docforge.domain.media import OCR_LANGUAGES
from docforge.infrastructure.local_files import check_local


def available_models(directory: str) -> tuple[str, ...]:
    if not directory:
        return ()
    folder = Path(directory)
    try:
        check_local(folder)
    except (OSError, DocForgeError):
        return ()
    languages = []
    for language in OCR_LANGUAGES:
        model = folder / (language + ".traineddata")
        try:
            check_local(model)
            if model.is_file() and 1024 < model.stat().st_size <= 64 * 1024**2:
                languages.append(language)
        except (OSError, DocForgeError):
            continue
    return tuple(languages)
