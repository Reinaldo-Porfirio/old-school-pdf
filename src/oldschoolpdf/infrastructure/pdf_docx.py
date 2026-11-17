"""Conversão local de PDF para documento do Word (.docx) com texto editável.

O resultado segue o fluxo do texto, como um documento digitado: parágrafos com
fonte, tamanho, negrito, itálico e cor; títulos com os estilos do Word; tabelas;
imagens; links; e uma quebra de página para cada página do PDF. Páginas com OCR
viram texto. Páginas digitalizadas sem OCR entram como imagem.
"""

import io
import re
import zipfile
from collections import Counter
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from statistics import median

import pymupdf as pdf
from docx import Document as WordDocument
from docx.enum.section import WD_ORIENT, WD_SECTION
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.image.exceptions import UnrecognizedImageError
from docx.opc.constants import RELATIONSHIP_TYPE
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt, RGBColor

from oldschoolpdf.domain.errors import OldSchoolPDFError
from oldschoolpdf.domain.text_editing import (
    clean_font_name,
    detect_alignment,
    font_family_key,
    is_bold_name,
    is_italic_name,
    line_joints,
)
from oldschoolpdf.infrastructure.system_fonts import ALIASES, system_fonts

Progress = Callable[[int, int, str], None]
TEXT_FLAGS = pdf.TEXT_PRESERVE_WHITESPACE | pdf.TEXT_MEDIABOX_CLIP
MAX_DOCX_BYTES = 512 * 1024**2
MAX_TABLE_ROWS = 500
MAX_TABLE_COLS = 40
MIN_IMAGE_POINTS = 12.0
FIGURE_DPI = 150
SCAN_SHARE = 0.8
HEADING_RATIO = 1.15
MAX_HEADING_CHARS = 150
SAMPLE_PAGES = 50
ALIGN = {
    "left": WD_ALIGN_PARAGRAPH.LEFT,
    "center": WD_ALIGN_PARAGRAPH.CENTER,
    "right": WD_ALIGN_PARAGRAPH.RIGHT,
    "justify": WD_ALIGN_PARAGRAPH.JUSTIFY,
}
BULLETS = "•◦▪▫‣⁃–-*·●○■□"
# Caracteres que o XML do Word não aceita.
INVALID_XML = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f\ufffe\uffff\ud800-\udfff]")


@dataclass
class Run:
    text: str
    font: str
    size: float
    bold: bool
    italic: bool
    color: int
    superscript: bool
    link: str = ""

    def same_style(self, other: "Run") -> bool:
        return (self.font, self.size, self.bold, self.italic, self.color, self.superscript,
                self.link) == (other.font, other.size, other.bold, other.italic, other.color,
                               other.superscript, other.link)  # fmt: skip


@dataclass
class Paragraph:
    runs: list[Run]
    align: str
    size: float
    left: float
    right: float
    first: float
    spacing: float
    top: float
    bottom: float


@dataclass
class Item:
    """Parágrafo, tabela ou imagem na ordem de leitura da página."""

    kind: str
    top: float
    paragraph: Paragraph | None = None
    rows: list[list[str]] = field(default_factory=list)
    table_size: float = 0.0
    image: bytes = b""
    width: float = 0.0


@dataclass
class PageContent:
    width: float
    height: float
    margins: tuple[float, float, float, float]
    items: list[Item]
    scanned: bool = False
    ocr: bool = False


def _clean(text: str) -> str:
    return INVALID_XML.sub("", text.replace("\u00a0", " "))


def family_name(font: str) -> str:
    """Nome de família para o Word: "ABCDEF+TimesNewRomanPS-BoldMT" vira "Times New Roman"."""
    key = font_family_key(font)
    key = ALIASES.get(key, key)
    found = system_fonts().get((key, False, False))
    if found:
        return found[1]
    base = re.split(r"[-,]", clean_font_name(font), maxsplit=1)[0]
    base = re.sub(r"(PSMT|MT|PS)$", "", base) or base
    return re.sub(r"(?<=[a-z])(?=[A-Z])", " ", base).strip() or "Arial"


def _hidden(page: pdf.Page) -> list[pdf.Rect]:
    """Áreas de texto invisível (a camada do OCR sobre a imagem digitalizada)."""
    return [
        pdf.Rect(trace["bbox"])
        for trace in page.get_texttrace()
        if trace.get("type") == 3 or trace.get("opacity", 1.0) == 0
    ]


def _center_in(rect: pdf.Rect, areas: list[pdf.Rect]) -> bool:
    x, y = (rect.x0 + rect.x1) / 2, (rect.y0 + rect.y1) / 2
    return any(area.x0 <= x <= area.x1 and area.y0 <= y <= area.y1 for area in areas)


def _links(page: pdf.Page) -> list[tuple[pdf.Rect, str]]:
    found = []
    for link in page.get_links():
        uri = link.get("uri") or ""
        if link.get("kind") == pdf.LINK_URI and re.match(r"(https?|mailto):", uri, re.I):
            found.append((pdf.Rect(link["from"]), uri[:2000]))
    return found


def _body_size(document: pdf.Document, pages: list[int]) -> float:
    sizes: Counter = Counter()
    for number in pages[:SAMPLE_PAGES]:
        for block in document[number].get_text("dict", flags=TEXT_FLAGS)["blocks"]:
            for line in block.get("lines", ()):
                for span in line["spans"]:
                    sizes[round(span["size"] * 2) / 2] += len(span["text"].strip())
    return sizes.most_common(1)[0][0] if sizes else 11.0


def _image_bytes(document: pdf.Document, page: pdf.Page, info: dict) -> bytes | None:
    """Imagem original quando possível; senão, a área da página renderizada."""
    xref = info.get("xref", 0)
    a, b, c, d = info["transform"][:4]
    upright = abs(b) < 1e-3 and abs(c) < 1e-3 and a > 0 and d > 0
    if xref and upright:
        try:
            image = document.extract_image(xref)
            # JPEG em CMYK pode sair com as cores invertidas no Word: vira PNG em RGB.
            plain = image and not image.get("smask") and image.get("colorspace", 3) <= 3
            if plain and image["ext"] in {"png", "jpeg"}:
                return image["image"]
            pixmap = pdf.Pixmap(document, xref)
            if pixmap.colorspace and pixmap.colorspace.n > 3:
                pixmap = pdf.Pixmap(pdf.csRGB, pixmap)
            if image and image.get("smask"):
                pixmap = pdf.Pixmap(pixmap, pdf.Pixmap(document, image["smask"]))
            if pixmap.width * pixmap.height <= 26_000_000:
                return pixmap.tobytes("png")
        except (RuntimeError, ValueError):
            pass
    # A posição da imagem vem sem a rotação da página, como a área de recorte.
    clip = pdf.Rect(info["bbox"]) & (page.rect * page.derotation_matrix)
    if clip.is_empty:
        return None
    return page.get_pixmap(clip=clip, dpi=FIGURE_DPI, alpha=False).tobytes("png")


def _paragraphs(
    block: dict, rotation: pdf.Matrix, links: list, hidden: list[pdf.Rect], column: float
) -> list[Paragraph]:
    lines = []
    for line in block["lines"]:
        spans = [span for span in line["spans"] if span["text"]]
        text = "".join(span["text"] for span in spans)
        if not text.strip():
            continue
        lines.append((pdf.Rect(line["bbox"]) * rotation, spans, text))
    if not lines:
        return []
    left = min(rect.x0 for rect, _, _ in lines)
    right = max(rect.x1 for rect, _, _ in lines)
    width = max(right - left, 1.0)
    fill = [rect.width / width for rect, _, _ in lines]
    joints = line_joints([text for _, _, text in lines], fill)
    # Linhas muito afastadas, ou que começam com marcador, abrem um parágrafo novo.
    heights = [rect.height for rect, _, _ in lines]
    typical = median(heights)
    for index in range(1, len(lines)):
        gap = lines[index][0].y0 - lines[index - 1][0].y1
        starts = lines[index][2].lstrip()[:1]
        # Linha anterior curta e a seguinte começando com maiúscula: fim de parágrafo
        # ou item de lista cujo marcador é um desenho, não texto.
        narrow = width < column * 0.6
        short = (fill[index - 1] < 0.6 or narrow) and (starts.isupper() or starts.isdigit())
        if gap > typical * 0.9 or short or (starts and starts in BULLETS and starts != "-"):
            joints[index - 1] = "\n"
    groups: list[list[int]] = [[0]]
    for index, joint in enumerate(joints, 1):
        if joint == "\n":
            groups.append([index])
        else:
            groups[-1].append(index)
    result = []
    for group in groups:
        runs: list[Run] = []
        sizes = []
        for position, index in enumerate(group):
            rect, spans, _text = lines[index]
            if position:
                joint = joints[index - 1]
                if joint == "-" and runs and runs[-1].text.endswith("-"):
                    runs[-1].text = runs[-1].text[:-1]
                elif runs and not runs[-1].text.endswith(" "):
                    runs[-1].text += " "
            for span in spans:
                box = pdf.Rect(span["bbox"]) * rotation
                name = span["font"]
                flags = span["flags"]
                link = next((uri for area, uri in links if _center_in(box, [area])), "")
                run = Run(
                    _clean(span["text"]),
                    family_name(name),
                    max(1.0, round(span["size"] * 2) / 2),
                    bool(flags & pdf.TEXT_FONT_BOLD) or is_bold_name(name),
                    bool(flags & pdf.TEXT_FONT_ITALIC) or is_italic_name(name),
                    span.get("color", 0) if not _center_in(box, hidden) else 0,
                    bool(flags & pdf.TEXT_FONT_SUPERSCRIPT),
                    link,
                )
                sizes.append(run.size)
                if not runs:
                    run.text = run.text.lstrip()
                if runs and runs[-1].same_style(run):
                    runs[-1].text += run.text
                elif run.text:
                    runs.append(run)
        if runs:
            runs[-1].text = runs[-1].text.rstrip()
        runs = [run for run in runs if run.text]
        if not runs:
            continue
        rects = [lines[index][0] for index in group]
        top, bottom = min(r.y0 for r in rects), max(r.y1 for r in rects)
        edges = [(r.x0, r.x1) for r in rects]
        align = detect_alignment(edges, left, right) if len(rects) > 1 else "left"
        size = median(sizes) if sizes else 11.0
        spacing = 1.0
        if len(rects) > 1:
            steps = [b.y0 - a.y0 for a, b in zip(rects, rects[1:], strict=False)]
            spacing = min(2.5, max(1.0, round(median(steps) / (size * 1.17) * 20) / 20))
        start = min(r.x0 for r in rects)
        indent = max(0.0, rects[0].x0 - start)
        result.append(
            Paragraph(
                runs,
                align,
                size,
                start,
                max(r.x1 for r in rects),
                indent if indent > 4 else 0.0,
                spacing,
                top,
                bottom,
            )
        )
    return result


def _tables(page: pdf.Page, rotation: pdf.Matrix) -> list[tuple[pdf.Rect, list[list[str]]]]:
    try:
        found = page.find_tables().tables
    except (RuntimeError, ValueError, ZeroDivisionError, IndexError):
        return []
    tables = []
    for table in found:
        rows = table.extract()
        if not rows or len(rows) < 2 or len(rows[0]) < 2:
            continue
        if len(rows) > MAX_TABLE_ROWS or len(rows[0]) > MAX_TABLE_COLS:
            continue
        cells = [[_clean(" ".join((cell or "").split())) for cell in row] for row in rows]
        if sum(bool(cell) for row in cells for cell in row) < 2:
            continue
        tables.append((pdf.Rect(table.bbox) * rotation, cells))
    return tables


def _read_page(document: pdf.Document, number: int, body: float, keep_scans: bool) -> PageContent:
    page = document[number]
    rotation = page.rotation_matrix
    view = page.rect
    hidden = _hidden(page)
    links = [(area * rotation, uri) for area, uri in _links(page)]
    tables = _tables(page, rotation)
    table_areas = [area for area, _ in tables]
    data = page.get_text("dict", flags=TEXT_FLAGS)
    items: list[Item] = []
    hidden_chars = visible_chars = 0
    # Largura da coluna de texto mais larga: referência para linhas curtas e listas.
    column = max(
        (
            (pdf.Rect(block["bbox"]) * rotation).width
            for block in data["blocks"]
            if block.get("type") == 0
        ),
        default=view.width,
    )
    for block in data["blocks"]:
        if block.get("type") != 0:
            continue
        kept_lines = []
        for line in block["lines"]:
            box = pdf.Rect(line["bbox"]) * rotation
            if _center_in(box, table_areas):
                continue
            count = sum(len(span["text"].strip()) for span in line["spans"])
            if _center_in(box, hidden):
                hidden_chars += count
            else:
                visible_chars += count
            kept_lines.append(line)
        if not kept_lines:
            continue
        for paragraph in _paragraphs({"lines": kept_lines}, rotation, links, hidden, column):
            items.append(Item("paragraph", paragraph.top, paragraph=paragraph))
    ocr = hidden_chars > max(20, visible_chars)
    text_items = len(items)
    page_area = view.width * view.height
    scanned = False
    for info in page.get_image_info(xrefs=True):
        box = pdf.Rect(info["bbox"]) * rotation & view
        if box.is_empty or min(box.width, box.height) < MIN_IMAGE_POINTS:
            continue
        cover = box.width * box.height / page_area
        if cover >= SCAN_SHARE and ocr and not keep_scans:
            continue
        if cover >= SCAN_SHARE and not text_items:
            scanned = True
        data_bytes = _image_bytes(document, page, info)
        if data_bytes:
            items.append(Item("image", box.y0, image=data_bytes, width=box.width))
    for area, rows in tables:
        sizes = [
            span["size"]
            for block in data["blocks"]
            if block.get("type") == 0
            for line in block["lines"]
            if _center_in(pdf.Rect(line["bbox"]) * rotation, [area])
            for span in line["spans"]
        ]
        items.append(
            Item(
                "table",
                area.y0,
                rows=rows,
                table_size=round(median(sizes) * 2) / 2 if sizes else body,
            )
        )
    # Texto na ordem do conteúdo; tabelas e imagens entram antes do primeiro
    # parágrafo que começa abaixo delas.
    ordered = [item for item in items if item.kind == "paragraph"]
    for item in sorted((i for i in items if i.kind != "paragraph"), key=lambda i: i.top):
        position = next(
            (index for index, other in enumerate(ordered) if other.top > item.top + 1),
            len(ordered),
        )
        ordered.insert(position, item)
    texts = [item.paragraph for item in ordered if item.paragraph]
    left = min((paragraph.left for paragraph in texts), default=72.0)
    right = view.width - max((paragraph.right for paragraph in texts), default=view.width - 72)
    margins = (
        min(max(left, 18.0), view.width / 3),
        36.0,
        min(max(right, 18.0), view.width / 3),
        36.0,
    )
    return PageContent(view.width, view.height, margins, ordered, scanned, ocr)


def _add_hyperlink(paragraph, run: Run, styled) -> None:
    """Envolve o trecho num link externo do Word."""
    part = paragraph.part
    relation = part.relate_to(run.link, RELATIONSHIP_TYPE.HYPERLINK, is_external=True)
    link = OxmlElement("w:hyperlink")
    link.set(qn("r:id"), relation)
    link.append(styled._r)
    paragraph._p.append(link)


def _style_run(target, run: Run) -> None:
    font = target.font
    font.name = run.font
    # Sem rFonts para East Asian, o Word pode trocar a fonte de caracteres acentuados.
    fonts = target._r.get_or_add_rPr().get_or_add_rFonts()
    fonts.set(qn("w:eastAsia"), run.font)
    font.size = Pt(run.size)
    font.bold = run.bold
    font.italic = run.italic
    if run.superscript:
        font.superscript = True
    if run.color:
        font.color.rgb = RGBColor((run.color >> 16) & 255, (run.color >> 8) & 255, run.color & 255)
    elif run.link:
        font.color.rgb = RGBColor(0x05, 0x63, 0xC1)
    if run.link:
        font.underline = True


def _heading_levels(pages: list[PageContent], body: float) -> dict[float, int]:
    sizes = {
        item.paragraph.size
        for content in pages
        for item in content.items
        if item.paragraph
        and item.paragraph.size >= body * HEADING_RATIO
        and len("".join(run.text for run in item.paragraph.runs)) <= MAX_HEADING_CHARS
    }
    return {size: index + 1 for index, size in enumerate(sorted(sizes, reverse=True)[:3])}


def _setup_section(section, content: PageContent) -> float:
    section.page_width = Pt(content.width)
    section.page_height = Pt(content.height)
    section.orientation = (
        WD_ORIENT.LANDSCAPE if content.width > content.height else WD_ORIENT.PORTRAIT
    )
    left, top, right, bottom = content.margins
    section.left_margin, section.top_margin = Pt(left), Pt(top)
    section.right_margin, section.bottom_margin = Pt(right), Pt(bottom)
    section.header_distance = section.footer_distance = Pt(18)
    return content.width - left - right


def _write(pages: list[PageContent], body: float, target: Path) -> dict:
    word = WordDocument()
    normal = word.styles["Normal"]
    normal.font.size = Pt(body)
    normal.paragraph_format.space_after = Pt(0)
    levels = _heading_levels(pages, body)
    totals = Counter()
    text_width = 0.0
    previous_size = None
    for index, content in enumerate(pages):
        size = (round(content.width), round(content.height))
        new_page = index > 0
        if index == 0:
            text_width = _setup_section(word.sections[0], content)
        elif size != previous_size:
            text_width = _setup_section(word.add_section(WD_SECTION.NEW_PAGE), content)
            new_page = False
        previous_size = size
        if not content.items:
            paragraph = word.add_paragraph()
            paragraph.paragraph_format.page_break_before = new_page
            continue
        for position, item in enumerate(content.items):
            first = position == 0 and new_page
            if item.kind == "table":
                if first:
                    word.add_paragraph().paragraph_format.page_break_before = True
                columns = max(len(row) for row in item.rows)
                table = word.add_table(rows=len(item.rows), cols=columns)
                table.style = "Table Grid"
                for row, values in zip(table.rows, item.rows, strict=True):
                    for cell, value in zip(row.cells, values, strict=False):
                        paragraph = cell.paragraphs[0]
                        run = paragraph.add_run(value)
                        run.font.size = Pt(max(6.0, item.table_size))
                totals["tables"] += 1
                continue
            paragraph = word.add_paragraph()
            paragraph.paragraph_format.page_break_before = first
            if item.kind == "image":
                width = min(item.width, text_width) if text_width > 0 else item.width
                try:
                    paragraph.add_run().add_picture(io.BytesIO(item.image), width=Pt(width))
                except (UnrecognizedImageError, ValueError, ZeroDivisionError, OSError):
                    totals["skipped_images"] += 1
                    continue
                totals["images"] += 1
                continue
            data = item.paragraph
            text = "".join(run.text for run in data.runs)
            level = levels.get(data.size) if len(text) <= MAX_HEADING_CHARS else None
            if level:
                paragraph.style = word.styles[f"Heading {level}"]
                totals["headings"] += 1
            fmt = paragraph.paragraph_format
            fmt.alignment = ALIGN.get(data.align, WD_ALIGN_PARAGRAPH.LEFT)
            indent = data.left - content.margins[0]
            if indent > 4:
                fmt.left_indent = Pt(min(indent, max(0.0, text_width - 36)))
            if data.first:
                fmt.first_line_indent = Pt(min(data.first, 144))
            fmt.line_spacing = data.spacing
            following = content.items[position + 1] if position + 1 < len(content.items) else None
            gap = following.top - data.bottom if following else 0
            fmt.space_after = Pt(min(24.0, max(0.0, round(gap))))
            fmt.space_before = Pt(0)
            for run in data.runs:
                styled = paragraph.add_run(run.text)
                _style_run(styled, run)
                if run.link:
                    _add_hyperlink(paragraph, run, styled)
            totals["paragraphs"] += 1
    # O modelo do python-docx traz datas e autor próprios; ficam só a data da conversão.
    now = datetime.now(UTC).replace(microsecond=0, tzinfo=None)
    properties = word.core_properties
    properties.author = properties.last_modified_by = ""
    properties.created = properties.modified = now
    properties.comments = "Convertido pelo Old School PDF"
    with target.open("xb") as output:
        word.save(output)
    return totals


def _validate(target: Path, expected: dict) -> None:
    size = target.stat().st_size
    if not 0 < size <= MAX_DOCX_BYTES:
        raise OldSchoolPDFError("O documento do Word ficou vazio ou grande demais.")
    try:
        with zipfile.ZipFile(target) as archive:
            if archive.testzip() is not None:
                raise OldSchoolPDFError("O documento do Word gravado está corrompido.")
        reopened = WordDocument(str(target))
    except (zipfile.BadZipFile, KeyError, ValueError):
        raise OldSchoolPDFError("O documento do Word gravado não pôde ser reaberto.") from None
    if len(reopened.tables) != expected.get("tables", 0):
        raise OldSchoolPDFError("A conferência do documento do Word não encontrou as tabelas.")


def pdf_to_docx(
    document: pdf.Document,
    pages: list[int],
    target: Path,
    progress: Progress,
    *,
    keep_scans: bool = False,
) -> str:
    """Converte as páginas escolhidas e confere o arquivo gravado."""
    # O módulo opcional de layout (modelo de IA) deixaria as tabelas lentas e diferentes.
    with suppress(NotImplementedError):
        pdf.use_layout(False)
    body = _body_size(document, pages)
    contents = []
    for index, number in enumerate(pages):
        progress(index, len(pages) + 1, f"Lendo a página {number + 1}")
        contents.append(_read_page(document, number, body, keep_scans))
    if not any(content.items for content in contents):
        raise OldSchoolPDFError("As páginas escolhidas não têm texto nem imagens para converter.")
    progress(len(pages), len(pages) + 1, "Gravando e conferindo o documento do Word")
    totals = _write(contents, body, target)
    _validate(target, totals)
    detail = (
        f"{len(pages)} página(s) · {totals['paragraphs']} parágrafo(s) · "
        f"{totals['tables']} tabela(s) · {totals['images']} imagem(ns)"
    )
    scanned = sum(content.scanned for content in contents)
    ocr = sum(content.ocr for content in contents)
    if ocr:
        detail += f" · texto do OCR usado em {ocr} página(s)"
    if scanned:
        detail += (
            f" · {scanned} página(s) digitalizada(s) entraram como imagem: "
            "use Reconhecer texto antes para ter texto editável"
        )
    if totals["skipped_images"]:
        detail += (
            f" · {totals['skipped_images']} imagem(ns) em formato incompatível ficaram de fora"
        )
    return detail
