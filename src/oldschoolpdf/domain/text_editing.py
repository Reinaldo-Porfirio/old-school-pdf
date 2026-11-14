"""Regras da edição do texto original do PDF, sem Qt e sem motor PDF."""

import re
import unicodedata
from dataclasses import dataclass

from oldschoolpdf.domain.errors import OldSchoolPDFError
from oldschoolpdf.domain.viewer import PdfRect

MAX_BLOCK_CHARS = 4000
MAX_EDIT_BLOCKS = 30
MAX_PAGE_BLOCKS = 400
# Quanto o texto pode encolher para caber no espaço original.
SHRINK_LIMITS = {"none": 1.0, "light": 0.85, "strong": 0.7}
ALIGNMENTS = ("left", "center", "right", "justify")
_SUBSET = re.compile(r"^[A-Z]{6}\+")
_STYLE_WORDS = re.compile(
    r"(bold|italic|oblique|regular|book|normal|medium|semibold|demibold|light|mt|ps)$"
)


@dataclass(frozen=True, slots=True)
class TextStyle:
    """Estilo encontrado no PDF para um trecho de texto."""

    font: str
    size: float
    color: int
    bold: bool
    italic: bool
    serif: bool
    mono: bool


@dataclass(frozen=True, slots=True)
class TextRun:
    """Trecho editável: texto, estilo de origem e ênfase escolhida pelo usuário."""

    text: str
    style: int
    bold: bool
    italic: bool


@dataclass(frozen=True, slots=True)
class TextBlock:
    key: str
    bbox: PdfRect
    region: PdfRect
    text: str
    runs: tuple[TextRun, ...]
    styles: tuple[TextStyle, ...]
    align: str
    line_height: float
    editable: bool
    reason: str = ""


def clean_font_name(name: str) -> str:
    """Remove o prefixo de subconjunto (ABCDEF+) do nome da fonte."""
    return _SUBSET.sub("", name or "").strip() or "Desconhecida"


def font_family_key(name: str) -> str:
    """Chave da família para comparar nomes do PDF e do sistema: "Arial-BoldMT" vira "arial"."""
    base = clean_font_name(name).lower()
    base = re.split(r"[-,]", base, maxsplit=1)[0]
    base = re.sub(r"[^a-z0-9]", "", base)
    previous = None
    while previous != base:
        previous = base
        base = _STYLE_WORDS.sub("", base)
    return base


def is_bold_name(name: str) -> bool:
    return bool(re.search(r"bold|black|heavy|semibold|demibold", name, re.IGNORECASE))


def is_italic_name(name: str) -> bool:
    return bool(re.search(r"italic|oblique|kursiv", name, re.IGNORECASE))


def _is_rtl(char: str) -> bool:
    return unicodedata.bidirectional(char) in {"R", "AL", "RLE", "RLO", "RLI"}


def validate_text(text: str) -> str:
    """Normaliza quebras e recusa o que o motor não escreve com segurança."""
    text = unicodedata.normalize("NFC", text.replace("\r\n", "\n").replace("\r", "\n"))
    text = text.replace(" ", "\n").replace(" ", "\n")
    if len(text) > MAX_BLOCK_CHARS:
        raise OldSchoolPDFError(f"Cada bloco aceita até {MAX_BLOCK_CHARS} caracteres.")
    for char in text:
        if char in "\n\t":
            continue
        category = unicodedata.category(char)
        if category in {"Cc", "Cs", "Co", "Cn"}:
            raise OldSchoolPDFError("O texto contém caracteres de controle ou inválidos.")
        if _is_rtl(char):
            raise OldSchoolPDFError(
                "Texto da direita para a esquerda (árabe, hebraico) ainda não é suportado."
            )
    return text.replace("\t", "    ")


def compare_form(text: str) -> str:
    """Forma usada para conferir o texto gravado: ignora espaços e variações invisíveis."""
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("­", "").replace(" ", " ")
    return " ".join(text.split())


def line_joints(lines: list[str], fill: list[float]) -> list[str]:
    """Como cada linha visual se liga à anterior: "-" (hifenização), "\\n" ou " ".

    `fill` diz quanto cada linha ocupa da largura do bloco (0 a 1). Uma linha curta
    que termina com pontuação encerra o parágrafo; hífen no fim de linha seguido de
    minúscula é tratado como hifenização e removido.
    """
    joints = []
    for index in range(1, len(lines)):
        previous = lines[index - 1].rstrip()
        current = lines[index].lstrip()
        if (
            previous.endswith("-")
            and len(previous) > 1
            and previous[-2].isalpha()
            and current[:1].islower()
        ):
            joints.append("-")
        elif fill[index - 1] < 0.75 and previous[-1:] in '.:;!?)"»”':
            joints.append("\n")
        else:
            joints.append(" ")
    return joints


def join_lines(lines: list[str], fill: list[float]) -> str:
    """Reconstrói os parágrafos a partir das linhas visuais do bloco."""
    if not lines:
        return ""
    result = lines[0].rstrip()
    for joint, line in zip(line_joints(lines, fill), lines[1:], strict=True):
        stripped = line.strip()
        result = result[:-1] + stripped if joint == "-" else result + joint + stripped
    return result


def detect_alignment(lines: list[tuple[float, float]], left: float, right: float) -> str:
    """Alinhamento provável a partir das bordas das linhas e do bloco."""
    if len(lines) < 2:
        return "left"
    width = max(right - left, 1.0)
    tolerance = max(1.5, width * 0.01)
    left_edges = all(abs(x0 - left) <= tolerance for x0, _ in lines)
    right_edges = all(abs(x1 - right) <= tolerance for _, x1 in lines[:-1])
    centered = all(abs((x0 + x1) / 2 - (left + right) / 2) <= tolerance for x0, x1 in lines)
    if left_edges and right_edges and len(lines) > 2:
        return "justify"
    if left_edges:
        return "left"
    if centered:
        return "center"
    if all(abs(x1 - right) <= tolerance for _, x1 in lines):
        return "right"
    return "left"


def css_color(value: int) -> str:
    return f"#{max(0, min(int(value), 0xFFFFFF)):06x}"


def block_from_dict(data: dict) -> TextBlock:
    """Reconstrói um bloco recebido pelo pipe, conferindo os tipos."""
    return TextBlock(
        key=str(data["key"]),
        bbox=tuple(float(value) for value in data["bbox"]),
        region=tuple(float(value) for value in data["region"]),
        text=str(data["text"]),
        runs=tuple(
            TextRun(str(run["text"]), int(run["style"]), bool(run["bold"]), bool(run["italic"]))
            for run in data["runs"]
        ),
        styles=tuple(
            TextStyle(
                str(style["font"]),
                float(style["size"]),
                int(style["color"]),
                bool(style["bold"]),
                bool(style["italic"]),
                bool(style["serif"]),
                bool(style["mono"]),
            )
            for style in data["styles"]
        ),
        align=str(data["align"]),
        line_height=float(data["line_height"]),
        editable=bool(data["editable"]),
        reason=str(data.get("reason", "")),
    )
