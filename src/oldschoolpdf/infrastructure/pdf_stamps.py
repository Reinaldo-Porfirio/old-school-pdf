"""Cabeçalho, rodapé, numeração e marca d'água gravados no conteúdo das páginas.

Cada marca é desenhada numa página auxiliar do tamanho da página visível e entra como
um Form XObject, chamado por um fluxo de conteúdo só dela. O dicionário /PieceInfo da
página guarda quais fluxos são do Old School PDF: assim a marca pode ser trocada ou
removida depois, mesmo com o PDF gravado e reaberto.

A marca d'água de texto vira desenho vetorial (contorno das letras). Ela não aparece na
busca, na cópia de texto nem na conversão para Word, e não atrapalha a edição do texto.
"""

import math
import re
from collections import Counter
from contextlib import contextmanager
from pathlib import Path

import pymupdf as pdf

from oldschoolpdf.domain.editing import MM
from oldschoolpdf.domain.errors import OldSchoolPDFError
from oldschoolpdf.domain.stamps import (
    MAX_MARGIN_MM,
    MAX_STAMP_SIZE,
    MAX_STAMP_TEXT,
    MAX_START,
    MAX_TOKEN_VALUE,
    MAX_WATERMARK_SIZE,
    MIN_IMAGE_SCALE,
    MIN_MARGIN_MM,
    MIN_OPACITY,
    MIN_STAMP_SIZE,
    MIN_WATERMARK_SIZE,
    SLOTS,
    STAMP_COLORS,
    STAMP_FONTS,
    STAMP_KINDS,
    WATERMARK_ANGLES,
    WATERMARK_LAYERS,
    check_choice,
    check_number,
    expand_tokens,
    one_line,
)
from oldschoolpdf.domain.text_editing import compare_form
from oldschoolpdf.infrastructure.pdf_editing import indices, read_image
from oldschoolpdf.infrastructure.pdf_pages import view_matrix

PIECE = "OldSchoolPDF"
KEYS = {"header": "Header", "watermark": "Watermark"}
ALPHA = "OSPDFAlpha"
# Distância mínima entre textos da mesma linha do cabeçalho ou do rodapé.
SLOT_GAP = 6.0
# Prévia pequena usada para saber se a marca d'água ficou visível.
CHECK_SCALE = 1 / 3
CHANGED_LEVEL = 3
CHANGED_PIXELS = 12


def _references(value: str) -> list[int]:
    return [int(number) for number in re.findall(r"(\d+)\s+0\s+R", value)]


def _number(value: float) -> str:
    return f"{value:.5f}".rstrip("0").rstrip(".") or "0"


def tracked(doc: pdf.Document, page: pdf.Page) -> dict[str, list[int]]:
    """Fluxos de conteúdo do programa que ainda desenham algo nesta página, por tipo."""
    contents = set(page.get_contents())
    result = {}
    for kind, key in KEYS.items():
        found, value = doc.xref_get_key(page.xref, f"PieceInfo/{PIECE}/Private/{key}")
        xrefs = _references(value) if found == "array" else []
        result[kind] = [xref for xref in xrefs if xref in contents]
    return result


def _record(doc: pdf.Document, page: pdf.Page, kind: str, xrefs: list[int]) -> None:
    others = {key: value for key, value in tracked(doc, page).items() if key != kind}
    if not xrefs and not any(others.values()):
        doc.xref_set_key(page.xref, f"PieceInfo/{PIECE}", "null")
        return
    value = "[" + " ".join(f"{xref} 0 R" for xref in xrefs) + "]" if xrefs else "null"
    doc.xref_set_key(page.xref, f"PieceInfo/{PIECE}/Private/{KEYS[kind]}", value)
    doc.xref_set_key(page.xref, f"PieceInfo/{PIECE}/LastModified", f"({pdf.get_pdf_now()})")


def remove(doc: pdf.Document, number: int, kind: str) -> bool:
    """Tira da página os fluxos do tipo pedido. Os objetos órfãos somem ao gravar."""
    page = doc[number]
    current = tracked(doc, page)[kind]
    if not current:
        return False
    contents = [xref for xref in page.get_contents() if xref not in current]
    doc.xref_set_key(page.xref, "Contents", "[" + " ".join(f"{x} 0 R" for x in contents) + "]")
    _record(doc, doc[number], kind, [])
    return True


def _xobject_name(doc: pdf.Document, xref: int) -> str | None:
    match = re.search(rb"/([A-Za-z0-9_.\-]+)\s+Do", doc.xref_stream(xref) or b"")
    return match[1].decode() if match else None


def _resources(doc: pdf.Document, page: pdf.Page) -> tuple[int, str]:
    """Objeto e caminho do dicionário de recursos da página, para gravar chaves nele."""
    kind, value = doc.xref_get_key(page.xref, "Resources")
    if kind == "xref":
        return int(value.split()[0]), ""
    if kind == "dict":
        return page.xref, "Resources/"
    raise OldSchoolPDFError("Os recursos da página não permitem gravar a marca.")


def detach(doc: pdf.Document, number: int) -> dict | None:
    """Tira da página, por um momento, os fluxos do programa. Devolve como recolocar.

    A edição do texto original usa redação, que junta os fluxos de conteúdo e refaz os
    recursos da página: sem isso, o cabeçalho e a marca d'água deixariam de ser removíveis.
    """
    page = doc[number]
    marks = tracked(doc, page)
    ours = [xref for kind in STAMP_KINDS for xref in marks[kind]]
    if not ours:
        return None
    contents = page.get_contents()
    names = {item[1]: item[0] for item in page.get_xobjects() if item[2] == 0}
    resources = {}
    for xref in ours:
        name = _xobject_name(doc, xref)
        if name in names:
            resources[name] = names[name]
    first = next((index for index, xref in enumerate(contents) if xref not in ours), 0)
    saved = {
        "raw": doc.xref_get_key(page.xref, "Contents"),
        "front": [xref for xref in contents[:first] if xref in ours],
        "back": [xref for xref in contents[first:] if xref in ours],
        "resources": resources,
    }
    rest = [xref for xref in contents if xref not in ours]
    doc.xref_set_key(page.xref, "Contents", "[" + " ".join(f"{x} 0 R" for x in rest) + "]")
    return saved


def reattach(doc: pdf.Document, number: int, saved: dict | None) -> None:
    """Devolve os fluxos tirados por `detach`, no começo e no fim do conteúdo."""
    if saved is None:
        return
    page = doc[number]
    middle = [
        xref
        for xref in page.get_contents()
        if xref not in saved["front"] and xref not in saved["back"]
    ]
    streams = [*saved["front"], *middle, *saved["back"]]
    doc.xref_set_key(page.xref, "Contents", "[" + " ".join(f"{x} 0 R" for x in streams) + "]")
    page = doc[number]
    present = {item[1]: item[0] for item in page.get_xobjects() if item[2] == 0}
    missing = {name: xref for name, xref in saved["resources"].items() if present.get(name) != xref}
    if not missing:
        return
    if any(name in present for name in missing):
        # Os nomes do programa são únicos; outro objeto com o mesmo nome seria um erro.
        raise OldSchoolPDFError("A página tem um recurso com o nome de uma marca do programa.")
    target, prefix = _resources(doc, page)
    for name, xref in missing.items():
        doc.xref_set_key(target, f"{prefix}XObject/{name}", f"{xref} 0 R")


@contextmanager
def bare_page(doc: pdf.Document, number: int):
    """A página sem as marcas do programa, só para leitura; depois volta como estava."""
    saved = detach(doc, number)
    try:
        yield doc[number]
    finally:
        if saved is not None:
            kind, value = saved["raw"]
            doc.xref_set_key(doc[number].xref, "Contents", value if kind != "null" else "null")


def stamp_areas(page: pdf.Page) -> list[pdf.Rect]:
    """Onde está o texto que o programa gravou (cabeçalho, rodapé, numeração)."""
    doc, number = page.parent, page.number
    if not any(tracked(doc, page).values()):
        return []

    def words(target: pdf.Page) -> Counter:
        return Counter(
            (word[4], *(round(value, 1) for value in word[:4])) for word in target.get_text("words")
        )

    full = words(page)
    with bare_page(doc, number) as bare:
        rest = words(bare)
    return [pdf.Rect(item[1:]) for item in (full - rest).elements()]


def _stamp(
    doc: pdf.Document,
    number: int,
    source: pdf.Document,
    source_page: int,
    kind: str,
    *,
    overlay: bool,
    opacity: float = 1.0,
) -> None:
    """Desenha a página auxiliar sobre (ou sob) a página, como ela aparece na tela."""
    page = doc[number]
    if not page.is_wrapped:
        # Isola o estado gráfico do conteúdo antigo antes, para o fluxo novo ser o único.
        page.wrap_contents()
        page = doc[number]
    before = set(page.get_contents())
    # O PyMuPDF cuida dos recursos da página (inclusive herdados); a matriz é refeita abaixo,
    # porque o posicionamento dele erra em páginas giradas com CropBox deslocada.
    page.show_pdf_page(page.rect, source, source_page, overlay=overlay, keep_proportion=False)
    page = doc[number]
    added = [xref for xref in page.get_contents() if xref not in before]
    name = _xobject_name(doc, added[0]) if len(added) == 1 else None
    names = {item[1]: item[0] for item in page.get_xobjects()}
    outer = names.get(name) if name else None
    if not outer:
        raise OldSchoolPDFError(f"O motor não conseguiu gravar a marca na página {number + 1}.")
    # Um nome próprio evita colidir com os "fzFrm" que o PyMuPDF cria em outras edições.
    unique = f"OSPDF{outer}"
    target, prefix = _resources(doc, page)
    doc.xref_set_key(target, f"{prefix}XObject/{name}", "null")
    doc.xref_set_key(target, f"{prefix}XObject/{unique}", f"{outer} 0 R")
    name = unique
    width, height = source[source_page].rect.width, source[source_page].rect.height
    doc.xref_set_key(outer, "Matrix", "[1 0 0 1 0 0]")
    doc.xref_set_key(outer, "BBox", f"[0 0 {_number(width)} {_number(height)}]")
    if opacity < 1:
        alpha = _number(opacity)
        doc.xref_set_key(outer, f"Resources/ExtGState/{ALPHA}", f"<</ca {alpha}/CA {alpha}>>")
        doc.update_stream(outer, f"/{ALPHA} gs\n".encode() + (doc.xref_stream(outer) or b""))
    # Da página auxiliar (y para cima) para a página como aparece, e dela para o PDF.
    matrix = pdf.Matrix(1, 0, 0, -1, 0, height) * ~view_matrix(page)
    transform = " ".join(_number(value) for value in matrix)
    doc.update_stream(added[0], f"q {transform} cm /{name} Do Q\n".encode())
    _record(doc, page, kind, [*tracked(doc, page)[kind], added[0]])


def _check_glyphs(font: pdf.Font, text: str) -> None:
    for char in text:
        if not char.isspace() and not font.has_glyph(ord(char)):
            raise OldSchoolPDFError(
                f"O caractere “{char}” não existe na fonte escolhida. Troque o caractere."
            )


def _occupied(page: pdf.Page) -> list[pdf.Rect]:
    """Texto, imagens e desenhos da página, nas coordenadas da página como aparece."""
    turn = page.rotation_matrix
    boxes = [pdf.Rect(word[:4]) * turn for word in page.get_text("words")]
    boxes += [pdf.Rect(item["bbox"]) * turn for item in page.get_image_info()]
    for drawing in page.get_drawings():
        area = pdf.Rect(drawing["rect"]) * turn
        # Fundos e molduras da página inteira não contam.
        if area.width < page.rect.width * 0.9 or area.height < page.rect.height * 0.9:
            boxes.append(area)
    return boxes


def _int(value: object, low: int, high: int, what: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
        raise OldSchoolPDFError(f"Informe {what} entre {low} e {high}.")
    return value


def header_footer(doc: pdf.Document, values: dict) -> tuple[int, dict]:
    """Numeração e textos de cabeçalho e rodapé nas páginas escolhidas."""
    selected = indices(values["ranges"], doc.page_count)
    font_key = check_choice(values.get("font", "sans"), STAMP_FONTS, "uma fonte")
    size = check_number(values.get("size", 10), MIN_STAMP_SIZE, MAX_STAMP_SIZE, "o tamanho")
    color = STAMP_COLORS[check_choice(values.get("color", "black"), STAMP_COLORS, "uma cor")][1]
    margin = check_number(values.get("margin", 12), MIN_MARGIN_MM, MAX_MARGIN_MM, "a margem") * MM
    start = _int(values.get("start", 1), 1, MAX_START, "o primeiro número")
    date = one_line(values.get("date", ""), MAX_TOKEN_VALUE, "da data")
    filename = one_line(values.get("file", ""), MAX_TOKEN_VALUE, "do nome do arquivo")
    raw = values.get("slots")
    if not isinstance(raw, dict) or set(raw) - set(SLOTS):
        raise OldSchoolPDFError("As posições do cabeçalho e do rodapé são inválidas.")
    templates = {
        slot: text
        for slot in SLOTS
        if (text := one_line(raw.get(slot, ""), MAX_STAMP_TEXT, "do cabeçalho ou rodapé"))
    }
    if not templates:
        raise OldSchoolPDFError("Escreva o texto de pelo menos uma posição.")
    font = pdf.Font(STAMP_FONTS[font_key][1])
    total = start + len(selected) - 1
    source = pdf.open()
    plans = []
    for index, number in enumerate(selected):
        page = doc[number]
        width, height = page.rect.width, page.rect.height
        auxiliary = source.new_page(width=width, height=height)
        writer = pdf.TextWriter(auxiliary.rect, color=color)
        boxes = []
        for row in ("header", "footer"):
            spans = []
            for slot in (slot for slot in SLOTS if slot.startswith(row)):
                if slot not in templates:
                    continue
                text = expand_tokens(templates[slot], start + index, total, date, filename)
                _check_glyphs(font, text)
                length = font.text_length(text, fontsize=size)
                if length > width - 2 * margin:
                    raise OldSchoolPDFError(
                        f"O texto “{text[:40]}” não cabe na largura da página {number + 1}. "
                        "Use um texto menor, uma fonte menor ou uma margem menor."
                    )
                align = slot.split("_")[1]
                if align == "left":
                    left = margin
                elif align == "center":
                    left = (width - length) / 2
                else:
                    left = width - margin - length
                if row == "header":
                    baseline = margin + font.ascender * size
                else:
                    baseline = height - margin + font.descender * size
                if baseline - font.ascender * size < 0 or baseline > height:
                    raise OldSchoolPDFError("A margem é grande demais para esta página.")
                writer.append((left, baseline), text, font=font, fontsize=size)
                spans.append((left, left + length))
                boxes.append(
                    (
                        pdf.Rect(
                            left,
                            baseline - font.ascender * size,
                            left + length,
                            baseline - font.descender * size,
                        ),
                        text,
                    )
                )
            spans.sort()
            for first, second in zip(spans, spans[1:], strict=False):
                if first[1] + SLOT_GAP > second[0]:
                    place = "cabeçalho" if row == "header" else "rodapé"
                    raise OldSchoolPDFError(
                        f"Os textos do {place} se encostam na página {number + 1}. "
                        "Use textos menores ou uma fonte menor."
                    )
        writer.write_text(auxiliary)
        plans.append((number, auxiliary.number, boxes))
    replaced = 0
    crowded = []
    for number, auxiliary, boxes in plans:
        if values.get("replace", True) and remove(doc, number, "header"):
            replaced += 1
        # A marca d'água do próprio programa não conta como conteúdo da página.
        with bare_page(doc, number) as bare:
            occupied = _occupied(bare)
        if any((box + (-2, -2, 2, 2)).intersects(other) for box, _ in boxes for other in occupied):
            crowded.append(number + 1)
        _stamp(doc, number, source, auxiliary, "header", overlay=True)
        page = doc[number]
        for box, text in boxes:
            found = page.get_text("text", clip=(box + (-1, -1, 1, 1)) * page.derotation_matrix)
            if compare_form(text) not in compare_form(found):
                raise OldSchoolPDFError(
                    f"O texto gravado na página {number + 1} não conferiu. Nada foi alterado."
                )
    return selected[0], {
        "pages": len(selected),
        "replaced": replaced,
        "crowded": crowded[:10],
        "crowded_count": len(crowded),
    }


def _text_source(width: float, height: float, values: dict) -> pdf.Document:
    text = one_line(values.get("text", ""), MAX_STAMP_TEXT, "da marca d'água")
    if not text:
        raise OldSchoolPDFError("Escreva o texto da marca d'água.")
    font_key = check_choice(values.get("font", "sans"), STAMP_FONTS, "uma fonte")
    color = STAMP_COLORS[check_choice(values.get("color", "gray"), STAMP_COLORS, "uma cor")][1]
    angle_key = check_choice(values.get("angle", "diagonal"), WATERMARK_ANGLES, "um ângulo")
    size = values.get("size", 0)
    if size != 0:
        size = check_number(size, MIN_WATERMARK_SIZE, MAX_WATERMARK_SIZE, "o tamanho")
    font = pdf.Font(STAMP_FONTS[font_key][2])
    _check_glyphs(font, text)
    unit = font.text_length(text, fontsize=1)
    if angle_key == "diagonal":
        angle = math.degrees(math.atan2(height, width))
        room = math.hypot(width, height) * 0.72
    elif angle_key == "horizontal":
        angle, room = 0.0, width * 0.8
    else:
        angle, room = 90.0, height * 0.8
    if not size:
        size = max(MIN_WATERMARK_SIZE, min(MAX_WATERMARK_SIZE, room / max(unit, 0.01)))
    source = pdf.open()
    auxiliary = source.new_page(width=width, height=height)
    center = pdf.Point(width / 2, height / 2)
    baseline = center.y + (font.ascender + font.descender) / 2 * size
    writer = pdf.TextWriter(auxiliary.rect, color=color)
    writer.append((center.x - unit * size / 2, baseline), text, font=font, fontsize=size)
    # Com y para baixo, o ângulo positivo sobe da esquerda para a direita.
    writer.write_text(auxiliary, morph=(center, pdf.Matrix(angle)))
    # O SVG com texto em contorno vira um PDF só com desenhos vetoriais.
    svg = auxiliary.get_svg_image(text_as_path=True)
    vector = pdf.open("pdf", pdf.open("svg", svg.encode()).convert_to_pdf())
    if vector.page_count != 1 or vector[0].get_text().strip() or not vector[0].get_drawings():
        raise OldSchoolPDFError("Não foi possível desenhar a marca d'água com esse texto.")
    return vector


def _image_source(width: float, height: float, data: bytes, scale: float) -> pdf.Document:
    source = pdf.open()
    auxiliary = source.new_page(width=width, height=height)
    image = pdf.Pixmap(data)
    target = width * scale / 100
    ratio = image.height / max(image.width, 1)
    target = min(target, height * 0.95 / max(ratio, 1e-6))
    left, top = (width - target) / 2, (height - target * ratio) / 2
    auxiliary.insert_image(pdf.Rect(left, top, left + target, top + target * ratio), stream=data)
    return source


def _thumbnail(page: pdf.Page) -> pdf.Pixmap:
    return page.get_pixmap(
        matrix=pdf.Matrix(CHECK_SCALE, CHECK_SCALE), colorspace=pdf.csGRAY, alpha=False
    )


def _changed(before: pdf.Pixmap, after: pdf.Pixmap) -> bool:
    if (before.width, before.height) != (after.width, after.height):
        return True
    count = 0
    for old, new in zip(before.samples, after.samples, strict=True):
        if abs(old - new) >= CHANGED_LEVEL:
            count += 1
            if count >= CHANGED_PIXELS:
                return True
    return False


def watermark(doc: pdf.Document, values: dict) -> tuple[int, dict]:
    """Marca d'água de texto (em contorno vetorial) ou de imagem, com transparência."""
    selected = indices(values["ranges"], doc.page_count)
    mode = check_choice(values.get("mode"), {"text", "image"}, "o tipo de marca d'água")
    opacity = check_number(values.get("opacity", 30), MIN_OPACITY, 100, "a opacidade") / 100
    layer = check_choice(values.get("layer", "behind"), WATERMARK_LAYERS, "a camada")
    data = b""
    scale = 0.0
    if mode == "image":
        data = read_image(Path(str(values.get("path", ""))))
        scale = check_number(values.get("scale", 50), MIN_IMAGE_SCALE, 100, "o tamanho da imagem")
    sources: dict[tuple[float, float], pdf.Document] = {}
    hidden = []
    for number in selected:
        page = doc[number]
        size = (round(page.rect.width, 2), round(page.rect.height, 2))
        if size not in sources:
            sources[size] = (
                _text_source(*size, values) if mode == "text" else _image_source(*size, data, scale)
            )
        if values.get("replace", True):
            remove(doc, number, "watermark")
        before = _thumbnail(doc[number])
        _stamp(
            doc,
            number,
            sources[size],
            0,
            "watermark",
            overlay=layer == "front",
            opacity=opacity,
        )
        if not _changed(before, _thumbnail(doc[number])):
            hidden.append(number + 1)
    if len(hidden) == len(selected):
        raise OldSchoolPDFError(
            "A marca d'água ficou escondida atrás do conteúdo em todas as páginas, o que é "
            "comum em páginas digitalizadas. Escolha “Na frente do conteúdo”."
        )
    return selected[0], {
        "pages": len(selected),
        "hidden": hidden[:10],
        "hidden_count": len(hidden),
    }


def remove_stamps(doc: pdf.Document, values: dict) -> tuple[int, dict]:
    """Remove o cabeçalho, o rodapé ou a marca d'água que o programa gravou."""
    selected = indices(values["ranges"], doc.page_count)
    kinds = values.get("kinds")
    if not isinstance(kinds, list) or not kinds or any(kind not in STAMP_KINDS for kind in kinds):
        raise OldSchoolPDFError("Escolha o que remover.")
    removed = dict.fromkeys(kinds, 0)
    for number in selected:
        for kind in kinds:
            if remove(doc, number, kind):
                removed[kind] += 1
    if not any(removed.values()):
        raise OldSchoolPDFError(
            "Nenhum cabeçalho, rodapé ou marca d'água do Old School PDF foi encontrado nessas "
            "páginas. Marcas feitas por outros programas não podem ser removidas por aqui."
        )
    return selected[0], {"removed": removed}


def strip_watermarks(doc: pdf.Document) -> None:
    """Tira as marcas d'água do programa de um documento em memória (conversão para Word)."""
    for number in range(doc.page_count):
        remove(doc, number, "watermark")
