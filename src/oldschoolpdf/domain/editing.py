"""Dados da edição independentes da interface e do motor PDF."""

import re
from dataclasses import dataclass

from oldschoolpdf.domain.errors import OldSchoolPDFError
from oldschoolpdf.domain.viewer import PdfRect

PAGE_EDITS = {"move_page", "delete_pages", "rotate_pages", "insert_blank"}
# Corte e redimensionamento mudam a geometria do conteúdo, não só a montagem.
BOX_EDITS = {"crop_pages", "resize_pages"}
OUTLINE_EDITS = {"set_outline"}
FIELD_EDITS = {"add_field", "remove_field"}
ANNOTATION_EDITS = {"add_annotation", "move_annotation", "remove_annotation", "change_annotation"}
TEXT_EDITS = {"replace_text"}

MM = 72 / 25.4
# Largura e altura em pontos, na orientação retrato.
PAPER_SIZES = {
    "a4": ("A4 (21 × 29,7 cm)", 210 * MM, 297 * MM),
    "a5": ("A5 (14,8 × 21 cm)", 148 * MM, 210 * MM),
    "letter": ("Carta (21,6 × 27,9 cm)", 612.0, 792.0),
    "legal": ("Ofício (21,6 × 35,6 cm)", 612.0, 1008.0),
}
MAX_BLANK_PAGES = 50
MAX_CROP_MM = 500
MIN_PAGE_POINTS = 36.0
MAX_OUTLINE_ENTRIES = 5000
MAX_OUTLINE_DEPTH = 12
MAX_TITLE_LENGTH = 512
FIELD_KINDS = {
    "text": "Texto de uma linha",
    "multiline": "Texto de várias linhas",
    "checkbox": "Caixa de marcar",
    "choice": "Lista suspensa",
}
MAX_FIELD_NAME = 120
MAX_FIELD_CHOICES = 200


def paper_size(key: str, orientation: str) -> tuple[float, float]:
    """Largura e altura do papel em pontos na orientação pedida."""
    if key not in PAPER_SIZES or orientation not in {"portrait", "landscape"}:
        raise OldSchoolPDFError("Escolha um tamanho de papel e uma orientação válidos.")
    _, width, height = PAPER_SIZES[key]
    return (height, width) if orientation == "landscape" else (width, height)


def clean_title(value: object) -> str:
    """Título de marcador numa linha, sem caracteres de controle."""
    if not isinstance(value, str):
        raise OldSchoolPDFError("O título do marcador é inválido.")
    text = " ".join("".join(" " if ord(ch) < 32 or ch == "\x7f" else ch for ch in value).split())
    if not text or len(text) > MAX_TITLE_LENGTH:
        raise OldSchoolPDFError(
            f"Cada marcador precisa de um título com 1 a {MAX_TITLE_LENGTH} caracteres."
        )
    return text


def check_levels(levels: list[int]) -> None:
    """O primeiro marcador fica no nível 1 e cada um desce no máximo um nível."""
    previous = 0
    for number, level in enumerate(levels, 1):
        if not isinstance(level, int) or not 1 <= level <= MAX_OUTLINE_DEPTH:
            raise OldSchoolPDFError(f"O marcador {number} tem um nível inválido.")
        if level > previous + 1:
            raise OldSchoolPDFError(
                f"O marcador {number} está recuado demais em relação ao anterior."
            )
        previous = level


def field_name(value: object) -> str:
    if not isinstance(value, str):
        raise OldSchoolPDFError("O nome do campo é inválido.")
    name = value.strip()
    if not re.fullmatch(rf"[\w\- ]{{1,{MAX_FIELD_NAME}}}", name):
        raise OldSchoolPDFError(
            "Dê ao campo um nome de até 120 letras, números, espaços, hífens ou sublinhados."
        )
    return name


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
class OutlineEntry:
    """Marcador lido do PDF. `page` é de base zero ou -1 quando não aponta para uma página."""

    level: int
    title: str
    page: int
    external: bool = False


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


def normalize_levels(levels: list[int]) -> list[int]:
    """Ajusta os níveis para uma árvore válida depois de mover ou excluir marcadores."""
    result = []
    previous = 0
    for level in levels:
        fixed = max(1, min(level, previous + 1, MAX_OUTLINE_DEPTH))
        result.append(fixed)
        previous = fixed
    return result
