"""Motor de edição de texto testado direto no PyMuPDF, sem interface."""

from dataclasses import asdict
from pathlib import Path

import pymupdf
import pytest

from oldschoolpdf.domain.errors import OldSchoolPDFError
from oldschoolpdf.domain.text_editing import TextRun
from oldschoolpdf.infrastructure.pdf_engine import PdfEngine
from oldschoolpdf.infrastructure.pdf_text_edit import read_blocks, replace_blocks

TIMES = Path(r"C:\Windows\Fonts\times.ttf")


def page_text(page):
    return " ".join(page.get_text().split())


def find(blocks, fragment):
    return next(block for block in blocks if fragment in block["text"])


def edit_of(block, text, *, bold=None):
    first = block["runs"][0]
    return {
        "key": block["key"],
        "runs": [
            {
                "text": text,
                "style": first["style"],
                "bold": first["bold"] if bold is None else bold,
                "italic": first["italic"],
            }
        ],
    }


def keep_runs(block, replace):
    """Mantém trechos e estilos, trocando uma palavra no texto."""
    runs = []
    for run in block["runs"]:
        run = dict(run)
        run["text"] = run["text"].replace(*replace)
        runs.append(run)
    return {"key": block["key"], "runs": runs}


@pytest.fixture
def document():
    doc = pymupdf.open()
    page = doc.new_page(width=420, height=600)
    page.insert_text((40, 60), "Título do relatório", fontsize=16)
    lines = ["Primeira linha do parágrafo", "Segunda linha do parágrafo", "Terceira linha final."]
    for index, line in enumerate(lines):
        page.insert_text((40, 100 + 13 * index), line, fontsize=12)
    page.insert_text((40, 300), "Bloco vizinho que não pode mudar", fontsize=12)
    yield doc
    doc.close()


def test_reads_blocks_with_text_styles_and_alignment(document):
    blocks = read_blocks(document[0])
    paragraph = find(blocks, "Primeira")
    assert paragraph["text"] == (
        "Primeira linha do parágrafo Segunda linha do parágrafo Terceira linha final."
    )
    assert paragraph["editable"] and paragraph["align"] == "left"
    assert paragraph["styles"][0]["size"] == 12
    assert 1.0 <= paragraph["line_height"] <= 1.2
    assert all(0 <= value <= 1 for value in paragraph["region"])


def test_replaces_paragraph_and_keeps_neighbours_exact(document):
    page = document[0]
    blocks = read_blocks(page)
    target = find(blocks, "Primeira")
    report = replace_blocks(document, 0, [edit_of(target, "Texto novo com ação e €.")], {})
    text = page_text(page)
    assert "Texto novo com ação e €." in text
    assert "Primeira linha" not in text
    assert "Título do relatório" in text and "Bloco vizinho que não pode mudar" in text
    assert report["blocks"] == 1 and report["scale"] == 1


def test_tight_leading_neighbour_line_survives(document):
    page = document[0]
    page.insert_text((40, 320), "Linha colada logo abaixo", fontsize=12)
    target = find(read_blocks(page), "Bloco vizinho")
    replace_blocks(document, 0, [edit_of(target, "Trocado")], {})
    assert "Linha colada logo abaixo" in page_text(page)


@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
@pytest.mark.parametrize("crop", [None, (30, 20, 380, 560)])
def test_rotated_and_cropped_pages_write_in_place(rotation, crop):
    with pymupdf.open() as doc:
        page = doc.new_page(width=420, height=600)
        page.insert_text((60, 140), "Alvo da edição", fontsize=12)
        page.insert_text((60, 400), "Fixo", fontsize=12)
        if crop:
            page.set_cropbox(pymupdf.Rect(crop))
        page.set_rotation(rotation)
        target = find(read_blocks(page), "Alvo")
        before = pymupdf.Rect(target["bbox"])
        replace_blocks(doc, 0, [edit_of(target, "Novo")], {})
        assert page.rotation == rotation
        written = find(read_blocks(page), "Novo")
        after = pymupdf.Rect(written["bbox"])
        assert abs(after.x0 - before.x0) < 2 and abs(after.y0 - before.y0) < 3
        assert "Fixo" in page_text(page)


def test_overflow_is_refused_then_widens_or_expands(document):
    page = document[0]
    target = find(read_blocks(page), "Título")
    huge = "Título do relatório anual da equipe de vendas, marketing e operações regionais"
    # A recusa acontece numa cópia, como faz o motor; o documento original não muda.
    with (
        pymupdf.open("pdf", document.tobytes()) as copy,
        pytest.raises(OldSchoolPDFError, match="não cabe"),
    ):
        replace_blocks(copy, 0, [edit_of(target, huge)], {"shrink": "none"})
    assert "Título do relatório" in page_text(page)
    # Uma linha um pouco maior usa a largura livre ao lado, sem reduzir a fonte.
    longer = "Título do relatório anual da equipe"
    report = replace_blocks(document, 0, [edit_of(target, longer)], {"shrink": "none"})
    assert report["widened"] == 1 and report["expanded"] == 0 and report["scale"] == 1.0
    assert longer in page_text(page)
    paragraph = find(read_blocks(page), "Primeira")
    text = paragraph["text"] + " " + "Mais uma frase acrescentada ao parágrafo. " * 4
    report = replace_blocks(document, 0, [edit_of(paragraph, text)], {"expand": True})
    assert report["expanded"] == 1 and report["scale"] == 1.0
    assert "Bloco vizinho que não pode mudar" in page_text(page)


def test_expansion_stops_at_the_next_block(document):
    page = document[0]
    target = find(read_blocks(page), "Título")
    huge = "palavra " * 60
    with pytest.raises(OldSchoolPDFError, match="não cabe"):
        replace_blocks(document, 0, [edit_of(target, huge)], {"expand": True, "shrink": "none"})


def test_invisible_rotated_and_form_text_are_not_editable():
    with pymupdf.open() as doc:
        page = doc.new_page(width=420, height=600)
        page.insert_text((40, 60), "Camada de OCR", fontsize=12, render_mode=3)
        page.insert_text((300, 400), "Vertical", fontsize=12, rotate=90)
        page.insert_text((40, 200), "Sobre o campo", fontsize=12)
        widget = pymupdf.Widget()
        widget.field_type = pymupdf.PDF_WIDGET_TYPE_TEXT
        widget.field_name = "Nome"
        widget.rect = pymupdf.Rect(35, 185, 200, 205)
        page.add_widget(widget)
        blocks = read_blocks(page)
        reasons = {block["text"]: block["reason"] for block in blocks}
        assert "invisível" in reasons["Camada de OCR"]
        assert "girado" in reasons["Vertical"]
        assert "formulário" in reasons["Sobre o campo"]
        with pytest.raises(OldSchoolPDFError, match="invisível"):
            replace_blocks(doc, 0, [edit_of(find(blocks, "OCR"), "x")], {})


def test_stale_or_malformed_requests_are_refused(document):
    target = find(read_blocks(document[0]), "Título")
    stale = edit_of(target, "x") | {"key": "0" * 16}
    with pytest.raises(OldSchoolPDFError, match="mudou"):
        replace_blocks(document, 0, [stale], {})
    bad_style = edit_of(target, "x")
    bad_style["runs"][0]["style"] = 9
    with pytest.raises(OldSchoolPDFError, match="estilo"):
        replace_blocks(document, 0, [bad_style], {})
    with pytest.raises(OldSchoolPDFError, match="controle"):
        replace_blocks(document, 0, [edit_of(target, "a\x00b")], {})
    with pytest.raises(OldSchoolPDFError, match="redução"):
        replace_blocks(document, 0, [edit_of(target, "x")], {"shrink": "total"})
    with pytest.raises(OldSchoolPDFError, match="1 a"):
        replace_blocks(document, 0, [], {})


def test_links_annotations_and_background_image_survive(document):
    page = document[0]
    target = find(read_blocks(page), "Primeira")
    link = {"kind": pymupdf.LINK_URI, "from": pymupdf.Rect(40, 90, 180, 104), "uri": "https://a.b"}
    page.insert_link(link)
    page.add_highlight_annot(pymupdf.Rect(40, 290, 200, 304))
    pixmap = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 40, 40), False)
    pixmap.clear_with(200)
    page.insert_image(pymupdf.Rect(300, 80, 400, 180), pixmap=pixmap)
    report = replace_blocks(document, 0, [edit_of(target, "Com link e imagem")], {})
    assert report["links_restored"] == 1
    with pymupdf.open("pdf", document.tobytes()) as saved:
        reopened = saved[0]
        assert [item["uri"] for item in reopened.get_links()] == ["https://a.b"]
        assert [annot.type[1] for annot in reopened.annots()] == ["Highlight"]
        assert len(reopened.get_images()) == 1


def test_edited_block_can_be_edited_again(document):
    page = document[0]
    replace_blocks(document, 0, [edit_of(find(read_blocks(page), "Título"), "Primeira versão")], {})
    replace_blocks(document, 0, [edit_of(find(read_blocks(page), "Primeira versão"), "Final")], {})
    text = page_text(page)
    assert "Final" in text and "Primeira versão" not in text and "Título" not in text


def test_empty_text_removes_the_block(document):
    page = document[0]
    replace_blocks(document, 0, [edit_of(find(read_blocks(page), "Título"), "  ")], {})
    assert "Título" not in page_text(page)
    assert "Primeira linha" in page_text(page)


def test_two_blocks_change_in_one_operation(document):
    page = document[0]
    blocks = read_blocks(page)
    edits = [
        edit_of(find(blocks, "Título"), "Outro título"),
        edit_of(find(blocks, "Bloco vizinho"), "Outro bloco"),
    ]
    assert replace_blocks(document, 0, edits, {})["blocks"] == 2
    text = page_text(page)
    assert "Outro título" in text and "Outro bloco" in text and "Primeira linha" in text


@pytest.mark.skipif(not TIMES.exists(), reason="Times New Roman do Windows indisponível")
def test_subset_font_is_replaced_by_installed_family_keeping_bold():
    with pymupdf.open() as doc:
        page = doc.new_page(width=420, height=600)
        page.insert_font(fontname="TR", fontfile=str(TIMES))
        page.insert_font(fontname="TB", fontfile=str(TIMES.with_name("timesbd.ttf")))
        page.insert_text((40, 80), "Valor normal ", fontname="TR", fontsize=12)
        # "Destaque" continua a frase logo depois do espaço, como num texto de verdade.
        after = 40 + pymupdf.Font(fontfile=str(TIMES)).text_length("Valor normal ", 12)
        page.insert_text((after, 80), "Destaque", fontname="TB", fontsize=12)
        doc.subset_fonts()
        doc = pymupdf.open("pdf", doc.tobytes())
        page = doc[0]
        target = find(read_blocks(page), "Valor")
        assert len(target["styles"]) == 2
        report = replace_blocks(doc, 0, [keep_runs(target, ("Valor", "Preço"))], {})
        fonts = {
            span["font"]
            for block in page.get_text("dict")["blocks"]
            for line in block["lines"]
            for span in line["spans"]
        }
        assert any("Times" in font and "Bold" in font for font in fonts)
        assert all(entry["exact"] for entry in report["fonts"])
        assert "Preço normal Destaque" in page_text(page)


def test_without_system_fonts_uses_builtin_family(document):
    page = document[0]
    report = replace_blocks(
        document, 0, [edit_of(find(read_blocks(page), "Título"), "Padrão")], {"system_fonts": False}
    )
    assert "fonte padrão" in report["fonts"][0]["label"]


def test_file_size_grows_little_per_edit(document):
    page = document[0]
    base = len(document.tobytes(garbage=1, deflate=True))
    for index in range(3):
        target = find(read_blocks(page), "Bloco vizinho" if index == 0 else f"Edição {index - 1}")
        replace_blocks(document, 0, [edit_of(target, f"Edição {index}")], {})
    assert len(document.tobytes(garbage=1, deflate=True)) - base < 3 * 120_000


def test_engine_applies_undoes_and_respects_permissions(tmp_path):
    source = tmp_path / "contrato.pdf"
    with pymupdf.open() as doc:
        doc.new_page().insert_text((40, 80), "Valor: R$ 100,00", fontsize=12)
        doc.save(source)
    engine = PdfEngine()
    engine.open(str(source))
    result, raster = engine.text_blocks(0, 400, 500, 1.0)
    assert raster and result["frame"]["width"] > 0
    block = result["blocks"][0]
    preview, _ = engine.preview_text(0, [edit_of(block, "Valor: R$ 150,00")], {}, 400, 500, 1.0)
    assert preview["report"]["blocks"] == 1
    assert "100,00" in engine.document[0].get_text()
    scratch = tmp_path / "trabalho"
    scratch.mkdir()
    changed = engine.edit(
        "replace_text", 0, {"blocks": [edit_of(block, "Valor: R$ 150,00")]}, str(scratch), False
    )
    assert changed["report"]["blocks"] == 1 and changed["undo"]
    assert "150,00" in engine.document[0].get_text()
    engine.step(-1)
    assert "100,00" in engine.document[0].get_text()
    engine.close()

    locked = tmp_path / "bloqueado.pdf"
    with pymupdf.open(source) as doc:
        doc.save(
            locked,
            encryption=pymupdf.PDF_ENCRYPT_AES_256,
            owner_pw="dono",
            user_pw="",
            permissions=pymupdf.PDF_PERM_PRINT | pymupdf.PDF_PERM_COPY,
        )
    engine = PdfEngine()
    engine.open(str(locked))
    block = engine.text_blocks(0, 400, 500, 1.0)[0]["blocks"][0]
    with pytest.raises(OldSchoolPDFError, match="permissões"):
        engine.preview_text(0, [edit_of(block, "x")], {}, 400, 500, 1.0)
    with pytest.raises(OldSchoolPDFError, match="permissões"):
        engine.edit("replace_text", 0, {"blocks": [edit_of(block, "x")]}, str(scratch), False)
    engine.close()


def test_run_dataclass_round_trip():
    assert asdict(TextRun("a", 0, True, False)) == {
        "text": "a",
        "style": 0,
        "bold": True,
        "italic": False,
    }


def pattern_pdf(path):
    from PySide6.QtCore import QPointF
    from PySide6.QtGui import (
        QBrush,
        QColor,
        QFont,
        QLinearGradient,
        QPageSize,
        QPainter,
        QPdfWriter,
        QPen,
    )

    writer = QPdfWriter(str(path))
    writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
    writer.setResolution(72)
    painter = QPainter(writer)
    gradient = QLinearGradient(QPointF(50, 0), QPointF(400, 0))
    gradient.setColorAt(0, QColor("#003399"))
    gradient.setColorAt(1, QColor("#003399"))
    painter.setPen(QPen(QBrush(gradient), 1))
    painter.setFont(QFont("Arial", 14))
    painter.drawText(QPointF(60, 120), "Texto pintado com padrão")
    painter.setPen(QColor("#000000"))
    painter.drawText(QPointF(60, 300), "Vizinho comum")
    painter.end()
    return path


def test_pattern_filled_text_keeps_its_visible_color(qapp, tmp_path):
    with pymupdf.open(pattern_pdf(tmp_path / "padrao.pdf")) as doc:
        page = doc[0]
        target = find(read_blocks(page), "padrão")
        assert target["styles"][0]["color"] == 0x003399
        replace_blocks(doc, 0, [edit_of(target, "Texto editado")], {})
        spans = [
            span
            for block in page.get_text("dict")["blocks"]
            for line in block.get("lines", [])
            for span in line["spans"]
            if "editado" in span["text"]
        ]
        assert spans and spans[0]["color"] == 0x003399


def test_white_on_dark_and_small_black_text_are_not_recoloured():
    with pymupdf.open() as doc:
        page = doc.new_page(width=420, height=600)
        page.draw_rect(pymupdf.Rect(30, 40, 390, 90), color=None, fill=(0.04, 0.14, 0.42))
        page.insert_text((40, 72), "Título branco", fontsize=16, color=(1, 1, 1))
        page.insert_text((40, 200), "texto miúdo preto", fontsize=7)
        blocks = read_blocks(page)
        assert find(blocks, "Título branco")["styles"][0]["color"] == 0xFFFFFF
        assert find(blocks, "miúdo")["styles"][0]["color"] == 0x000000
        replace_blocks(doc, 0, [edit_of(find(blocks, "Título branco"), "Novo título")], {})
        assert "Novo título" in page_text(page)


def test_invisible_white_on_white_text_is_refused():
    with pymupdf.open() as doc:
        page = doc.new_page(width=420, height=600)
        page.insert_text((40, 80), "Texto branco escondido", fontsize=12, color=(1, 1, 1))
        target = find(read_blocks(page), "escondido")
        with pytest.raises(OldSchoolPDFError, match="invisível"):
            replace_blocks(doc, 0, [edit_of(target, "Outro")], {})


def test_table_cells_on_one_line_become_separate_blocks():
    with pymupdf.open() as doc:
        page = doc.new_page(width=500, height=400)
        for x, text in ((40, "Produto"), (200, "Preço"), (330, "Qtd")):
            page.insert_text((x, 80), text, fontsize=11)
        for x, text in ((40, "Café"), (200, "R$ 10,00"), (330, "3")):
            page.insert_text((x, 96), text, fontsize=11)
        blocks = read_blocks(page)
        assert {"Produto", "Preço", "Qtd", "Café", "R$ 10,00", "3"} <= {b["text"] for b in blocks}
        cell = find(blocks, "R$ 10,00")
        replace_blocks(doc, 0, [edit_of(cell, "R$ 12,50")], {})
        words = page.get_text("words")
        price = next(w for w in words if w[4] == "12,50")
        # A célula foi trocada no lugar; as vizinhas continuam onde estavam.
        assert price[0] < 330 and next(w for w in words if w[4] == "Qtd")[0] == pytest.approx(
            330, abs=1
        )


def test_tight_single_line_heading_grows_sideways_without_losing_words():
    # Título de uma linha com o parágrafo logo abaixo, como nos PDFs do Word: o MuPDF dizia
    # que o texto cabia e descartava a segunda linha em silêncio.
    with pymupdf.open() as doc:
        page = doc.new_page(width=612, height=792)
        page.insert_text((90, 192), "Cláusula Primeira - Do Objeto", fontsize=14, fontname="hebo")
        page.insert_text(
            (90, 214), "O objeto deste contrato é a prestação de serviços.", fontsize=11
        )
        heading = find(read_blocks(page), "Cláusula")
        assert heading["text"] == "Cláusula Primeira - Do Objeto"
        longer = "Cláusula Primeira - Do Objeto do Contrato"
        report = replace_blocks(doc, 0, [edit_of(heading, longer)], {"shrink": "none"})
        assert report["widened"] == 1 and report["scale"] == 1.0
        assert longer in page_text(page)
        assert "O objeto deste contrato" in page_text(page)


def test_centered_single_line_title_stays_centered():
    with pymupdf.open() as doc:
        page = doc.new_page(width=600, height=400)
        page.insert_text(
            (40, 160), "Texto comum alinhado à esquerda da página inteira.", fontsize=11
        )
        width = pymupdf.get_text_length("Relatório", fontsize=18)
        page.insert_text(((600 - width) / 2, 80), "Relatório", fontsize=18)
        title = find(read_blocks(page), "Relatório")
        assert title["align"] == "center"
        replace_blocks(
            doc, 0, [edit_of(title, "Relatório anual de atividades")], {"shrink": "none"}
        )
        box = page.search_for("Relatório anual de atividades")[0]
        assert abs((box.x0 + box.x1) / 2 - 300) < 6
