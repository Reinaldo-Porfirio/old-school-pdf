"""Edição do texto original de uma página do PDF.

O fluxo nunca reescreve o conteúdo da página por dentro. Ele:
1. apaga, com redação, só a faixa central de cada trecho do bloco (sem pintar nada);
2. confere que o bloco sumiu e que nenhum texto vizinho foi afetado;
3. escreve o texto novo numa página temporária idêntica, reduz as fontes novas a um
   subconjunto e a sobrepõe à página real, sem tocar nas fontes que já existiam;
4. confere o texto gravado, os pixels fora da área editada, os links e as anotações.
Qualquer divergência interrompe a edição sem gravar a revisão.
"""

import hashlib
from collections import Counter
from dataclasses import asdict, replace
from html import escape

import pymupdf

from oldschoolpdf.domain.errors import OldSchoolPDFError
from oldschoolpdf.domain.text_editing import (
    ALIGNMENTS,
    MAX_BLOCK_CHARS,
    MAX_EDIT_BLOCKS,
    MAX_PAGE_BLOCKS,
    SHRINK_LIMITS,
    TextBlock,
    TextRun,
    TextStyle,
    clean_font_name,
    compare_form,
    css_color,
    detect_alignment,
    is_bold_name,
    is_italic_name,
    line_joints,
    validate_text,
)
from oldschoolpdf.infrastructure.pdf_editing import normalized_rect
from oldschoolpdf.infrastructure.system_fonts import FontChoice, resolve_font

TEXT_FLAGS = pymupdf.TEXT_PRESERVE_WHITESPACE | pymupdf.TEXT_MEDIABOX_CLIP
# Faixa apagada em cada trecho, em frações do tamanho da fonte acima da linha de base:
# atinge as letras do trecho sem alcançar as linhas vizinhas.
BAND_TOP = 0.45
BAND_BOTTOM = 0.25
CHECK_SCALE = 0.75
PIXEL_MARGIN = 2.5
PIXEL_THRESHOLD = 48
PIXEL_TOLERANCE = 0.0008
EXPAND_MARGIN = 18.0
SAMPLE_SCALE = 3.0
# Distâncias entre cores RGB (0 a 441) usadas para decidir se o texto aparece no fundo.
SAME_COLOR = 40.0
VISIBLE_INK = 60.0
BLEND_GAP = 60.0
PLAIN_BACKGROUND = 0.6


def _rgb(value: int) -> tuple[int, int, int]:
    return (value >> 16) & 0xFF, (value >> 8) & 0xFF, value & 0xFF


def _distance(first: int, second: int) -> float:
    return sum((a - b) ** 2 for a, b in zip(_rgb(first), _rgb(second), strict=True)) ** 0.5


def _sample(page: pymupdf.Page, rect: pymupdf.Rect) -> tuple[int, int, float] | None:
    """Cor do fundo (a mais comum), da tinta (a mais distante do fundo) e quanto da
    área é fundo liso (0 a 1)."""
    clip = (rect * page.rotation_matrix) & page.rect
    if clip.is_empty or clip.width < 1 or clip.height < 1:
        return None
    matrix = pymupdf.Matrix(SAMPLE_SCALE, SAMPLE_SCALE)
    pixmap = page.get_pixmap(matrix=matrix, clip=clip, colorspace=pymupdf.csRGB, alpha=False)
    samples = pixmap.samples
    colors = Counter(
        (samples[index] << 16) | (samples[index + 1] << 8) | samples[index + 2]
        for index in range(0, len(samples), 3)
    )
    if not colors:
        return None
    background, count = colors.most_common(1)[0]
    ink = max(colors, key=lambda color: _distance(color, background))
    return background, ink, count / sum(colors.values())


def _blend_gap(ink: int, background: int, reported: int) -> float:
    """Distância da tinta até a mistura fundo→cor informada (a suavização das bordas)."""
    base, target, point = _rgb(background), _rgb(reported), _rgb(ink)
    direction = [b - a for a, b in zip(base, target, strict=True)]
    length = sum(value * value for value in direction)
    if not length:
        return _distance(ink, background)
    step = sum((p - a) * d for p, a, d in zip(point, base, direction, strict=True)) / length
    step = min(max(step, 0.0), 1.0)
    closest = [a + step * d for a, d in zip(base, direction, strict=True)]
    return sum((p - c) ** 2 for p, c in zip(point, closest, strict=True)) ** 0.5


def _visible_color(page: pymupdf.Page, span: dict, reported: int) -> int:
    """Cor que aparece de fato na tela.

    Alguns geradores pintam o texto com padrões de preenchimento e o motor informa
    outra cor (até igual à do fundo, o que deixaria o texto novo invisível). A cor
    medida na imagem só substitui a informada quando o fundo é liso, a tinta é
    visível e ela não pode ser explicada como mistura do fundo com a cor informada.
    """
    measured = _sample(page, pymupdf.Rect(span["bbox"]))
    if measured is None:
        return reported
    background, ink, plain = measured
    if _distance(ink, background) < VISIBLE_INK or plain < PLAIN_BACKGROUND:
        return reported
    if _distance(reported, background) < SAME_COLOR:
        return ink
    if _blend_gap(ink, background, reported) > BLEND_GAP:
        return ink
    return reported


def _style(span: dict) -> TextStyle:
    flags = span.get("flags", 0)
    font = span.get("font", "")
    return TextStyle(
        font=clean_font_name(font),
        size=round(float(span.get("size", 11.0)), 2),
        color=int(span.get("color", 0)) & 0xFFFFFF,
        bold=bool(flags & pymupdf.TEXT_FONT_BOLD) or is_bold_name(font),
        italic=bool(flags & pymupdf.TEXT_FONT_ITALIC) or is_italic_name(font),
        serif=bool(flags & pymupdf.TEXT_FONT_SERIFED),
        mono=bool(flags & pymupdf.TEXT_FONT_MONOSPACED),
    )


def _span_text(span: dict) -> str:
    # O motor grava espaços como não separáveis; para quem edita, são espaços comuns.
    return span["text"].replace(" ", " ")


def _line_text(line: dict) -> str:
    return "".join(_span_text(span) for span in line["spans"])


def _horizontal(line: dict) -> bool:
    dx, dy = line.get("dir", (1.0, 0.0))
    return abs(dx - 1.0) < 1e-3 and abs(dy) < 1e-3


def _hidden_regions(page: pymupdf.Page) -> list[pymupdf.Rect]:
    regions = []
    for trace in page.get_texttrace():
        if trace.get("type") == 3 or trace.get("opacity", 1.0) == 0:
            regions.append(pymupdf.Rect(trace["bbox"]))
    return regions


def _scan(page: pymupdf.Page) -> tuple[list[TextBlock], dict[str, list[dict]]]:
    """Blocos de texto da página e, por chave, os trechos brutos usados na remoção."""
    data = page.get_text("dict", flags=TEXT_FLAGS)
    hidden = _hidden_regions(page)
    widgets = [pymupdf.Rect(widget.rect) for widget in page.widgets()]
    blocks: list[TextBlock] = []
    spans_by_key: dict[str, list[dict]] = {}
    colors: dict[TextStyle, int] = {}
    for raw in data["blocks"]:
        if raw.get("type") != 0:
            continue
        lines = [line for line in raw.get("lines", []) if _line_text(line).strip()]
        if not lines:
            continue
        bbox = pymupdf.Rect(lines[0]["bbox"])
        for line in lines[1:]:
            bbox |= pymupdf.Rect(line["bbox"])
        width = max(bbox.width, 1.0)
        texts = [_line_text(line) for line in lines]
        fill = [pymupdf.Rect(line["bbox"]).width / width for line in lines]
        joints = line_joints(texts, fill)
        styles: list[TextStyle] = []
        runs: list[TextRun] = []
        for index, line in enumerate(lines):
            line_runs: list[TextRun] = []
            for span in line["spans"]:
                if not span["text"]:
                    continue
                style = _style(span)
                if style not in colors:
                    colors[style] = _visible_color(page, span, style.color)
                style = replace(style, color=colors[style])
                if style not in styles:
                    styles.append(style)
                run = TextRun(_span_text(span), styles.index(style), style.bold, style.italic)
                if line_runs and line_runs[-1].style == run.style:
                    previous = line_runs.pop()
                    run = TextRun(previous.text + run.text, run.style, run.bold, run.italic)
                line_runs.append(run)
            if index == 0:
                line_runs[0] = TextRun(line_runs[0].text.lstrip(), *_tail(line_runs[0]))
            else:
                joint = joints[index - 1]
                last = runs[-1]
                text = last.text.rstrip()
                text = text[:-1] if joint == "-" else text + joint
                runs[-1] = TextRun(text, *_tail(last))
                line_runs[0] = TextRun(line_runs[0].text.lstrip(), *_tail(line_runs[0]))
            runs.extend(line_runs)
        runs[-1] = TextRun(runs[-1].text.rstrip(), *_tail(runs[-1]))
        runs = [run for run in runs if run.text]
        text = "".join(run.text for run in runs)
        key = hashlib.sha1(f"{[round(value, 1) for value in bbox]}|{text}".encode()).hexdigest()[
            :16
        ]
        reason = ""
        if not all(_horizontal(line) for line in lines):
            reason = "Texto girado ou vertical."
        elif any(region.intersects(bbox) for region in hidden):
            reason = "Camada de texto invisível, como a criada pelo OCR."
        elif any(region.intersects(bbox) for region in widgets):
            reason = "Texto sobre campo de formulário. Use Preencher formulário."
        elif len(text) > MAX_BLOCK_CHARS:
            reason = f"Bloco com mais de {MAX_BLOCK_CHARS} caracteres."
        heights = [
            pymupdf.Rect(b["bbox"]).y0 - pymupdf.Rect(a["bbox"]).y0
            for a, b in zip(lines, lines[1:], strict=False)
        ]
        size = max(style.size for style in styles) or 11.0
        spacing = sorted(heights)[len(heights) // 2] / size if heights else 1.2
        blocks.append(
            TextBlock(
                key=key,
                bbox=tuple(round(value, 3) for value in bbox),
                region=normalized_rect(page, bbox),
                text=text,
                runs=tuple(runs),
                styles=tuple(styles),
                align=detect_alignment(
                    [
                        (pymupdf.Rect(line["bbox"]).x0, pymupdf.Rect(line["bbox"]).x1)
                        for line in lines
                    ],
                    bbox.x0,
                    bbox.x1,
                ),
                line_height=round(min(max(spacing, 1.0), 2.5), 3),
                editable=not reason,
                reason=reason,
            )
        )
        spans_by_key[key] = [span for line in lines for span in line["spans"] if span["text"]]
        if len(blocks) >= MAX_PAGE_BLOCKS:
            break
    return blocks, spans_by_key


def _tail(run: TextRun) -> tuple[int, bool, bool]:
    return run.style, run.bold, run.italic


def read_blocks(page: pymupdf.Page) -> list[dict]:
    blocks, _ = _scan(page)
    return [asdict(block) for block in blocks]


def _words(page: pymupdf.Page) -> list[tuple]:
    return [
        (word[4], *(round(value * 2) / 2 for value in word[:4]))
        for word in page.get_text("words", flags=TEXT_FLAGS)
    ]


def _center_inside(word: tuple, rects: list[pymupdf.Rect]) -> bool:
    x = (word[1] + word[3]) / 2
    y = (word[2] + word[4]) / 2
    return any(
        rect.x0 - 0.5 <= x <= rect.x1 + 0.5 and rect.y0 - 0.5 <= y <= rect.y1 + 0.5
        for rect in rects
    )


def _written_text(page: pymupdf.Page, rect: pymupdf.Rect) -> str:
    words = page.get_text("words", flags=TEXT_FLAGS, sort=True)
    return " ".join(
        word[4]
        for word in words
        if rect.x0 - 1 <= (word[0] + word[2]) / 2 <= rect.x1 + 1
        and rect.y0 - 1 <= (word[1] + word[3]) / 2 <= rect.y1 + 1
    )


def _snapshot(page: pymupdf.Page) -> pymupdf.Pixmap:
    matrix = pymupdf.Matrix(CHECK_SCALE, CHECK_SCALE)
    return page.get_pixmap(matrix=matrix, colorspace=pymupdf.csRGB, alpha=False, annots=True)


def _pixels_changed(
    before: pymupdf.Pixmap, after: pymupdf.Pixmap, regions: list[pymupdf.Rect]
) -> bool:
    if (before.width, before.height) != (after.width, after.height):
        return True
    scale = pymupdf.Matrix(CHECK_SCALE, CHECK_SCALE)
    for region in regions:
        area = (region + (-PIXEL_MARGIN, -PIXEL_MARGIN, PIXEL_MARGIN, PIXEL_MARGIN)) * scale
        box = area.irect & before.irect
        if not box.is_empty:
            before.set_rect(box, (255, 255, 255))
            after.set_rect(box, (255, 255, 255))
    if before.samples == after.samples:
        return False
    first, second = before.samples, after.samples
    changed = sum(
        1
        for index in range(0, len(first), 3)
        if max(abs(first[index + channel] - second[index + channel]) for channel in range(3))
        > PIXEL_THRESHOLD
    )
    return changed > PIXEL_TOLERANCE * before.width * before.height


def _html(runs: list[TextRun], styles: tuple[TextStyle, ...], fonts: dict) -> str:
    paragraphs: list[str] = []
    current: list[str] = []

    def close() -> None:
        paragraphs.append("<p>" + ("".join(current) or "<br/>") + "</p>")
        current.clear()

    for run in runs:
        style = styles[run.style]
        choice: FontChoice = fonts[(run.style, run.bold, run.italic)]
        css = (
            f"font-family:'{choice.css}';font-size:{style.size:.2f}px;"
            f"color:{css_color(style.color)};"
            f"font-weight:{'bold' if run.bold else 'normal'};"
            f"font-style:{'italic' if run.italic else 'normal'}"
        )
        parts = run.text.split("\n")
        for index, part in enumerate(parts):
            if index:
                close()
            if part:
                text = escape(part).replace("  ", "  ")
                current.append(f'<span style="{css}">{text}</span>')
    close()
    return "".join(paragraphs)


def _stamp(
    page: pymupdf.Page,
    rect: pymupdf.Rect,
    html: str,
    css: str,
    archive: pymupdf.Archive,
    scale_low: float,
) -> tuple[float, float]:
    """Escreve numa página gêmea, reduz as fontes novas e sobrepõe à página real."""
    with pymupdf.open() as twin:
        twin_page = twin.new_page(width=page.mediabox.width, height=page.mediabox.height)
        twin_page.set_mediabox(page.mediabox)
        twin_page.set_cropbox(page.cropbox)
        spare, scale = twin_page.insert_htmlbox(
            rect, html, css=css, archive=archive, scale_low=scale_low
        )
        if spare < 0:
            return spare, scale
        twin.subset_fonts()
        data = twin.tobytes(garbage=3, deflate=True)
    with pymupdf.open("pdf", data) as stamp:
        page.show_pdf_page(page.rect, stamp, 0)
    return spare, scale


def _obstacles(page: pymupdf.Page, rect: pymupdf.Rect, edited: list[pymupdf.Rect]) -> float:
    """Até onde o bloco pode crescer para baixo sem encostar em outro conteúdo."""
    limit = page.rect.y1 - EXPAND_MARGIN
    candidates = [pymupdf.Rect(block[:4]) for block in page.get_text("blocks", flags=TEXT_FLAGS)]
    candidates += [pymupdf.Rect(item["bbox"]) for item in page.get_image_info()]
    for drawing in page.get_drawings():
        area = pymupdf.Rect(drawing["rect"])
        # Fundos que ocupam a página inteira não são obstáculos.
        if area.height < page.rect.height * 0.6:
            candidates.append(area)
    for other in candidates:
        if any(other.intersects(region) for region in edited):
            continue
        if other.x1 <= rect.x0 or other.x0 >= rect.x1:
            continue
        if other.y0 >= rect.y1 - 0.5:
            limit = min(limit, other.y0 - 2.0)
    return limit


def _check_options(options: dict) -> tuple[float, bool, bool]:
    shrink = options.get("shrink", "light")
    if shrink not in SHRINK_LIMITS:
        raise OldSchoolPDFError("Opção de redução inválida.")
    return (
        SHRINK_LIMITS[shrink],
        bool(options.get("expand", False)),
        bool(options.get("system_fonts", True)),
    )


def _parse_runs(raw_runs, styles: tuple[TextStyle, ...]) -> list[TextRun]:
    if not isinstance(raw_runs, list) or len(raw_runs) > MAX_BLOCK_CHARS:
        raise OldSchoolPDFError("O texto editado chegou em formato inválido.")
    runs = []
    for raw in raw_runs:
        try:
            run = TextRun(
                str(raw["text"]), int(raw["style"]), bool(raw["bold"]), bool(raw["italic"])
            )
        except (KeyError, TypeError, ValueError):
            raise OldSchoolPDFError("O texto editado chegou em formato inválido.") from None
        if not 0 <= run.style < len(styles):
            raise OldSchoolPDFError("O texto editado usa um estilo desconhecido.")
        runs.append(run)
    text = validate_text("".join(run.text for run in runs))
    if text != "".join(run.text for run in runs):
        runs = [TextRun(validate_text(run.text), *_tail(run)) for run in runs]
    return runs


def replace_blocks(doc: pymupdf.Document, number: int, edits: list, options: dict) -> dict:
    """Troca o texto dos blocos pedidos e devolve um relatório do que foi feito.

    Altera `doc` em memória. Em caso de erro, `doc` pode ficar pela metade: por isso o
    motor sempre chama esta função numa cópia descartável da revisão e só grava uma
    revisão nova quando todas as verificações passam.
    """
    if not isinstance(edits, list) or not 1 <= len(edits) <= MAX_EDIT_BLOCKS:
        raise OldSchoolPDFError(f"Edite de 1 a {MAX_EDIT_BLOCKS} blocos por vez.")
    page = doc[number]
    original_rotation = page.rotation
    # Com a página a 0°, extração, remoção e escrita usam o mesmo sistema de coordenadas.
    page.set_rotation(0)
    try:
        return _replace(page, edits, options)
    finally:
        page.set_rotation(original_rotation)


def _annotations(page: pymupdf.Page) -> list[tuple[int, int]]:
    """Anotações e links lidos do dicionário da página, sem cache do objeto Page."""
    return [(xref, kind) for xref, kind, _ in page.annot_xrefs()]


def _reattach(page: pymupdf.Page, xrefs: list[int]) -> None:
    """Devolve à página links que a redação desanexou; os objetos continuam intactos."""
    doc = page.parent
    references = " ".join(f"{xref} 0 R" for xref in xrefs)
    kind, value = doc.xref_get_key(page.xref, "Annots")
    if kind == "xref":
        holder = int(value.split()[0])
        array = doc.xref_object(holder, compressed=True).strip()
        doc.update_object(holder, array[:-1] + " " + references + "]")
    elif kind == "array":
        doc.xref_set_key(page.xref, "Annots", value.strip()[:-1] + " " + references + "]")
    else:
        doc.xref_set_key(page.xref, "Annots", "[" + references + "]")


def _replace(page: pymupdf.Page, edits: list, options: dict) -> dict:
    scale_low, expand, use_system = _check_options(options)
    blocks, spans_by_key = _scan(page)
    by_key = {block.key: block for block in blocks}
    targets: list[tuple[TextBlock, list[TextRun]]] = []
    for edit in edits:
        block = by_key.get(edit.get("key") if isinstance(edit, dict) else None)
        if block is None:
            raise OldSchoolPDFError(
                "O texto da página mudou desde a leitura. Abra o editor de texto novamente."
            )
        if not block.editable:
            raise OldSchoolPDFError(block.reason)
        if any(block is target for target, _ in targets):
            raise OldSchoolPDFError("O mesmo bloco foi enviado duas vezes.")
        targets.append((block, _parse_runs(edit.get("runs"), block.styles)))
    target_rects = [pymupdf.Rect(block.bbox) for block, _ in targets]
    words_before = _words(page)
    target_keys = {block.key for block, _ in targets}
    for other in blocks:
        if other.key not in target_keys and any(
            pymupdf.Rect(other.bbox).intersects(rect) for rect in target_rects
        ):
            raise OldSchoolPDFError(
                "O bloco escolhido se sobrepõe a outro texto da página e não pode ser editado "
                "com segurança."
            )
    neighbours = Counter(word for word in words_before if not _center_inside(word, target_rects))
    pixels_before = _snapshot(page)
    annotations_before = _annotations(page)

    # 1. Remoção pela faixa central de cada trecho.
    for block, _ in targets:
        for span in spans_by_key[block.key]:
            box = pymupdf.Rect(span["bbox"])
            baseline = span["origin"][1]
            size = span["size"]
            page.add_redact_annot(
                pymupdf.Rect(
                    box.x0, baseline - BAND_TOP * size, box.x1, baseline - BAND_BOTTOM * size
                ),
                fill=False,
                cross_out=False,
            )
    page.apply_redactions(
        images=pymupdf.PDF_REDACT_IMAGE_NONE,
        graphics=pymupdf.PDF_REDACT_LINE_ART_NONE,
        text=pymupdf.PDF_REDACT_TEXT_REMOVE,
    )
    present = {xref for xref, _ in _annotations(page)}
    detached = [
        xref
        for xref, kind in annotations_before
        if kind == pymupdf.PDF_ANNOT_LINK and xref not in present
    ]
    if detached:
        _reattach(page, detached)

    # 2. O bloco sumiu por inteiro e os vizinhos continuam intactos?
    remaining = Counter(_words(page))
    if neighbours - remaining:
        raise OldSchoolPDFError(
            "A remoção afetaria um texto vizinho. Por segurança, nada foi alterado."
        )
    if remaining - neighbours:
        raise OldSchoolPDFError(
            "Parte do texto original não pôde ser removida com segurança. Nada foi alterado."
        )

    # 3. Escrita do texto novo.
    archive = pymupdf.Archive()
    archived: set[str] = set()
    report_fonts: dict[str, bool] = {}
    written: list[tuple[pymupdf.Rect, str]] = []
    smallest = 1.0
    expanded = 0
    for block, runs in targets:
        text = "".join(run.text for run in runs)
        if not text.strip():
            continue
        fonts = {}
        faces = []
        for run in runs:
            key = (run.style, run.bold, run.italic)
            if key in fonts:
                continue
            choice = resolve_font(
                block.styles[run.style], run.bold, run.italic, use_system=use_system
            )
            fonts[key] = choice
            report_fonts[choice.label] = report_fonts.get(choice.label, True) and choice.exact
            if choice.path:
                name = choice.css + ".font"
                if name not in archived:
                    with open(choice.path, "rb") as stream:
                        archive.add(stream.read(), name)
                    archived.add(name)
                faces.append(f"@font-face{{font-family:'{choice.css}';src:url({name});}}")
        align = block.align if block.align in ALIGNMENTS else "left"
        css = "".join(dict.fromkeys(faces)) + (
            f"p{{margin:0;}} body{{margin:0;text-align:{align};line-height:{block.line_height};}}"
        )
        html = _html(runs, block.styles, fonts)
        rect = pymupdf.Rect(block.bbox)
        spare, scale = _stamp(page, rect, html, css, archive, scale_low)
        if spare < 0 and expand:
            limit = _obstacles(page, rect, target_rects)
            if limit > rect.y1 + 1:
                rect = pymupdf.Rect(rect.x0, rect.y0, rect.x1, limit)
                spare, scale = _stamp(page, rect, html, css, archive, scale_low)
                expanded += spare >= 0
        if spare < 0:
            raise OldSchoolPDFError(
                "O texto novo não cabe no espaço do bloco, mesmo reduzindo a fonte. "
                "Encurte o texto ou permita reduzir mais e expandir para baixo."
            )
        smallest = min(smallest, scale)
        written.append((rect, text))

    # 4. Verificações finais.
    if sorted(_annotations(page)) != sorted(annotations_before):
        raise OldSchoolPDFError(
            "A edição alteraria os links ou as anotações da página. Nada foi alterado."
        )
    new_rects = [rect for rect, _ in written]
    final_words = Counter(word for word in _words(page) if not _center_inside(word, new_rects))
    if final_words != neighbours:
        raise OldSchoolPDFError(
            "A verificação encontrou texto alterado fora da área editada. Nada foi alterado."
        )
    for rect, text in written:
        if compare_form(_written_text(page, rect)) != compare_form(text):
            raise OldSchoolPDFError(
                "O texto gravado não conferiu com o digitado. A fonte pode não ter algum "
                "caractere. Nada foi alterado."
            )
    for rect, _ in written:
        measured = _sample(page, rect)
        if measured is None or _distance(measured[0], measured[1]) < VISIBLE_INK / 2:
            raise OldSchoolPDFError(
                "O texto novo ficaria invisível sobre o fundo. Nada foi alterado."
            )
    if _pixels_changed(pixels_before, _snapshot(page), target_rects + new_rects):
        raise OldSchoolPDFError(
            "A verificação visual encontrou mudanças fora da área editada. Nada foi alterado."
        )
    return {
        "blocks": len(targets),
        "fonts": [{"label": label, "exact": exact} for label, exact in report_fonts.items()],
        "scale": round(smallest, 3),
        "expanded": expanded,
        "links_restored": len(detached),
    }
