"""Conversão de PDF para Word sem interface: estrutura, estilos, tabelas, imagens e OCR."""

import zipfile

import pymupdf
import pytest
from docx import Document

from oldschoolpdf.domain.errors import OldSchoolPDFError
from oldschoolpdf.infrastructure.media_output import MediaOutput
from oldschoolpdf.infrastructure.pdf_docx import family_name, pdf_to_docx
from oldschoolpdf.infrastructure.pdf_media import process_media

BODY = "Texto comum do relatório com palavras suficientes para ocupar a linha toda."


def image_pixmap(width=120, height=80, value=90):
    pixmap = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, width, height), False)
    pixmap.clear_with(value)
    return pixmap


def build(path):
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 80), "Relatório Mensal", fontsize=22, fontname="hebo")
    y = 120
    for _ in range(3):
        page.insert_text((72, y), BODY, fontsize=10)
        y += 13
    page.insert_text((72, y + 20), "Resultados", fontsize=15, fontname="hebo")
    page.insert_text((72, y + 45), "Palavra em itálico", fontsize=10, fontname="heit")
    # Tabela com linhas de grade desenhadas.
    top, rows, cols = 300, 3, 3
    for r in range(rows + 1):
        page.draw_line((72, top + r * 20), (372, top + r * 20))
    for c in range(cols + 1):
        page.draw_line((72 + c * 100, top), (72 + c * 100, top + rows * 20))
    cells = [["Produto", "Preço", "Qtd"], ["Café", "R$ 10,00", "3"], ["Pão", "R$ 2,50", "12"]]
    for r, row in enumerate(cells):
        for c, value in enumerate(row):
            page.insert_text((78 + c * 100, top + 14 + r * 20), value, fontsize=10)
    page.insert_text((72, 420), "Visite o site oficial agora.", fontsize=10)
    link = page.search_for("site oficial")[0]
    page.insert_link({"kind": pymupdf.LINK_URI, "from": link, "uri": "https://example.org"})
    page.insert_image(pymupdf.Rect(72, 450, 252, 570), pixmap=image_pixmap())
    # Página em paisagem.
    wide = doc.new_page(width=842, height=595)
    wide.insert_text((72, 80), "Página em paisagem", fontsize=12)
    # Página digitalizada com a camada invisível do OCR.
    scan = doc.new_page()
    scan.insert_image(scan.rect, pixmap=image_pixmap(600, 800, 235))
    scan.insert_text((72, 100), "Texto reconhecido pelo OCR", fontsize=12, render_mode=3)
    # Página digitalizada sem OCR.
    raw = doc.new_page()
    raw.insert_image(raw.rect, pixmap=image_pixmap(600, 800, 200))
    doc.save(path)
    return doc


def test_conversion_keeps_structure_styles_tables_images_links_and_pages(tmp_path):
    doc = build(tmp_path / "relatorio.pdf")
    target = tmp_path / "relatorio.docx"
    steps = []
    detail = pdf_to_docx(doc, list(range(doc.page_count)), target, lambda *a: steps.append(a))
    assert steps and "4 página(s)" in detail and "1 tabela(s)" in detail
    assert "OCR usado em 1 página(s)" in detail and "1 página(s) digitalizada(s)" in detail
    word = Document(str(target))
    paragraphs = [p for p in word.paragraphs if p.text.strip()]
    styles = {p.text: p.style.name for p in paragraphs}
    assert styles["Relatório Mensal"] == "Heading 1"
    assert styles["Resultados"] == "Heading 2"
    body = next(p for p in paragraphs if p.text.startswith("Texto comum"))
    # As três linhas viram um parágrafo só.
    assert body.text.count("Texto comum") == 3
    title_run = next(p for p in paragraphs if p.text == "Relatório Mensal").runs[0]
    assert title_run.bold and title_run.font.size.pt == 22
    italic = next(p for p in paragraphs if p.text == "Palavra em itálico").runs[0]
    assert italic.italic
    table = word.tables[0]
    assert [[cell.text for cell in row.cells] for row in table.rows] == [
        ["Produto", "Preço", "Qtd"],
        ["Café", "R$ 10,00", "3"],
        ["Pão", "R$ 2,50", "12"],
    ]
    assert not any("R$ 10,00" in p.text for p in paragraphs)
    assert "Texto reconhecido pelo OCR" in [p.text for p in paragraphs]
    with zipfile.ZipFile(target) as archive:
        relations = archive.read("word/_rels/document.xml.rels").decode()
        media = [name for name in archive.namelist() if name.startswith("word/media/")]
    assert "https://example.org" in relations
    # A ilustração e a página digitalizada sem OCR; a digitalização com OCR vira só texto.
    assert len(media) == 2
    sizes = [(round(s.page_width.pt), round(s.page_height.pt)) for s in word.sections]
    assert sizes == [(595, 842), (842, 595), (595, 842)]
    assert word.core_properties.author == ""


def test_only_selected_pages_and_empty_selection(tmp_path):
    doc = build(tmp_path / "relatorio.pdf")
    target = tmp_path / "paisagem.docx"
    detail = pdf_to_docx(doc, [1], target, lambda *a: None)
    assert detail.startswith("1 página(s)")
    texts = [p.text for p in Document(str(target)).paragraphs if p.text.strip()]
    assert texts == ["Página em paisagem"]
    with pymupdf.open() as empty:
        empty.new_page()
        with pytest.raises(OldSchoolPDFError, match="não têm texto"):
            pdf_to_docx(empty, [0], tmp_path / "vazio.docx", lambda *a: None)


def test_font_family_names_for_word():
    assert family_name("ABCDEF+TimesNewRomanPS-BoldMT") in {"Times New Roman", "TimesNewRoman"}
    assert family_name("Helvetica") in {"Arial", "Helvetica"}
    assert family_name("ABCDEF+MinhaFonteEspecial-Bold") == "Minha Fonte Especial"


def test_media_pipeline_publishes_the_word_document(tmp_path):
    source = tmp_path / "Relatório anual.pdf"
    build(source).close()
    output = MediaOutput.prepare(tmp_path, "Relatório anual - Word")
    result = process_media(
        "docx", [str(source)], str(output.stage), {"ranges": "1-2"}, lambda *a: None
    )
    assert result["files"] == 1 and "2 página(s)" in result["detail"]
    published = output.publish(1)
    assert published.name == "documento.docx" and published.parent.name == "Relatório anual - Word"
    assert Document(str(published)).paragraphs
