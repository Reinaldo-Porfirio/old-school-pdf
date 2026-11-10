"""Descoberta passiva de modelos Tesseract escolhidos pelo usuário."""

from pathlib import Path

from oldschoolpdf.domain.errors import OldSchoolPDFError
from oldschoolpdf.domain.media import OCR_LANGUAGES
from oldschoolpdf.infrastructure.local_files import check_local


def available_models(directory: str) -> tuple[str, ...]:
    if not directory:
        return ()
    folder = Path(directory)
    try:
        check_local(folder)
    except (OSError, OldSchoolPDFError):
        return ()
    languages = []
    for language in OCR_LANGUAGES:
        model = folder / (language + ".traineddata")
        try:
            check_local(model)
            if model.is_file() and 1024 < model.stat().st_size <= 64 * 1024**2:
                languages.append(language)
        except (OSError, OldSchoolPDFError):
            continue
    return tuple(languages)
