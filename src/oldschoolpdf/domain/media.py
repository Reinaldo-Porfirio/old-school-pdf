"""Pedidos de OCR, conversão e lote, independentes de Qt e do motor PDF."""

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path

from oldschoolpdf.domain.errors import OldSchoolPDFError

OCR_LANGUAGES = {"por": "Português (Brasil)", "eng": "Inglês"}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tif", ".tiff"}
MEDIA_DPI = (96, 150, 200, 300)
MAX_BATCH_INPUTS = 100


class MediaOperation(StrEnum):
    OCR = "ocr"
    RENDER = "render"
    IMAGES_PDF = "images_pdf"
    TEXT = "text"
    EXTRACT_IMAGES = "extract_images"
    OPTIMIZE = "optimize"
    SPLIT = "split"
    MERGE = "merge"


MEDIA_LABELS = {
    MediaOperation.OCR: "Reconhecer texto",
    MediaOperation.RENDER: "Exportar páginas como imagens",
    MediaOperation.IMAGES_PDF: "Reunir imagens em um PDF",
    MediaOperation.TEXT: "Extrair texto UTF-8",
    MediaOperation.EXTRACT_IMAGES: "Extrair imagens incorporadas",
    MediaOperation.OPTIMIZE: "Otimizar PDF",
    MediaOperation.SPLIT: "Dividir por quantidade de páginas",
    MediaOperation.MERGE: "Mesclar PDFs",
}


@dataclass(frozen=True, slots=True)
class MediaOptions:
    ranges: str = ""
    dpi: int = 200
    image_format: str = "png"
    language: str = "por"
    tessdata: str = ""
    reduce_images: bool = False
    split_size: int = 1
    confirmed: bool = False

    def __post_init__(self) -> None:
        if self.dpi not in MEDIA_DPI or self.image_format not in {"png", "jpg"}:
            raise OldSchoolPDFError("Escolha uma resolução e um formato de imagem compatíveis.")
        if self.language not in {*OCR_LANGUAGES, "por+eng"}:
            raise OldSchoolPDFError("Escolha português, inglês ou os dois idiomas.")
        if not 1 <= self.split_size <= 1000 or len(self.ranges) > 1800:
            raise OldSchoolPDFError("Informe uma seleção de páginas válida.")


@dataclass(frozen=True, slots=True)
class MediaRequest:
    operation: MediaOperation
    inputs: tuple[Path, ...]
    destination: Path
    options: MediaOptions = field(default_factory=MediaOptions)

    def __post_init__(self) -> None:
        minimum = 2 if self.operation == MediaOperation.MERGE else 1
        if not minimum <= len(self.inputs) <= MAX_BATCH_INPUTS:
            raise OldSchoolPDFError(
                f"Escolha de {minimum} a {MAX_BATCH_INPUTS} arquivos de entrada."
            )

    def groups(self) -> tuple[tuple[Path, ...], ...]:
        if self.operation in {MediaOperation.IMAGES_PDF, MediaOperation.MERGE}:
            return (self.inputs,)
        return tuple((path,) for path in self.inputs)
