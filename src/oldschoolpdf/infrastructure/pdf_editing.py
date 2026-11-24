"""Edições aplicadas a uma revisão descartável do documento."""

import math
import re
from base64 import b64decode
from collections.abc import Iterable
from dataclasses import asdict
from pathlib import Path
from struct import unpack

import pymupdf as pdf

from oldschoolpdf.domain.editing import (
    MAX_STROKE_POINTS,
    MAX_STROKES,
    PEN_COLORS,
    PEN_WIDTHS,
    STROKE_KINDS,
    TEXT_ANNOTATIONS,
    TEXT_MARKUPS,
    AnnotationInfo,
    FormField,
)
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
    pdf.PDF_ANNOT_STRIKE_OUT: "strikeout",
    pdf.PDF_ANNOT_INK: "ink",
    pdf.PDF_ANNOT_LINE: "line",
}
# O marca-texto amarelo fica translúcido para não esconder o que está embaixo.
MARKER_OPACITY = 0.45
FIELD_TYPES = {
    pdf.PDF_WIDGET_TYPE_TEXT: "text",
    pdf.PDF_WIDGET_TYPE_CHECKBOX: "checkbox",
    pdf.PDF_WIDGET_TYPE_COMBOBOX: "choice",
    pdf.PDF_WIDGET_TYPE_LISTBOX: "choice",
    pdf.PDF_WIDGET_TYPE_RADIOBUTTON: "radio",
}
STAMPS = (pdf.STAMP_Approved, pdf.STAMP_ForComment, pdf.STAMP_Final, pdf.STAMP_Confidential)
LOCKED = pdf.PDF_ANNOT_IS_READ_ONLY | pdf.PDF_ANNOT_IS_LOCKED | pdf.PDF_ANNOT_IS_LOCKED_CONTENTS


# Chaves de anotações com pares de coordenadas na página.
POINT_KEYS = ("QuadPoints", "Vertices", "L", "CL")
NUMBER = re.compile(r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?")


def _numbers(text: str) -> list[float]:
    return [float(value) for value in NUMBER.findall(text)]


def pdf_array(values) -> str:
    return "[" + " ".join(f"{value:.4f}".rstrip("0").rstrip(".") for value in values) + "]"


def _transform_points(values: list[float], matrix: pdf.Matrix) -> list[float]:
    result = []
    for x, y in zip(values[::2], values[1::2], strict=True):
        point = pdf.Point(x, y) * matrix
        result += [point.x, point.y]
    return result


def transform_annotations(doc: pdf.Document, page: pdf.Page, matrix: pdf.Matrix) -> None:
    """Leva as anotações, links e campos para a nova posição do conteúdo."""
    for xref, _kind, _ in page.annot_xrefs():
        transform_annotation(doc, xref, matrix)


def transform_annotation(doc: pdf.Document, xref: int, matrix: pdf.Matrix) -> None:
    """Aplica `matrix` (espaço do PDF) à posição e aos pontos de uma anotação."""
    scale = abs(matrix.a) or abs(matrix.b)
    kind, rect = doc.xref_get_key(xref, "Rect")
    if kind != "array":
        return
    corners = _numbers(rect)
    if len(corners) != 4:
        raise OldSchoolPDFError("Uma anotação da página tem uma posição inválida.")
    moved = pdf.Rect(
        pdf.Point(corners[0], corners[1]) * matrix, pdf.Point(corners[2], corners[3]) * matrix
    )
    moved.normalize()
    doc.xref_set_key(xref, "Rect", pdf_array(moved))
    for key in POINT_KEYS:
        kind, value = doc.xref_get_key(xref, key)
        if kind == "array":
            numbers = _numbers(value)
            if len(numbers) % 2:
                raise OldSchoolPDFError("Uma anotação da página tem pontos inválidos.")
            doc.xref_set_key(xref, key, pdf_array(_transform_points(numbers, matrix)))
    kind, value = doc.xref_get_key(xref, "InkList")
    if kind == "array":
        strokes = re.findall(r"\[([^\[\]]*)\]", value)
        moved_strokes = [pdf_array(_transform_points(_numbers(s), matrix)) for s in strokes]
        doc.xref_set_key(xref, "InkList", "[" + " ".join(moved_strokes) + "]")
    kind, value = doc.xref_get_key(xref, "RD")
    if kind == "array":
        doc.xref_set_key(xref, "RD", pdf_array(v * scale for v in _numbers(value)))


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


def read_image(path: Path) -> bytes:
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


def _pen(values: dict) -> tuple[tuple[float, float, float], float, float]:
    """Cor, espessura e opacidade escolhidas na barra de desenho."""
    color = values.get("color", "blue")
    width = values.get("width", "medium")
    if color not in PEN_COLORS or width not in PEN_WIDTHS:
        raise OldSchoolPDFError("Escolha uma cor e uma espessura válidas.")
    return PEN_COLORS[color][1], PEN_WIDTHS[width][1], MARKER_OPACITY if color == "yellow" else 1.0


def _page_points(page: pdf.Page, raw, minimum: int) -> list[tuple[float, float]]:
    """Pontos normalizados da página como aparece, levados para as coordenadas do PDF."""
    if not isinstance(raw, list) or not minimum <= len(raw) <= MAX_STROKE_POINTS:
        raise OldSchoolPDFError("O desenho chegou em formato inválido.")
    width, height = page.rect.width, page.rect.height
    points = []
    for item in raw:
        if (
            not isinstance(item, list | tuple)
            or len(item) != 2
            or not all(
                isinstance(v, int | float) and not isinstance(v, bool) and 0 <= v <= 1 for v in item
            )
        ):
            raise OldSchoolPDFError("O desenho tem pontos fora da página.")
        point = pdf.Point(item[0] * width, item[1] * height) * page.derotation_matrix
        points.append((point.x, point.y))
    return points


def _add_stroke(page: pdf.Page, kind: str, values: dict) -> None:
    color, width, opacity = _pen(values)
    if kind == "ink":
        strokes = values.get("strokes")
        if not isinstance(strokes, list) or not 1 <= len(strokes) <= MAX_STROKES:
            raise OldSchoolPDFError(f"Desenhe de 1 a {MAX_STROKES} traços por vez.")
        paths = [_page_points(page, stroke, 2) for stroke in strokes]
        if sum(len(path) for path in paths) > MAX_STROKE_POINTS:
            raise OldSchoolPDFError("O desenho é detalhado demais. Grave em partes.")
        annot = page.add_ink_annot(paths)
    else:
        start, end = _page_points(page, values.get("points"), 2)
        if math.dist(start, end) < 3:
            raise OldSchoolPDFError("Arraste um pouco mais para desenhar a linha.")
        annot = page.add_line_annot(start, end)
    if kind == "arrow":
        # A ponta fechada da seta usa a cor de preenchimento.
        annot.set_line_ends(pdf.PDF_ANNOT_LE_NONE, pdf.PDF_ANNOT_LE_CLOSED_ARROW)
        annot.set_colors(stroke=color, fill=color)
    else:
        annot.set_colors(stroke=color)
    annot.set_border(width=width)
    if opacity < 1:
        annot.set_opacity(opacity)
    annot.update()


def _translate(page: pdf.Page, annot: pdf.Annot, delta) -> None:
    """Move linhas, setas e desenhos à mão deslocando os pontos, sem sair da página."""
    bounds = annot.rect * page.rotation_matrix
    width, height = page.rect.width, page.rect.height
    dx = min(max(delta[0] * width, -bounds.x0), width - bounds.x1)
    dy = min(max(delta[1] * height, -bounds.y0), height - bounds.y1)
    turn = page.derotation_matrix
    shift = pdf.Point(dx, dy) * turn - pdf.Point(0, 0) * turn
    xref = annot.xref
    # No espaço do PDF o eixo y aponta para cima.
    transform_annotation(page.parent, xref, pdf.Matrix(1, 0, 0, 1, shift.x, -shift.y))
    moved = page.load_annot(xref)
    if moved is None:
        raise OldSchoolPDFError("O motor não conseguiu reposicionar o objeto.")
    moved.update()


def add_annotation(page: pdf.Page, values: dict) -> None:
    kind = values["kind"]
    if kind in STROKE_KINDS:
        _add_stroke(page, kind, values)
        return
    rect = page_rect(page, values["region"])
    if kind in TEXT_MARKUPS:
        regions = _line_regions(page, rect)
        if kind == "highlight":
            annot = page.add_highlight_annot(regions)
        elif kind == "underline":
            annot = page.add_underline_annot(regions)
            annot.set_colors(stroke=(0.13, 0.37, 0.68))
        else:
            annot = page.add_strikeout_annot(regions)
            annot.set_colors(stroke=(0.82, 0.1, 0.1))
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
        if "color" in values:
            color, width, opacity = _pen(values)
        else:
            color, width, opacity = (0.15, 0.38, 0.69), 1.5, 1.0
        annot.set_border(width=width)
        annot.set_colors(stroke=color)
        if opacity < 1:
            annot.set_opacity(opacity)
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
            image = read_image(Path(values["path"]))
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
    if kind == "line" and (annot.line_ends or (0, 0))[1] != pdf.PDF_ANNOT_LE_NONE:
        kind = "arrow"
    editable = not (annot.flags & LOCKED)
    return AnnotationInfo(
        annot.xref,
        kind,
        normalized_rect(page, annot.rect),
        (info.get("content") or "")[:TEXT_LIMIT],
        editable and kind not in TEXT_MARKUPS,
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
        if info.kind in STROKE_KINDS:
            _translate(page, annot, delta)
        else:
            x, y = info.region[:2]
            _position(page, annot, x + delta[0], y + delta[1])
    else:
        if info.kind not in TEXT_ANNOTATIONS:
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
