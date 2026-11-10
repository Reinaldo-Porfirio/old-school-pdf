"""OCR opt-in no processo PDF, usando os modelos locais do Tesseract."""

from collections.abc import Callable
from pathlib import Path

import pymupdf as pdf

from docforge.domain.errors import DocForgeError
from docforge.infrastructure.ocr_models import available_models
from docforge.infrastructure.pdf_storage import open_pdf, save_validated

MAX_MEDIA_PIXELS = 26_000_000


def raster(page: pdf.Page, dpi: int, *, annots: bool = True) -> pdf.Pixmap:
    width, height = page.rect.width * dpi / 72, page.rect.height * dpi / 72
    if not (0 < width <= 16384 and 0 < height <= 16384 and width * height <= MAX_MEDIA_PIXELS):
        raise DocForgeError("A imagem desta página é grande demais. Escolha um DPI menor.")
    return page.get_pixmap(dpi=dpi, colorspace=pdf.csRGB, alpha=False, annots=annots)


def _recognize(pixmap: pdf.Pixmap, tessdata: str, language: str) -> pdf.Document:
    try:
        content = pixmap.pdfocr_tobytes(language=language, tessdata=tessdata)
        return pdf.open(stream=content, filetype="pdf")
    except (ValueError, RuntimeError):
        raise DocForgeError(
            "O Tesseract não conseguiu usar os modelos de idioma indicados."
        ) from None


def probe_ocr(tessdata: str) -> dict:
    models = available_models(tessdata)
    if not models:
        raise DocForgeError("Escolha a pasta local que contém por.traineddata ou eng.traineddata.")
    with pdf.open() as demo:
        page = demo.new_page(width=300, height=100)
        page.insert_text((20, 56), "Teste OCR 2026", fontsize=26)
        image = raster(page, 150)
    valid = []
    for language in models:
        try:
            with _recognize(image, tessdata, language) as result:
                if "2026" in result[0].get_text():
                    valid.append(language)
        except DocForgeError:
            continue
    if not valid:
        raise DocForgeError("Nenhum modelo selecionado reconheceu o texto de teste.")
    return {"languages": valid}


def searchable_pdf(
    document: pdf.Document,
    pages: list[int],
    destination: Path,
    *,
    dpi: int,
    language: str,
    tessdata: str,
    progress: Callable[[int, int, str], None],
) -> str:
    if not set(language.split("+")).issubset(available_models(tessdata)):
        raise DocForgeError("Valide os modelos do idioma em OCR > Configurar OCR local.")
    recognized = []
    skipped = empty = 0
    for index, number in enumerate(pages):
        progress(index, len(pages), f"OCR da página {number + 1}")
        page = document[number]
        if page.get_text().strip():
            skipped += 1
            continue
        with _recognize(raster(page, dpi, annots=False), tessdata, language) as layer:
            text_page = layer[0]
            if not text_page.get_text().strip():
                empty += 1
                continue
            # Retira a imagem temporária, conservando apenas a camada invisível do OCR.
            for image in text_page.get_images():
                text_page.delete_image(image[0])
            page.show_pdf_page(
                page.rect * page.derotation_matrix,
                layer,
                rotate=page.rotation,
                keep_proportion=False,
            )
            recognized.append(number)
    if not recognized:
        raise DocForgeError(
            f"Nenhum texto novo reconhecido. {skipped} página(s) já tinham texto e "
            f"{empty} ficaram sem reconhecimento."
        )
    progress(len(pages), len(pages), "Validando a camada de texto")
    save_validated(document, destination, None)
    with open_pdf(destination) as output:
        for number in recognized:
            if not output[number].get_text().strip():
                raise DocForgeError("A camada de texto não persistiu na saída do OCR.")
    return (
        f"{len(recognized)} página(s) com OCR · {skipped} já tinham texto · "
        f"{empty} sem reconhecimento · {dpi} DPI"
    )
