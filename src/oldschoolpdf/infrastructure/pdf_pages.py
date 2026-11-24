"""Páginas em branco, corte de margens e mudança do tamanho do papel."""

from collections import Counter

import pymupdf as pdf

from oldschoolpdf.domain.editing import (
    MAX_BLANK_PAGES,
    MAX_CROP_MM,
    MIN_PAGE_POINTS,
    MM,
    paper_size,
)
from oldschoolpdf.domain.errors import OldSchoolPDFError
from oldschoolpdf.domain.text_editing import compare_form
from oldschoolpdf.infrastructure.pdf_editing import indices, pdf_array, transform_annotations

# Resolução da varredura que procura o conteúdo visível no corte automático.
AUTO_CROP_DPI = 48
WHITE = 245


def insert_blank(doc: pdf.Document, page: int, values: dict) -> int:
    """Insere páginas em branco antes ou depois da página indicada."""
    count = values.get("count", 1)
    where = values.get("where", "after")
    size = values.get("size", "same")
    if not isinstance(count, int) or not 1 <= count <= MAX_BLANK_PAGES:
        raise OldSchoolPDFError(f"Insira de 1 a {MAX_BLANK_PAGES} páginas por vez.")
    if where not in {"before", "after"}:
        raise OldSchoolPDFError("Escolha se as páginas entram antes ou depois da atual.")
    if size == "same":
        # Mesmo tamanho visível da página de referência, já com a rotação aplicada.
        reference = doc[page].rect
        width, height = reference.width, reference.height
    else:
        width, height = paper_size(size, values.get("orientation", "portrait"))
    position = page if where == "before" else page + 1
    for offset in range(count):
        target = position + offset
        doc.new_page(pno=target if target < doc.page_count else -1, width=width, height=height)
    return position


def _page_words(page: pdf.Page, clip: pdf.Rect | None = None) -> Counter:
    return Counter(compare_form(word[4]) for word in page.get_text("words", clip=clip))


def _media_box(page: pdf.Page) -> pdf.Rect:
    """MediaBox no sistema usado por `cropbox` e `set_cropbox`: x do PDF, y a partir do topo."""
    media = page.mediabox
    return pdf.Rect(media.x0, 0, media.x1, media.y1 - media.y0)


def _visible_to_box(page: pdf.Page, visible: pdf.Rect) -> pdf.Rect:
    """Converte um retângulo da página como ela aparece em coordenadas da CropBox."""
    box = visible * page.derotation_matrix
    box.normalize()
    box += (page.cropbox.x0, page.cropbox.y0, page.cropbox.x0, page.cropbox.y0)
    return box & _media_box(page)


def _content_area(page: pdf.Page) -> pdf.Rect | None:
    """Área com tinta da página como ela aparece, ou None se estiver em branco."""
    scale = AUTO_CROP_DPI / 72
    pixmap = page.get_pixmap(matrix=pdf.Matrix(scale, scale), colorspace=pdf.csGRAY, alpha=False)
    width, height, samples = pixmap.width, pixmap.height, pixmap.samples
    rows = [y for y in range(height) if min(samples[y * width : (y + 1) * width]) < WHITE]
    if not rows:
        return None
    left, right = width, -1
    for y in range(rows[0], rows[-1] + 1):
        line = samples[y * width : (y + 1) * width]
        dark = [x for x in range(width) if line[x] < WHITE]
        if dark:
            left, right = min(left, dark[0]), max(right, dark[-1])
    return pdf.Rect(left, rows[0], right + 1, rows[-1] + 1) / scale


def _margins(values: dict, key: str) -> tuple[float, float, float, float]:
    raw = values.get(key)
    if (
        not isinstance(raw, list | tuple)
        or len(raw) != 4
        or not all(isinstance(v, int | float) and 0 <= v <= MAX_CROP_MM for v in raw)
    ):
        raise OldSchoolPDFError(f"Informe margens entre 0 e {MAX_CROP_MM} mm.")
    return tuple(float(v) * MM for v in raw)


def crop_pages(doc: pdf.Document, values: dict) -> tuple[int, dict]:
    """Corta as margens visíveis. O conteúdo fora do corte continua no arquivo."""
    mode = values.get("mode")
    if mode not in {"margins", "auto", "reset"}:
        raise OldSchoolPDFError("Escolha como cortar as páginas.")
    selected = indices(values["ranges"], doc.page_count)
    left = top = right = bottom = 0.0
    if mode == "margins":
        left, top, right, bottom = _margins(values, "margins")
    elif mode == "auto":
        padding = _margins(values, "margins")[0]
    changed = blank = 0
    for number in selected:
        page = doc[number]
        if mode == "reset":
            full = _media_box(page)
            if max(abs(a - b) for a, b in zip(full, page.cropbox, strict=True)) < 0.5:
                continue
            page.set_cropbox(full)
        else:
            area = page.rect
            if mode == "auto":
                content = _content_area(page)
                if content is None:
                    blank += 1
                    continue
                target = (content + (-padding, -padding, padding, padding)) & area
            else:
                target = pdf.Rect(area.x0 + left, area.y0 + top, area.x1 - right, area.y1 - bottom)
            if target.width < MIN_PAGE_POINTS or target.height < MIN_PAGE_POINTS:
                raise OldSchoolPDFError(
                    f"O corte deixaria a página {number + 1} pequena demais. Use margens menores."
                )
            box = _visible_to_box(page, target)
            if max(abs(a - b) for a, b in zip(box, page.cropbox, strict=True)) < 0.5:
                continue
            page.set_cropbox(box)
        changed += 1
    if not changed:
        raise OldSchoolPDFError(
            "Nenhuma página mudou. As páginas escolhidas já estão nesse tamanho"
            + (" ou estão em branco." if blank else ".")
        )
    return selected[0], {"pages": changed, "blank": blank}


def view_matrix(page: pdf.Page) -> pdf.Matrix:
    """Do espaço do PDF para a página como ela aparece: corte e rotação aplicados."""
    crop, media = page.cropbox, page.mediabox
    # `cropbox` conta y a partir do topo da MediaBox; o PDF conta a partir de baixo.
    top = media.y1 - crop.y0
    return pdf.Matrix(1, 0, 0, -1, -crop.x0, top) * page.rotation_matrix


def resize_pages(doc: pdf.Document, values: dict) -> tuple[int, dict]:
    """Ajusta cada página a um papel novo, centralizada e sem distorção."""
    size = values.get("size")
    orientation = values.get("orientation", "auto")
    if orientation not in {"auto", "portrait", "landscape"}:
        raise OldSchoolPDFError("Escolha uma orientação válida.")
    selected = indices(values["ranges"], doc.page_count)
    changed = 0
    for number in selected:
        page = doc[number]
        visible = page.rect
        wanted = orientation
        if wanted == "auto":
            wanted = "landscape" if visible.width > visible.height else "portrait"
        width, height = paper_size(size, wanted)
        if abs(visible.width - width) < 1 and abs(visible.height - height) < 1:
            continue
        scale = min(width / visible.width, height / visible.height)
        if not 0.02 <= scale <= 50:
            raise OldSchoolPDFError(f"A página {number + 1} tem um tamanho incompatível.")
        words = _page_words(page)
        old_view = view_matrix(page)
        # O que estava fora do corte antigo continua escondido no papel novo.
        clip = visible * ~old_view
        clip.normalize()
        # Caixa nova sem rotação; a rotação da página continua a mesma.
        if page.rotation in (90, 270):
            box = pdf.Rect(0, 0, height, width)
        else:
            box = pdf.Rect(0, 0, width, height)
        offset_x = (width - visible.width * scale) / 2
        offset_y = (height - visible.height * scale) / 2
        fit = pdf.Matrix(scale, 0, 0, scale, offset_x, offset_y)
        array = pdf_array(box)
        for key in ("MediaBox", "CropBox"):
            doc.xref_set_key(page.xref, key, array)
        for key in ("TrimBox", "BleedBox", "ArtBox"):
            if doc.xref_get_key(page.xref, key)[0] != "null":
                doc.xref_set_key(page.xref, key, array)
        page = doc[number]
        matrix = old_view * fit * ~view_matrix(page)
        _wrap_contents(doc, page, matrix, clip)
        transform_annotations(doc, page, matrix)
        page = doc[number]
        if abs(page.rect.width - width) > 1 or abs(page.rect.height - height) > 1:
            raise OldSchoolPDFError("O novo tamanho da página não pôde ser confirmado.")
        inside = (visible * fit) * page.derotation_matrix
        if _page_words(page, clip=inside) != words:
            raise OldSchoolPDFError(
                f"O texto da página {number + 1} mudou ao redimensionar. Nada foi alterado."
            )
        changed += 1
    if not changed:
        raise OldSchoolPDFError("As páginas escolhidas já estão nesse tamanho.")
    return selected[0], {"pages": changed}


def _number(value: float) -> str:
    return f"{value:.6f}".rstrip("0").rstrip(".") or "0"


def _new_stream(doc: pdf.Document, data: bytes) -> int:
    xref = doc.get_new_xref()
    doc.update_object(xref, "<<>>")
    doc.update_stream(xref, data, compress=True)
    return xref


def _wrap_contents(doc: pdf.Document, page: pdf.Page, matrix: pdf.Matrix, clip: pdf.Rect) -> None:
    """Desenha o conteúdo antigo dentro de uma transformação.

    Dois fluxos novos, um antes e um depois, envolvem os fluxos antigos sem alterá-los:
    páginas que compartilham o conteúdo antigo continuam iguais, e cabeçalhos ou marcas
    d'água do programa, que são fluxos próprios, continuam removíveis.
    """
    transform = " ".join(_number(value) for value in matrix)
    area = " ".join(_number(value) for value in (clip.x0, clip.y0, clip.width, clip.height))
    head = _new_stream(doc, f"q {transform} cm {area} re W n\n".encode())
    tail = _new_stream(doc, b"\nQ\n")
    streams = [head, *page.get_contents(), tail]
    doc.xref_set_key(page.xref, "Contents", "[" + " ".join(f"{x} 0 R" for x in streams) + "]")
