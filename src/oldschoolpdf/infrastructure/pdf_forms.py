"""Criação e remoção de campos de formulário (AcroForm)."""

import pymupdf as pdf

from oldschoolpdf.domain.editing import FIELD_KINDS, MAX_FIELD_CHOICES, field_name
from oldschoolpdf.domain.errors import OldSchoolPDFError
from oldschoolpdf.infrastructure.pdf_editing import TEXT_LIMIT, page_rect

MIN_FIELD_POINTS = 8.0
FONT_SIZES = (0, 8, 9, 10, 11, 12, 14, 16, 18, 24)
REMOVABLE = {
    pdf.PDF_WIDGET_TYPE_TEXT,
    pdf.PDF_WIDGET_TYPE_CHECKBOX,
    pdf.PDF_WIDGET_TYPE_COMBOBOX,
    pdf.PDF_WIDGET_TYPE_LISTBOX,
    pdf.PDF_WIDGET_TYPE_RADIOBUTTON,
}


def field_names(doc: pdf.Document) -> set[str]:
    if not doc.is_form_pdf:
        return set()
    return {(widget.field_name or "").casefold() for page in doc for widget in page.widgets() or ()}


def _choices(raw) -> list[str]:
    if not isinstance(raw, list) or not 1 <= len(raw) <= MAX_FIELD_CHOICES:
        raise OldSchoolPDFError(
            f"Informe de 1 a {MAX_FIELD_CHOICES} opções para a lista, uma por linha."
        )
    choices = []
    for item in raw:
        if not isinstance(item, str) or not item.strip() or len(item) > 200:
            raise OldSchoolPDFError("Cada opção da lista precisa de 1 a 200 caracteres.")
        if any(ord(ch) < 32 for ch in item):
            raise OldSchoolPDFError("As opções da lista não podem ter quebras de linha.")
        choices.append(item.strip())
    if len({item.casefold() for item in choices}) != len(choices):
        raise OldSchoolPDFError("A lista tem opções repetidas.")
    return choices


def add_field(page: pdf.Page, values: dict) -> int:
    """Cria um campo na área escolhida e devolve o xref do widget novo."""
    kind = values.get("kind")
    if kind not in FIELD_KINDS:
        raise OldSchoolPDFError("Escolha um tipo de campo disponível.")
    name = field_name(values.get("name"))
    doc = page.parent
    if name.casefold() in field_names(doc):
        raise OldSchoolPDFError(f"Já existe um campo chamado {name}. Escolha outro nome.")
    rect = page_rect(page, values["region"])
    if rect.width < MIN_FIELD_POINTS or rect.height < MIN_FIELD_POINTS:
        raise OldSchoolPDFError("Desenhe um retângulo maior para o campo.")
    label = values.get("label", "")
    if not isinstance(label, str) or len(label) > 200:
        raise OldSchoolPDFError("A dica do campo pode ter até 200 caracteres.")
    size = values.get("font_size", 0)
    if size not in FONT_SIZES:
        raise OldSchoolPDFError("Escolha um tamanho de fonte da lista.")
    value = values.get("value", "")
    widget = pdf.Widget()
    widget.field_name = name
    widget.field_label = label.strip() or None
    widget.rect = rect
    widget.text_font = "Helv"
    widget.text_fontsize = size
    widget.text_color = (0, 0, 0)
    widget.border_color = (0.45, 0.45, 0.45)
    widget.border_width = 1
    widget.fill_color = (1, 1, 1)
    flags = pdf.PDF_FIELD_IS_REQUIRED if values.get("required") else 0
    if kind in {"text", "multiline"}:
        limit = values.get("max_length", 0)
        if not isinstance(limit, int) or not 0 <= limit <= TEXT_LIMIT:
            raise OldSchoolPDFError(f"O limite de caracteres vai de 0 (sem limite) a {TEXT_LIMIT}.")
        if not isinstance(value, str) or len(value) > (limit or TEXT_LIMIT):
            raise OldSchoolPDFError("O valor inicial ultrapassa o limite do campo.")
        if kind == "text" and "\n" in value:
            raise OldSchoolPDFError("Um campo de uma linha não aceita quebras de linha.")
        widget.field_type = pdf.PDF_WIDGET_TYPE_TEXT
        widget.text_maxlen = limit
        widget.field_value = value
        if kind == "multiline":
            flags |= pdf.PDF_TX_FIELD_IS_MULTILINE
    elif kind == "checkbox":
        widget.field_type = pdf.PDF_WIDGET_TYPE_CHECKBOX
        widget.field_value = bool(value)
    else:
        choices = _choices(values.get("choices"))
        if value and value not in choices:
            raise OldSchoolPDFError("O valor inicial precisa ser uma das opções.")
        widget.field_type = pdf.PDF_WIDGET_TYPE_COMBOBOX
        widget.choice_values = choices
        widget.field_value = value or choices[0]
    widget.field_flags = flags
    created = page.add_widget(widget)
    xref = created.xref
    if page.rotation:
        # Sem /MK /R, o texto do campo sairia de lado numa página girada.
        doc.xref_set_key(xref, "MK/R", str(page.rotation))
        page.load_widget(xref).update()
    check = page.load_widget(xref)
    if check is None or (check.field_name or "") != name:
        raise OldSchoolPDFError("O campo criado não pôde ser conferido. Nada foi alterado.")
    return xref


def remove_field(page: pdf.Page, values: dict) -> None:
    xref = values.get("xref")
    present = {item.xref for item in page.widgets() or ()}
    widget = page.load_widget(xref) if isinstance(xref, int) and xref in present else None
    if widget is None:
        raise OldSchoolPDFError("O campo não está mais nesta página.")
    if widget.field_type not in REMOVABLE:
        raise OldSchoolPDFError("Este tipo de campo não pode ser excluído pelo programa.")
    page.delete_widget(widget)
    if any(item.xref == xref for item in page.widgets() or ()):
        raise OldSchoolPDFError("O campo não pôde ser excluído. Nada foi alterado.")
