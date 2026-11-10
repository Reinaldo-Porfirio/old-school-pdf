"""Valores compartilhados pelo leitor, pelo renderizador e pela interface."""

from dataclasses import dataclass
from typing import Literal

from oldschoolpdf.domain.models import DocumentMetadata

PdfRect = tuple[float, float, float, float]
FitMode = Literal["page", "width", "thumbnail", "continuous"]
MAX_QUERY_LENGTH = 160
MAX_SEARCH_HITS = 1000
MAX_RASTER_BYTES = 24_500_000
MAX_REPLY_HEADER = 4 * 1024 * 1024


def rotate_rect(rect: PdfRect, rotation: int) -> PdfRect:
    """Gira um retângulo normalizado no sentido horário."""
    x0, y0, x1, y1 = rect
    match rotation % 360:
        case 90:
            return (1 - y1, x0, 1 - y0, x1)
        case 180:
            return (1 - x1, 1 - y1, 1 - x0, 1 - y0)
        case 270:
            return (y0, 1 - x1, y1, 1 - x0)
        case _:
            return rect


@dataclass(frozen=True, slots=True)
class PdfInfo(DocumentMetadata):
    format: str = "PDF"
    protected: bool = False
    owner_authenticated: bool = False
    copy_allowed: bool = True
    repaired: bool = False
    signed: bool = False
    can_organize: bool = False
    can_annotate: bool = False
    can_fill: bool = False


@dataclass(frozen=True, slots=True)
class RasterRequest:
    page: int
    rotation: int
    zoom: float | FitMode
    width: int = 0
    height: int = 0
    dpr: float = 1.0


@dataclass(frozen=True, slots=True)
class SearchHit:
    page: int
    regions: tuple[PdfRect, ...]
