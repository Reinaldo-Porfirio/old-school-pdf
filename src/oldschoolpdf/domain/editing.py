"""Dados da edição independentes da interface e do motor PDF."""

import re
from dataclasses import dataclass

from oldschoolpdf.domain.errors import OldSchoolPDFError
from oldschoolpdf.domain.viewer import PdfRect

PAGE_EDITS = {"move_page", "delete_pages", "rotate_pages"}
ANNOTATION_EDITS = {"add_annotation", "move_annotation", "remove_annotation", "change_annotation"}
ANNOTATION_LABELS = {
    "highlight": "Destaque",
    "underline": "Sublinhado",
    "comment": "Comentário",
    "text": "Caixa de texto",
    "stamp": "Carimbo",
    "rectangle": "Retângulo",
    "ellipse": "Elipse",
    "image": "Imagem",
    "visual_signature": "Assinatura visual",
}
STAMP_LABELS = ("Aprovado", "Em análise", "Revisado", "Confidencial")


def parse_intervals(text: str, count: int) -> list[tuple[int, int]]:
    """Retorna intervalos inclusivos de base zero, na ordem digitada."""
    ranges = []
    for token in text.split(","):
        match = re.fullmatch(r"\s*([1-9][0-9]{0,5})(?:\s*[-–—]\s*([1-9][0-9]{0,5}))?\s*", token)
        if not match:
            raise OldSchoolPDFError("Informe páginas ou intervalos, como 2–4 ou 1,3,6–8.")
        start = int(match[1])
        end = int(match[2] or match[1])
        if not 1 <= start <= end <= count:
            raise OldSchoolPDFError(f"Os intervalos devem estar entre as páginas 1 e {count}.")
        ranges.append((start - 1, end - 1))
    ordered = sorted(ranges)
    if any(left[1] >= right[0] for left, right in zip(ordered, ordered[1:], strict=False)):
        raise OldSchoolPDFError("Os intervalos se sobrepõem. Indique cada página uma vez.")
    return ranges


@dataclass(frozen=True, slots=True)
class AnnotationInfo:
    xref: int
    kind: str
    region: PdfRect
    text: str
    movable: bool
    editable: bool


@dataclass(frozen=True, slots=True)
class FormField:
    xref: int
    name: str
    kind: str
    value: str
    choices: tuple[str, ...]
    editable: bool
    max_length: int
    multiline: bool
    region: PdfRect
