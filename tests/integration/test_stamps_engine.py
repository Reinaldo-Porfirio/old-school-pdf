"""Numeração, cabeçalho e rodapé, marca d'água, localizar e substituir e desenhos."""

import pymupdf
import pytest

from oldschoolpdf.domain.errors import OldSchoolPDFError
from oldschoolpdf.domain.text_editing import TextRun
from oldschoolpdf.infrastructure.pdf_editing import edit_annotation, read_objects
from oldschoolpdf.infrastructure.pdf_engine import PdfEngine
from oldschoolpdf.infrastructure.pdf_pages import resize_pages
from oldschoolpdf.infrastructure.pdf_replace import find_text, splice
from oldschoolpdf.infrastructure.pdf_stamps import (
    header_footer,
    remove_stamps,
    strip_watermarks,
    tracked,
    watermark,
)
from oldschoolpdf.infrastructure.pdf_text_edit import read_blocks, replace_blocks


def sample(*, rotation=0, crop=None, pages=3, image=False):
    doc = pymupdf.open()
    for number in range(pages):
        page = doc.new_page(width=595, height=842)
        if image:
            # Página digitalizada: uma imagem branca cobre tudo.
            pixmap = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 40, 56), False)
            pixmap.set_rect(pixmap.irect, (255, 255, 255))
            page.insert_image(page.rect, pixmap=pixmap)
        page.insert_text((90, 200), f"Corpo da página {number + 1}", fontsize=14)
        page.insert_text((90, 230), "Contrato com a CONTRATANTE e o contratado.", fontsize=11)
        if crop:
            page.set_cropbox(pymupdf.Rect(*crop))
        page.set_rotation(rotation)
    return doc


def visible(page):
    matrix = page.rotation_matrix
    return [(word[4], pymupdf.Rect(word[:4]) * matrix) for word in page.get_text("words")]


def phrase_box(page, first):
    boxes = [box for word, box in visible(page) if word == first]
    assert boxes, (first, page.get_text())
    return boxes[0]


# Cabeçalho, rodapé e numeração
@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
@pytest.mark.parametrize("crop", [None, (30, 40, 565, 820)])
def test_header_footer_lands_where_the_user_sees_it(rotation, crop):
    doc = sample(rotation=rotation, crop=crop)
    values = {
        "ranges": [(1, 2)],
        "slots": {
            "header_left": "Acordo nº 7 — [arquivo]",
            "header_right": "[data]",
            "footer_center": "Página [página] de [total]",
        },
        "start": 5,
        "date": "23/11/2026",
        "file": "acordo.pdf",
    }
    first, report = header_footer(doc, values)
    assert first == 1 and report["pages"] == 2 and report["replaced"] == 0
    assert "Página" not in doc[0].get_text()
    for number, label in ((1, "5"), (2, "6")):
        page = doc[number]
        text = " ".join(page.get_text().split())
        assert f"Página {label} de 6" in text and "acordo.pdf" in text and "23/11/2026" in text
        width, height = page.rect.width, page.rect.height
        footer = phrase_box(page, "Página")
        header = phrase_box(page, "Acordo")
        date = phrase_box(page, "23/11/2026")
        assert footer.y0 > height * 0.9 and header.y1 < height * 0.1 and date.y1 < height * 0.1
        assert header.x0 < width * 0.15 and date.x1 > width * 0.85
        # As palavras saem na horizontal, como a página aparece.
        assert footer.width > footer.height
        assert tracked(doc, page)["header"]


def test_header_is_replaced_removed_and_survives_saving():
    doc = sample()
    values = {"ranges": [(0, 2)], "slots": {"footer_right": "[página]"}}
    header_footer(doc, values)
    _, report = header_footer(doc, {**values, "slots": {"footer_right": "Folha [página]"}})
    assert report["replaced"] == 3
    assert "Folha 1" in doc[0].get_text() and doc[0].get_text().count("1") == 1 + 1  # "Folha 1"
    reopened = pymupdf.open("pdf", doc.tobytes(garbage=3, deflate=True))
    assert all(tracked(reopened, page)["header"] for page in reopened)
    _, report = remove_stamps(reopened, {"ranges": [(0, 1)], "kinds": ["header"]})
    assert report["removed"] == {"header": 2}
    assert "Folha" not in reopened[0].get_text() and "Folha 3" in reopened[2].get_text()
    with pytest.raises(OldSchoolPDFError, match="Nenhum"):
        remove_stamps(reopened, {"ranges": [(0, 1)], "kinds": ["header", "watermark"]})


def test_header_warns_when_crowded_and_refuses_bad_text():
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((30, 820), "Rodapé que já existia", fontsize=10)
    _, report = header_footer(doc, {"ranges": [(0, 0)], "slots": {"footer_left": "[página]"}})
    assert report["crowded"] == [1]
    cases = (
        ({"footer_center": "x" * 199}, "não cabe"),
        ({"footer_left": "A" * 60, "footer_center": "B" * 60}, "se encostam"),
        ({"footer_left": "olá 😀"}, "caractere"),
        ({}, "pelo menos"),
        ({"rodape": "x"}, "inválidas"),
    )
    for slots, message in cases:
        with pytest.raises(OldSchoolPDFError, match=message):
            header_footer(doc, {"ranges": [(0, 0)], "slots": slots})
    with pytest.raises(OldSchoolPDFError, match="tamanho"):
        header_footer(doc, {"ranges": [(0, 0)], "slots": {"footer_left": "1"}, "size": 99})


# Marca d'água
@pytest.mark.parametrize("rotation", [0, 90])
def test_text_watermark_is_vector_translucent_and_removable(rotation):
    doc = sample(rotation=rotation, crop=(30, 40, 565, 820))
    before = [page.get_text() for page in doc]
    _, report = watermark(
        doc, {"ranges": [(0, 2)], "mode": "text", "text": "CONFIDENCIAL", "opacity": 30}
    )
    assert report == {"pages": 3, "hidden": [], "hidden_count": 0}
    for page, text in zip(doc, before, strict=True):
        # Não vira texto: busca, cópia e Word continuam iguais.
        assert page.get_text() == text
        drawings = page.get_drawings()
        assert drawings and all(abs(item["fill_opacity"] - 0.3) < 0.01 for item in drawings)
        area = pymupdf.Rect(drawings[0]["rect"])
        for item in drawings:
            area |= item["rect"]
        # Diagonal no centro da página.
        center = (area * page.rotation_matrix).tl + (area * page.rotation_matrix).br
        assert abs(center.x / 2 - page.rect.width / 2) < page.rect.width * 0.1
    _, report = watermark(doc, {"ranges": [(0, 0)], "mode": "text", "text": "CÓPIA"})
    assert len(tracked(doc, doc[0])["watermark"]) == 1
    strip_watermarks(doc)
    assert not doc[0].get_drawings() and not any(tracked(doc, page)["watermark"] for page in doc)


def test_watermark_behind_a_scan_is_reported_or_refused(tmp_path):
    doc = sample(image=True, pages=2)
    with pytest.raises(OldSchoolPDFError, match="escondida"):
        watermark(doc, {"ranges": [(0, 1)], "mode": "text", "text": "PAGO"})
    mixed = sample(pages=1)
    mixed.insert_pdf(sample(image=True, pages=1))
    _, report = watermark(mixed, {"ranges": [(0, 1)], "mode": "text", "text": "PAGO"})
    assert report["hidden"] == [2]
    _, report = watermark(
        mixed, {"ranges": [(0, 1)], "mode": "text", "text": "PAGO", "layer": "front"}
    )
    assert report["hidden_count"] == 0
    logo = tmp_path / "logo.png"
    pixmap = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 60, 30), False)
    pixmap.set_rect(pixmap.irect, (200, 30, 30))
    pixmap.save(logo)
    _, report = watermark(
        mixed,
        {
            "ranges": [(0, 0)],
            "mode": "image",
            "path": str(logo),
            "scale": 40,
            "layer": "front",
            "opacity": 100,
        },
    )
    images = mixed[0].get_image_info()
    assert report["pages"] == 1 and any(
        abs(pymupdf.Rect(item["bbox"]).width - mixed[0].rect.width * 0.4) < 2 for item in images
    )
    with pytest.raises(OldSchoolPDFError, match="Escreva"):
        watermark(mixed, {"ranges": [(0, 0)], "mode": "text", "text": "  "})
    with pytest.raises(OldSchoolPDFError, match="opacidade"):
        watermark(mixed, {"ranges": [(0, 0)], "mode": "text", "text": "A", "opacity": 0})


def test_stamps_do_not_block_text_editing_and_survive_resizing():
    doc = sample(pages=1)
    header_footer(doc, {"ranges": [(0, 0)], "slots": {"footer_center": "Folha [página]"}})
    watermark(doc, {"ranges": [(0, 0)], "mode": "text", "text": "RASCUNHO", "opacity": 40})
    doc = pymupdf.open("pdf", doc.tobytes())
    block = next(block for block in read_blocks(doc[0]) if block["text"].startswith("Contrato"))
    edit = {"key": block["key"], "runs": [dict(block["runs"][0], text=block["text"] + " Fim.")]}
    replace_blocks(doc, 0, [edit], {})
    # A edição cria seus próprios XObjects: o cabeçalho não pode passar a desenhar o texto novo.
    text = " ".join(doc[0].get_text().split())
    assert text.count("Fim.") == 1 and "Folha 1" in text
    doc = pymupdf.open("pdf", doc.tobytes())
    block = next(block for block in read_blocks(doc[0]) if block["text"].startswith("Corpo"))
    edit = {"key": block["key"], "runs": [dict(block["runs"][0], text="Corpo novo")]}
    replace_blocks(doc, 0, [edit], {})
    text = " ".join(doc[0].get_text().split())
    assert text.count("Fim.") == 1 and text.count("Corpo novo") == 1 and "Folha 1" in text
    resize_pages(doc, {"ranges": [(0, 0)], "size": "a5"})
    marks = tracked(doc, doc[0])
    assert marks["header"] and marks["watermark"]
    _, report = remove_stamps(doc, {"ranges": [(0, 0)], "kinds": ["watermark"]})
    assert report["removed"] == {"watermark": 1} and not doc[0].get_drawings()


# Localizar e substituir
def test_splice_keeps_the_style_where_the_match_starts():
    runs = [TextRun("Olá ", 0, False, False), TextRun("mundo", 1, True, False)]
    assert splice(runs, 2, 6, "X") == [
        TextRun("OlX", 0, False, False),
        TextRun("ndo", 1, True, False),
    ]
    assert splice(runs, 4, 9, "") == [TextRun("Olá ", 0, False, False)]
    assert splice(runs, 4, 9, "terra") == [
        TextRun("Olá ", 0, False, False),
        TextRun("terra", 1, True, False),
    ]


def test_find_respects_case_and_whole_words():
    doc = sample(pages=2)
    everything = find_text(doc, {"query": "contrat", "ranges": [(0, 1)]})
    assert len(everything["items"]) == 6
    words = find_text(doc, {"query": "contratante", "word": True, "ranges": [(0, 1)]})
    assert [item["match"] for item in words["items"]] == ["CONTRATANTE", "CONTRATANTE"]
    exact = find_text(doc, {"query": "Contrato", "case": True, "ranges": [(1, 1)]})
    assert len(exact["items"]) == 1 and exact["items"][0]["page"] == 1
    assert exact["items"][0]["after"].startswith("com a")
    with pytest.raises(OldSchoolPDFError, match="Escreva"):
        find_text(doc, {"query": "  ", "ranges": [(0, 1)]})


def test_engine_replaces_marked_matches_skipping_what_does_not_fit(tmp_path):
    source = tmp_path / "base.pdf"
    with pymupdf.open() as doc:
        page = doc.new_page(width=420, height=600)
        page.insert_text((40, 100), "Pagamento ao fornecedor até sexta.", fontsize=11)
        # Duas células apertadas, lado a lado, como numa tabela.
        page.insert_text((40, 200), "Item", fontsize=11)
        page.insert_text((200, 200), "fornecedor", fontsize=11)
        page.insert_text((280, 200), "Valor", fontsize=11)
        doc.new_page(width=420, height=600).insert_text((40, 100), "Outro fornecedor.")
        doc.save(source)
    scratch = tmp_path / "trabalho"
    scratch.mkdir()
    engine = PdfEngine()
    engine.open(str(source))
    found = engine.find_text({"query": "fornecedor", "ranges": [(0, 1)]})
    items = [{key: item[key] for key in ("page", "key", "start", "end")} for item in found["items"]]
    assert len(items) == 3
    values = {"query": "fornecedor", "replacement": "prestador de serviços", "items": items}
    result = engine.edit("replace_matches", 0, values, str(scratch), False)
    report = result["report"]
    assert report["items"] == 2 and report["pages"] == 2
    assert [item["page"] for item in report["failed"]] == [1]
    assert "prestador de serviços" in " ".join(engine.document[1].get_text().split())
    assert result["undo"]
    engine.step(-1)
    assert "prestador" not in engine.document[1].get_text()
    with pytest.raises(OldSchoolPDFError, match="Nenhuma ocorrência"):
        engine.edit(
            "replace_matches",
            0,
            {**values, "items": [items[1]], "replacement": "prestador de serviços terceirizados"},
            str(scratch),
            False,
        )
    engine.close()


def test_new_edits_need_permission_to_modify(tmp_path):
    source = tmp_path / "base.pdf"
    sample(pages=1).save(source)
    locked = tmp_path / "restrito.pdf"
    with pymupdf.open(source) as doc:
        doc.save(locked, encryption=pymupdf.PDF_ENCRYPT_AES_256, owner_pw="dono", user_pw="",
                 permissions=pymupdf.PDF_PERM_PRINT | pymupdf.PDF_PERM_COPY)  # fmt: skip
    scratch = tmp_path / "trabalho"
    scratch.mkdir()
    engine = PdfEngine()
    engine.open(str(locked))
    for action, values in (
        ("header_footer", {"ranges": [(0, 0)], "slots": {"footer_left": "1"}}),
        ("watermark", {"ranges": [(0, 0)], "mode": "text", "text": "A"}),
        ("remove_stamps", {"ranges": [(0, 0)], "kinds": ["header"]}),
        ("replace_matches", {"query": "a", "replacement": "b", "items": []}),
    ):
        with pytest.raises(OldSchoolPDFError, match="permissões"):
            engine.edit(action, 0, values, str(scratch), False)
    with pytest.raises(OldSchoolPDFError, match="permissões"):
        engine.find_text({"query": "Corpo", "ranges": [(0, 0)]})
    engine.close()


# Desenhos e texto riscado
@pytest.mark.parametrize("rotation", [0, 90])
def test_pen_lines_arrows_and_strikeout(rotation):
    doc = sample(pages=1, rotation=rotation, crop=(20, 30, 575, 812))
    page = doc[0]
    word = phrase_box(page, "Corpo")
    width, height = page.rect.width, page.rect.height
    region = (
        (word.x0 - 2) / width,
        (word.y0 - 2) / height,
        (word.x1 + 2) / width,
        (word.y1 + 2) / height,
    )
    edit_annotation(page, "add_annotation", {"kind": "strikeout", "region": region})
    strokes = [[[0.2, 0.5], [0.3, 0.55], [0.4, 0.5]], [[0.2, 0.6], [0.4, 0.6]]]
    edit_annotation(
        page,
        "add_annotation",
        {"kind": "ink", "strokes": strokes, "color": "red", "width": "thick"},
    )
    for kind, points in (("arrow", [[0.1, 0.9], [0.5, 0.7]]), ("line", [[0.6, 0.9], [0.9, 0.9]])):
        edit_annotation(page, "add_annotation", {"kind": kind, "points": points, "color": "yellow"})
    objects = {item["kind"]: item for item in read_objects(page)["annotations"]}
    assert set(objects) == {"strikeout", "ink", "arrow", "line"}
    assert not objects["strikeout"]["movable"] and objects["ink"]["movable"]
    ink = objects["ink"]["region"]
    assert abs(ink[0] - 0.2) < 0.03 and abs(ink[3] - 0.6) < 0.03
    arrow = objects["arrow"]["region"]
    assert arrow[0] < 0.12 and arrow[3] > 0.88
    edit_annotation(
        page, "move_annotation", {"xref": objects["arrow"]["xref"], "delta": (0.2, -0.1)}
    )
    edit_annotation(page, "move_annotation", {"xref": objects["ink"]["xref"], "delta": (0.9, 0.0)})
    moved = {item["kind"]: item["region"] for item in read_objects(page)["annotations"]}
    assert abs(moved["arrow"][0] - arrow[0] - 0.2) < 0.02
    assert abs(moved["arrow"][1] - arrow[1] + 0.1) < 0.02
    # O desenho para na borda da página em vez de sair dela.
    assert moved["ink"][2] <= 1.0 and moved["ink"][2] > 0.98
    for values, message in (
        ({"kind": "ink", "strokes": []}, "traços"),
        ({"kind": "ink", "strokes": [[[0.1, 0.1], [2, 0.1]]]}, "fora da página"),
        ({"kind": "line", "points": [[0.5, 0.5], [0.5, 0.501]]}, "Arraste"),
        ({"kind": "arrow", "points": [[0.1, 0.1], [0.3, 0.3]], "color": "rosa"}, "cor"),
    ):
        with pytest.raises(OldSchoolPDFError, match=message):
            edit_annotation(page, "add_annotation", values)


def test_text_editor_points_to_the_header_tool_for_stamped_text():
    doc = sample(pages=1)
    header_footer(doc, {"ranges": [(0, 0)], "slots": {"footer_center": "Folha [página]"}})
    blocks = read_blocks(doc[0])
    stamped = [block for block in blocks if block["text"].startswith("Folha")]
    assert stamped and not stamped[0]["editable"]
    assert "Numeração, cabeçalho e rodapé" in stamped[0]["reason"]
    assert all(block["editable"] for block in blocks if block not in stamped)
    # A leitura não altera o conteúdo da página.
    assert tracked(doc, doc[0])["header"] and "Folha 1" in doc[0].get_text()


def test_tokens_and_one_line_rules():
    from oldschoolpdf.domain.stamps import expand_tokens, one_line

    text = "[Página]/[total] · [pagina] · [data] · [arquivo] · [outro]"
    assert expand_tokens(text, 3, 9, "01/02/2026", "a.pdf") == (
        "3/9 · 3 · 01/02/2026 · a.pdf · [outro]"
    )
    assert one_line("  Olá \t mundo ", 20, "x") == "Olá mundo"
    for value in ("a\x00b", "a​b", 7):
        with pytest.raises(OldSchoolPDFError):
            one_line(value, 20, "x")
    with pytest.raises(OldSchoolPDFError, match="até 3"):
        one_line("abcd", 3, "x")
