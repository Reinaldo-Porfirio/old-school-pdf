"""Edições aplicadas a uma revisão descartável do documento."""

import math
from base64 import b64decode
from collections.abc import Iterable
from dataclasses import asdict
from pathlib import Path
from struct import unpack

import pymupdf as pdf

from oldschoolpdf.domain.editing import AnnotationInfo, FormField
from oldschoolpdf.domain.errors import OldSchoolPDFError
from oldschoolpdf.domain.security import SIGNATURE_PAD_SIZE
from oldschoolpdf.domain.viewer import PdfRect
from oldschoolpdf.infrastructure.local_files import check_local

TEXT_LIMIT = 4096
IMAGE_LIMIT = 12 * 1024 * 1024
VISUAL_SIGNATURE_SUBJECT = "Old School PDF: assinatura visual"
ANNOTATION_TYPES = {
    pdf.PDF_ANNOT_HIGHLIGHT: "highlight",
    pdf.PDF_ANNOT_UNDERLINE: "underline",
    pdf.PDF_ANNOT_TEXT: "comment",
    pdf.PDF_ANNOT_FREE_TEXT: "text",
    pdf.PDF_ANNOT_STAMP: "stamp",
    pdf.PDF_ANNOT_SQUARE: "rectangle",
    pdf.PDF_ANNOT_CIRCLE: "ellipse",
}
FIELD_TYPES = {
    pdf.PDF_WIDGET_TYPE_TEXT: "text",
    pdf.PDF_WIDGET_TYPE_CHECKBOX: "checkbox",
    pdf.PDF_WIDGET_TYPE_COMBOBOX: "choice",
    pdf.PDF_WIDGET_TYPE_LISTBOX: "choice",
    pdf.PDF_WIDGET_TYPE_RADIOBUTTON: "radio",
}
STAMPS = (pdf.STAMP_Approved, pdf.STAMP_ForComment, pdf.STAMP_Final, pdf.STAMP_Confidential)
LOCKED = pdf.PDF_ANNOT_IS_READ_ONLY | pdf.PDF_ANNOT_IS_LOCKED | pdf.PDF_ANNOT_IS_LOCKED_CONTENTS


def normalized_rect(page: pdf.Page, bounds) -> PdfRect:
    rect = pdf.Rect(bounds) * page.rotation_matrix
    width, height = page.rect.width, page.rect.height
    return tuple(
        round(max(0.0, min(1.0, value / size)), 6)
        for value, size in zip(rect, (width, height, width, height), strict=True)
    )


def page_rect(page: pdf.Page, region: PdfRect) -> pdf.Rect:
    x0, y0, x1, y1 = region
    if not (0 <= x0 < x1 <= 1 and 0 <= y0 < y1 <= 1):
        raise OldSchoolPDFError("Indique uma área dentro da página.")
    width, height = page.rect.width, page.rect.height
    rect = pdf.Rect(x0 * width, y0 * height, x1 * width, y1 * height) * page.derotation_matrix
    if rect.width < 1 or rect.height < 1:
        raise OldSchoolPDFError("Selecione uma área maior na página.")
    return rect


def indices(ranges: list, count: int) -> list[int]:
    selected = []
    for start, end in ranges:
        if not 0 <= start <= end < count:
            raise OldSchoolPDFError("Há páginas fora do intervalo do documento.")
        selected.extend(range(start, end + 1))
        if len(selected) > count:
            raise OldSchoolPDFError("Indique cada página uma vez.")
    if not selected or len(set(selected)) != len(selected):
        raise OldSchoolPDFError("Indique páginas distintas para a operação.")
    return selected


def _detach_widgets(doc: pdf.Document, discarded: Iterable[int]) -> None:
    if not doc.is_form_pdf:
        return
    removed = False
    for number in discarded:
        page = doc[number]
        widget = page.first_widget
        while widget is not None:
            widget = page.delete_widget(widget)
            removed = True
    if removed:
        # A ordem de cálculo pode referenciar campos que acabaram de sair do PDF.
        doc.xref_set_key(doc.pdf_catalog(), "AcroForm/CO", "null")


def select_pages(doc: pdf.Document, selected: list[int]) -> None:
    if selected == list(range(doc.page_count)):
        return
    included = set(selected)
    _detach_widgets(doc, (page for page in range(doc.page_count) if page not in included))
    catalog = doc.pdf_catalog()
    form = None
    if doc.is_form_pdf:
        doc.xref_set_key(catalog, "AcroForm/XFA", "null")
        _, form = doc.xref_get_key(catalog, "AcroForm")
    doc.select(selected)
    if form is not None:
        # O motor preserva os widgets das páginas selecionadas e recria o catálogo.
        doc.xref_set_key(doc.pdf_catalog(), "AcroForm", form)


def edit_pages(doc: pdf.Document, action: str, page: int, values: dict) -> int:
    count = doc.page_count
    if action == "move_page":
        target = values["target"]
        if not 0 <= page < count or not 0 <= target < count or page == target:
            raise OldSchoolPDFError("Escolha uma posição diferente e válida para a página.")
        before = target if target < page else target + 1
        doc.move_page(page, to=-1 if before == count else before)
        return target
    selected = indices(values["ranges"], count)
    if action == "delete_pages":
        if len(selected) == count:
            raise OldSchoolPDFError("O PDF precisa manter ao menos uma página.")
        _detach_widgets(doc, selected)
        doc.delete_pages(selected)
        return min(min(selected), doc.page_count - 1)
    angle = values["angle"]
    if angle not in (90, 180, 270):
        raise OldSchoolPDFError("Escolha uma rotação de 90°, 180° ou 270°.")
    for number in selected:
        target_page = doc[number]
        target_page.set_rotation((target_page.rotation + angle) % 360)
    return selected[0]


def _text(value: str) -> str:
    if not value.strip() or len(value) > TEXT_LIMIT:
        raise OldSchoolPDFError(f"Informe um texto de até {TEXT_LIMIT} caracteres.")
    return value


def _image(path: Path) -> bytes:
    check_local(path)
    if not path.is_file() or path.suffix.casefold() not in {".png", ".jpg", ".jpeg"}:
        raise OldSchoolPDFError("Escolha um arquivo de imagem PNG ou JPEG.")
    with path.open("rb") as stream:
        data = stream.read(IMAGE_LIMIT + 1)
    if len(data) > IMAGE_LIMIT or not data.startswith((b"\x89PNG\r\n\x1a\n", b"\xff\xd8\xff")):
        raise OldSchoolPDFError("A imagem precisa ser um PNG ou JPEG válido de até 12 MiB.")
    try:
        image = pdf.mupdf.fz_new_image_from_buffer(pdf.mupdf.fz_new_buffer_from_copied_data(data))
    except (RuntimeError, ValueError):
        raise OldSchoolPDFError("Não foi possível ler a imagem selecionada.") from None
    if not 0 < image.w() * image.h() <= 16_000_000:
        raise OldSchoolPDFError("A imagem excede o limite de 16 milhões de pixels.")
    return data


def _line_regions(page: pdf.Page, rect: pdf.Rect) -> list:
    lines = {}
    for word in page.get_text("words", clip=rect):
        key = (word[5], word[6])
        box = pdf.Rect(word[:4])
        lines[key] = lines[key] | box if key in lines else box
    if not lines:
        raise OldSchoolPDFError("A área precisa conter texto da página para aplicar a marcação.")
    return list(lines.values())


def _position(page: pdf.Page, annot: pdf.Annot, x: float, y: float) -> None:
    bounds = annot.rect * page.rotation_matrix
    width, height = page.rect.width, page.rect.height
    if not (0 < bounds.width <= width and 0 < bounds.height <= height):
        raise OldSchoolPDFError("As dimensões do objeto não permitem movê-lo nesta página.")
    left = min(width - bounds.width, max(0, x * width))
    top = min(height - bounds.height, max(0, y * height))
    target = pdf.Rect(left, top, left + bounds.width, top + bounds.height) * page.derotation_matrix
    if annot.set_rect(target) is False:
        raise OldSchoolPDFError("O motor não conseguiu reposicionar o objeto.")
    if page.rotation and annot.flags & pdf.PDF_ANNOT_IS_NO_ROTATE:
        # MuPDF mantém o ícone na vertical e desloca a origem aparente em páginas giradas.
        dx, dy = target.tl - annot.rect.tl
        if annot.set_rect(target + (dx, dy, dx, dy)) is False:
            raise OldSchoolPDFError("O motor não conseguiu reposicionar o objeto.")


def add_annotation(page: pdf.Page, values: dict) -> None:
    kind = values["kind"]
    rect = page_rect(page, values["region"])
    if kind in {"highlight", "underline"}:
        regions = _line_regions(page, rect)
        if kind == "highlight":
            annot = page.add_highlight_annot(regions)
        else:
            annot = page.add_underline_annot(regions)
            annot.set_colors(stroke=(0.13, 0.37, 0.68))
        if values.get("text"):
            annot.set_info(content=_text(values["text"]))
        annot.update()
    elif kind == "comment":
        annot = page.add_text_annot(rect.top_left, _text(values["text"]))
        _position(page, annot, *values["region"][:2])
    elif kind == "text":
        page.add_freetext_annot(
            rect,
            _text(values["text"]),
            fontsize=11,
            fontname="Helv",
            text_color=(0.08, 0.17, 0.29),
            fill_color=(1, 1, 0.94),
            rotate=(values.get("view_rotation", 0) + page.rotation) % 360,
        )
    elif kind == "stamp":
        page.add_stamp_annot(rect, stamp=STAMPS[values["stamp"]])
    elif kind in {"rectangle", "ellipse"}:
        annot = page.add_rect_annot(rect) if kind == "rectangle" else page.add_circle_annot(rect)
        annot.set_border(width=1.5)
        annot.set_colors(stroke=(0.15, 0.38, 0.69))
        annot.update()
    elif kind in {"image", "visual_signature"}:
        if kind == "visual_signature" and "drawing" in values:
            encoded = values["drawing"]
            if not 0 < len(encoded) <= 256 * 1024:
                raise OldSchoolPDFError("O desenho da assinatura excede o limite.")
            try:
                image = b64decode(encoded, validate=True)
                if (
                    len(image) < 24
                    or not image.startswith(b"\x89PNG\r\n\x1a\n")
                    or unpack("!II", image[16:24]) != SIGNATURE_PAD_SIZE
                ):
                    raise ValueError
            except ValueError:
                raise OldSchoolPDFError("O desenho da assinatura está inválido.") from None
        else:
            image = _image(Path(values["path"]))
        annot = page.add_stamp_annot(rect, stamp=image)
        if kind == "visual_signature":
            annot.set_info(subject=VISUAL_SIGNATURE_SUBJECT)
    else:
        raise OldSchoolPDFError("Este tipo de anotação está indisponível.")


def annotation_info(page: pdf.Page, annot: pdf.Annot) -> AnnotationInfo | None:
    kind = ANNOTATION_TYPES.get(annot.type[0])
    if kind is None or annot.flags & (pdf.PDF_ANNOT_IS_HIDDEN | pdf.PDF_ANNOT_IS_INVISIBLE):
        return None
    info = annot.info
    if kind == "stamp" and info.get("name") == "ImageStamp":
        kind = "visual_signature" if info.get("subject") == VISUAL_SIGNATURE_SUBJECT else "image"
    editable = not (annot.flags & LOCKED)
    return AnnotationInfo(
        annot.xref,
        kind,
        normalized_rect(page, annot.rect),
        (info.get("content") or "")[:TEXT_LIMIT],
        editable and kind not in {"highlight", "underline"},
        editable,
    )


def edit_annotation(page: pdf.Page, action: str, values: dict) -> None:
    if action == "add_annotation":
        add_annotation(page, values)
        return
    annot = page.load_annot(values["xref"])
    info = annotation_info(page, annot) if annot else None
    if info is None or not info.editable:
        raise OldSchoolPDFError("A anotação está indisponível para edição.")
    if action == "remove_annotation":
        page.delete_annot(annot)
    elif action == "move_annotation":
        if not info.movable:
            raise OldSchoolPDFError("A marcação permanece vinculada ao texto.")
        delta = values["delta"]
        if len(delta) != 2 or any(not math.isfinite(part) or abs(part) > 1 for part in delta):
            raise OldSchoolPDFError("O deslocamento da anotação é inválido.")
        x, y = info.region[:2]
        _position(page, annot, x + delta[0], y + delta[1])
    else:
        if info.kind not in {"comment", "text", "highlight", "underline"}:
            raise OldSchoolPDFError("Este objeto não possui texto editável.")
        annot.set_info(content=_text(values["text"]))
        annot.update()


def field_info(page: pdf.Page, widget: pdf.Widget) -> FormField:
    kind = FIELD_TYPES.get(widget.field_type, "other")
    flags = widget.field_flags or 0
    blocked = pdf.PDF_FIELD_IS_READ_ONLY
    if kind == "text":
        blocked |= pdf.PDF_TX_FIELD_IS_PASSWORD | pdf.PDF_TX_FIELD_IS_FILE_SELECT
        blocked |= pdf.PDF_TX_FIELD_IS_RICH_TEXT
    if kind == "choice":
        blocked |= pdf.PDF_CH_FIELD_IS_MULTI_SELECT
    scripts = (
        widget.script,
        widget.script_calc,
        widget.script_change,
        widget.script_format,
        widget.script_stroke,
        widget.script_focus,
        widget.script_blur,
    )
    choices = ()
    if kind in {"checkbox", "radio"}:
        state = widget.on_state()
        if state:
            choices = ("Off", str(state)) if kind == "checkbox" else (str(state),)
    elif kind == "choice":
        choices = tuple(str(choice) for choice in (widget.choice_values or ())[:1000])
    editable = kind != "other" and not bool(flags & blocked) and not any(scripts)
    editable = editable and (kind == "text" or bool(choices))
    return FormField(
        widget.xref,
        (widget.field_label or widget.field_name or "Campo")[:512],
        kind,
        str(widget.field_value or "")[:TEXT_LIMIT],
        choices,
        editable,
        min(widget.text_maxlen or TEXT_LIMIT, TEXT_LIMIT),
        kind == "text" and bool(flags & pdf.PDF_TX_FIELD_IS_MULTILINE),
        normalized_rect(page, widget.rect),
    )


def update_field(page: pdf.Page, values: dict) -> None:
    widget = page.load_widget(values["xref"])
    if widget is None:
        raise OldSchoolPDFError("O campo não está disponível nesta página.")
    field = field_info(page, widget)
    value = values["value"]
    if not field.editable:
        raise OldSchoolPDFError(
            "Este campo requer uma leitura passiva ou um formato não suportado."
        )
    if field.kind == "text":
        if len(value) > field.max_length or (not field.multiline and "\n" in value):
            raise OldSchoolPDFError("O texto ultrapassa o limite do campo.")
    elif value not in field.choices:
        raise OldSchoolPDFError("Escolha um dos valores do campo.")
    if (widget.field_flags or 0) & pdf.PDF_FIELD_IS_REQUIRED and value in ("", "Off"):
        raise OldSchoolPDFError("Este campo é obrigatório.")
    widget.field_value = value
    widget.update()


def read_objects(page: pdf.Page) -> dict:
    annotations = []
    for annot in page.annots() or ():
        if info := annotation_info(page, annot):
            annotations.append(asdict(info))
            if len(annotations) == 300:
                break
    fields = []
    for widget in page.widgets() or ():
        fields.append(asdict(field_info(page, widget)))
        if len(fields) == 300:
            break
    return {"annotations": annotations, "fields": fields}
