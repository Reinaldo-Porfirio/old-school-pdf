"""Regras de cabeçalho, rodapé, numeração e marca d'água, sem Qt e sem motor PDF."""

import re
import unicodedata

from oldschoolpdf.domain.errors import OldSchoolPDFError

STAMP_EDITS = {"header_footer", "watermark", "remove_stamps"}
STAMP_KINDS = ("header", "watermark")

# Fonte normal e negrito embutidas no motor, sem depender das fontes do Windows.
STAMP_FONTS = {
    "sans": ("Sem serifa (Helvetica)", "helv", "hebo"),
    "serif": ("Com serifa (Times)", "tiro", "tibo"),
    "mono": ("Máquina de escrever (Courier)", "cour", "cobo"),
}
STAMP_COLORS = {
    "black": ("Preto", (0.0, 0.0, 0.0)),
    "gray": ("Cinza", (0.45, 0.45, 0.45)),
    "navy": ("Azul-marinho", (0.08, 0.17, 0.42)),
    "red": ("Vermelho", (0.78, 0.08, 0.1)),
    "green": ("Verde", (0.05, 0.45, 0.2)),
}
SLOTS = (
    "header_left",
    "header_center",
    "header_right",
    "footer_left",
    "footer_center",
    "footer_right",
)
SLOT_LABELS = {
    "header_left": "Cabeçalho à esquerda",
    "header_center": "Cabeçalho no centro",
    "header_right": "Cabeçalho à direita",
    "footer_left": "Rodapé à esquerda",
    "footer_center": "Rodapé no centro",
    "footer_right": "Rodapé à direita",
}
NUMBER_FORMATS = {
    "page_of": ("Página 1 de 10", "Página [página] de [total]"),
    "page": ("Página 1", "Página [página]"),
    "plain": ("1", "[página]"),
    "slash": ("1/10", "[página]/[total]"),
    "dash": ("- 1 -", "- [página] -"),
}
TOKENS = {
    "página": "Número da página",
    "total": "Total de páginas",
    "data": "Data de hoje",
    "arquivo": "Nome do arquivo",
}
WATERMARK_PRESETS = (
    "CONFIDENCIAL",
    "CÓPIA",
    "RASCUNHO",
    "USO INTERNO",
    "CÓPIA NÃO CONTROLADA",
    "AMOSTRA",
    "PAGO",
    "CANCELADO",
)
WATERMARK_ANGLES = {
    "diagonal": "Diagonal (de baixo para cima)",
    "horizontal": "Horizontal",
    "vertical": "Vertical",
}
WATERMARK_LAYERS = {
    "behind": "Atrás do conteúdo (o texto continua legível)",
    "front": "Na frente do conteúdo (aparece também sobre imagens)",
}
MAX_STAMP_TEXT = 200
MAX_TOKEN_VALUE = 120
MIN_STAMP_SIZE = 6
MAX_STAMP_SIZE = 36
MIN_MARGIN_MM = 3
MAX_MARGIN_MM = 60
MAX_START = 99_999
MIN_WATERMARK_SIZE = 8
MAX_WATERMARK_SIZE = 250
MIN_OPACITY = 5
MIN_IMAGE_SCALE = 5
_TOKEN = re.compile(r"\[(página|pagina|total|data|arquivo)\]", re.IGNORECASE)


def one_line(value: object, limit: int, what: str) -> str:
    """Texto de uma linha, sem caracteres de controle."""
    if not isinstance(value, str):
        raise OldSchoolPDFError(f"O texto {what} é inválido.")
    text = unicodedata.normalize("NFC", value)
    if any(
        not char.isspace() and unicodedata.category(char) in {"Cc", "Cf", "Cs", "Co", "Cn"}
        for char in text
    ):
        raise OldSchoolPDFError(f"O texto {what} tem caracteres de controle ou inválidos.")
    text = " ".join(text.split())
    if len(text) > limit:
        raise OldSchoolPDFError(f"O texto {what} aceita até {limit} caracteres.")
    return text


def expand_tokens(template: str, number: int, total: int, date: str, filename: str) -> str:
    """Troca [página], [total], [data] e [arquivo] pelos valores desta página."""
    values = {
        "página": str(number),
        "pagina": str(number),
        "total": str(total),
        "data": date,
        "arquivo": filename,
    }
    return _TOKEN.sub(lambda match: values[match[1].lower()], template)


def check_choice(value: object, options, what: str) -> str:
    if value not in options:
        raise OldSchoolPDFError(f"Escolha {what} válido(a).")
    return value


def check_number(value: object, low: float, high: float, what: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float) or not low <= value <= high:
        raise OldSchoolPDFError(f"Informe {what} entre {low:g} e {high:g}.")
    return float(value)
