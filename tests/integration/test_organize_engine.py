"""Páginas em branco, corte, tamanho do papel, marcadores, campos e continuação de texto."""

import pymupdf
import pytest

from oldschoolpdf.domain.editing import MM, paper_size
from oldschoolpdf.domain.errors import OldSchoolPDFError
from oldschoolpdf.infrastructure.pdf_engine import PdfEngine
from oldschoolpdf.infrastructure.pdf_forms import add_field, remove_field
from oldschoolpdf.infrastructure.pdf_outline import read_outline, set_outline, suggest_outline
from oldschoolpdf.infrastructure.pdf_pages import crop_pages, insert_blank, resize_pages
from oldschoolpdf.infrastructure.pdf_text_edit import read_blocks, replace_blocks


def sample(*, rotation=0, crop=None, offset=False, pages=1):
    doc = pymupdf.open()
    for _ in range(pages):
        page = doc.new_page(width=612, height=792)
        if offset:
            doc.xref_set_key(page.xref, "MediaBox", "[100 200 712 992]")
            page = doc[page.number]
        page.insert_text((72, 100), "Topo esquerdo", fontsize=14)
        page.insert_text((400, 700), "Fundo direito", fontsize=14)
        page.add_highlight_annot(page.search_for("Topo"))
        page.insert_link(
            {
                "kind": pymupdf.LINK_URI,
                "from": pymupdf.Rect(400, 685, 500, 705),
                "uri": "https://example.org",
            }
        )
        widget = pymupdf.Widget()
        widget.field_type = pymupdf.PDF_WIDGET_TYPE_TEXT
        widget.field_name = f"nome{page.number}"
        widget.field_value = "olá"
        widget.rect = pymupdf.Rect(72, 300, 300, 330)
        page.add_widget(widget)
    for page in doc:
        if crop:
            media = page.mediabox
            page.set_cropbox(pymupdf.Rect(*crop) + (media.x0, 0, media.x0, 0))
        page.set_rotation(rotation)
    return doc


def visible_words(page):
    """Palavras na página como ela aparece, já com a rotação aplicada."""
    matrix = page.rotation_matrix
    return {word[4]: pymupdf.Rect(word[:4]) * matrix for word in page.get_text("words")}


# Páginas em branco
def test_blank_pages_take_size_position_and_orientation():
    doc = sample(pages=2, rotation=90)
    assert insert_blank(doc, 0, {"where": "after", "count": 2, "size": "same"}) == 1
    assert doc.page_count == 4
    assert doc[1].rect == doc[0].rect and not doc[1].get_text().strip()
    assert insert_blank(doc, 0, {"where": "before", "size": "a4", "orientation": "landscape"}) == 0
    width, height = paper_size("a4", "landscape")
    assert abs(doc[0].rect.width - width) < 0.5 and abs(doc[0].rect.height - height) < 0.5
    insert_blank(doc, doc.page_count - 1, {"where": "after", "size": "letter"})
    assert doc[-1].rect == pymupdf.Rect(0, 0, 612, 792)
    for bad in ({"count": 0}, {"count": 51}, {"where": "meio"}, {"size": "a3"}):
        with pytest.raises(OldSchoolPDFError):
            insert_blank(doc, 0, {"where": "after", "size": "same", **bad})


# Corte
@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
def test_fixed_margins_cut_what_the_user_sees(rotation):
    doc = sample(rotation=rotation)
    before = doc[0].rect
    words = visible_words(doc[0])
    crop_pages(doc, {"ranges": [(0, 0)], "mode": "margins", "margins": [5, 8, 6, 7]})
    after = doc[0].rect
    assert abs(after.width - (before.width - 11 * MM)) < 0.6
    assert abs(after.height - (before.height - 15 * MM)) < 0.6
    moved = visible_words(doc[0])
    # Tudo o que aparece deslocou exatamente a margem esquerda e a superior.
    for word in ("Topo", "Fundo"):
        assert abs(moved[word].x0 - (words[word].x0 - 5 * MM)) < 0.6
        assert abs(moved[word].y0 - (words[word].y0 - 8 * MM)) < 0.6


def test_auto_crop_reset_and_limits():
    doc = sample(offset=True)
    insert_blank(doc, 0, {"where": "after", "size": "same"})
    report = crop_pages(doc, {"ranges": [(0, 1)], "mode": "auto", "margins": [5, 5, 5, 5]})[1]
    assert report == {"pages": 1, "blank": 1}
    area = doc[0].rect
    assert area.width < 612 - 100 and area.height < 792 - 100
    assert {"Topo", "Fundo"} <= set(visible_words(doc[0]))
    crop_pages(doc, {"ranges": [(0, 0)], "mode": "reset"})
    assert doc[0].rect == pymupdf.Rect(0, 0, 612, 792)
    with pytest.raises(OldSchoolPDFError, match="Nenhuma página mudou"):
        crop_pages(doc, {"ranges": [(0, 0)], "mode": "reset"})
    with pytest.raises(OldSchoolPDFError, match="pequena demais"):
        crop_pages(doc, {"ranges": [(0, 0)], "mode": "margins", "margins": [200, 0, 200, 0]})
    with pytest.raises(OldSchoolPDFError, match="margens"):
        crop_pages(doc, {"ranges": [(0, 0)], "mode": "margins", "margins": [1, 2, 3]})


# Tamanho do papel
@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
@pytest.mark.parametrize("crop", [None, (50, 50, 560, 740)])
@pytest.mark.parametrize("offset", [False, True])
def test_resize_scales_content_annotations_links_and_fields(rotation, crop, offset):
    doc = sample(rotation=rotation, crop=crop, offset=offset)
    page = doc[0]
    before = page.rect
    words = visible_words(page)
    resize_pages(doc, {"ranges": [(0, 0)], "size": "a4", "orientation": "auto"})
    with pymupdf.open("pdf", doc.tobytes()) as saved:
        page = saved[0]
        width, height = paper_size(
            "a4", "landscape" if before.width > before.height else "portrait"
        )
        assert abs(page.rect.width - width) < 1 and abs(page.rect.height - height) < 1
        scale = min(width / before.width, height / before.height)
        dx, dy = (width - before.width * scale) / 2, (height - before.height * scale) / 2
        moved = visible_words(page)
        for word in ("Topo", "Fundo"):
            assert abs(moved[word].x0 - (words[word].x0 * scale + dx)) < 1.5
            assert abs(moved[word].y0 - (words[word].y0 * scale + dy)) < 1.5
        # Links são lidos como a página aparece; a busca, sem a rotação.
        link = pymupdf.Rect(page.get_links()[0]["from"])
        assert link.intersects(page.search_for("Fundo")[0] * page.rotation_matrix)
        highlight = next(page.annots(types=[pymupdf.PDF_ANNOT_HIGHLIGHT]))
        assert highlight.rect.intersects(page.search_for("Topo")[0])
        widget = next(page.widgets())
        assert widget.field_value == "olá" and widget.rect.width > 100
        # O texto continua editável depois do redimensionamento.
        block = next(b for b in read_blocks(page) if "Topo" in b["text"])
        edit = {"key": block["key"], "runs": [dict(block["runs"][0], text="Topo novo")]}
        replace_blocks(saved, 0, [edit], {})
        assert "Topo novo" in " ".join(saved[0].get_text().split())


def test_resize_keeps_hidden_crop_hidden_and_refuses_repeats():
    doc = sample(crop=(0, 0, 612, 600))
    resize_pages(doc, {"ranges": [(0, 0)], "size": "letter", "orientation": "landscape"})
    # "Fundo direito" estava fora do corte e não pode reaparecer na margem.
    page = doc[0]
    pixmap = page.get_pixmap(
        dpi=30, clip=pymupdf.Rect(page.rect.x1 - 200, 0, page.rect.x1, page.rect.y1)
    )
    assert set(pixmap.samples) <= {255, 254} or min(pixmap.samples) > 200
    with pytest.raises(OldSchoolPDFError, match="já estão"):
        resize_pages(doc, {"ranges": [(0, 0)], "size": "letter", "orientation": "landscape"})


# Marcadores
def outline_document():
    doc = pymupdf.open()
    for number in range(4):
        page = doc.new_page()
        page.insert_text((72, 40), "Relatório anual · cabeçalho", fontsize=9)
        page.insert_text((72, 90), f"Capítulo {number + 1}", fontsize=20)
        page.insert_text((72, 130), f"Seção {number + 1}.1", fontsize=14)
        for line in range(20):
            page.insert_text(
                (72, 160 + line * 14), "Texto comum do corpo do documento.", fontsize=10
            )
    doc.set_toc(
        [[1, "Velho", 1], [1, "Site", -1, {"kind": pymupdf.LINK_URI, "uri": "https://example.org"}]]
    )
    return doc


def test_outline_round_trip_keeps_external_links_and_detects_staleness():
    doc = outline_document()
    current = read_outline(doc)
    assert [(e["title"], e["page"], e["external"]) for e in current["entries"]] == [
        ("Velho", 0, False),
        ("Site", -1, True),
    ]
    entries = [
        {"level": 1, "title": "Velho renomeado", "page": 0, "source": 0},
        {"level": 2, "title": "Filho novo", "page": 2, "source": None},
        {"level": 1, "title": "Site", "page": -1, "source": 1},
    ]
    assert set_outline(doc, {"signature": current["signature"], "entries": entries}) == {
        "entries": 3
    }
    toc = doc.get_toc(simple=False)
    assert [row[:3] for row in toc] == [
        [1, "Velho renomeado", 1],
        [2, "Filho novo", 3],
        [1, "Site", -1],
    ]
    assert toc[2][3]["uri"] == "https://example.org"
    with pytest.raises(OldSchoolPDFError, match="mudaram"):
        set_outline(doc, {"signature": current["signature"], "entries": []})
    fresh = read_outline(doc)["signature"]
    for bad, message in (
        ([{"level": 2, "title": "x", "page": 0}], "recuado"),
        ([{"level": 1, "title": " ", "page": 0}], "título"),
        ([{"level": 1, "title": "x", "page": 99}], "inexistente"),
    ):
        with pytest.raises(OldSchoolPDFError, match=message):
            set_outline(doc, {"signature": fresh, "entries": bad})
    set_outline(doc, {"signature": fresh, "entries": []})
    assert doc.get_toc() == []


def test_outline_suggestion_uses_heading_sizes_and_skips_running_headers():
    doc = outline_document()
    entries = suggest_outline(doc)["entries"]
    assert [(e["level"], e["title"], e["page"]) for e in entries[:3]] == [
        (1, "Capítulo 1", 0),
        (2, "Seção 1.1", 0),
        (1, "Capítulo 2", 1),
    ]
    assert not any("cabeçalho" in e["title"] for e in entries)
    with pymupdf.open() as empty:
        empty.new_page()
        with pytest.raises(OldSchoolPDFError, match="OCR"):
            suggest_outline(empty)


def test_deleted_page_leaves_bookmark_without_target():
    doc = outline_document()
    doc.set_toc([[1, "A", 1], [1, "B", 3]])
    doc.delete_pages([2])
    entries = read_outline(doc)["entries"]
    assert entries[1]["page"] == -1 and not entries[1]["external"]


# Campos de formulário
@pytest.mark.parametrize("rotation", [0, 90])
def test_fields_are_created_filled_and_removed(rotation):
    doc = pymupdf.open()
    page = doc.new_page()
    page.set_rotation(rotation)
    text = add_field(page, {"kind": "text", "name": "nome completo", "region": (0.1, 0.1, 0.6, 0.15),
                            "value": "João Ção", "required": True, "font_size": 11})  # fmt: skip
    add_field(
        page, {"kind": "multiline", "name": "obs", "region": (0.1, 0.2, 0.6, 0.3), "value": "a\nb"}
    )
    add_field(
        page,
        {"kind": "checkbox", "name": "aceito", "region": (0.1, 0.35, 0.14, 0.38), "value": True},
    )
    add_field(page, {"kind": "choice", "name": "estado", "region": (0.1, 0.4, 0.4, 0.44),
                     "choices": ["São Paulo", "Paraná"]})  # fmt: skip
    with pytest.raises(OldSchoolPDFError, match="Já existe"):
        add_field(page, {"kind": "text", "name": "OBS", "region": (0.1, 0.5, 0.6, 0.55)})
    for bad, message in (
        ({"kind": "radio"}, "tipo"),
        ({"name": "a.b"}, "nome"),
        ({"region": (0.1, 0.1, 0.105, 0.105)}, "maior"),
        ({"kind": "choice", "choices": []}, "opções"),
        ({"kind": "choice", "choices": ["A", "a"]}, "repetidas"),
        ({"font_size": 13}, "tamanho"),
        ({"max_length": 3, "value": "longo"}, "limite"),
    ):
        values = {"kind": "text", "name": "outro", "region": (0.1, 0.6, 0.6, 0.65), **bad}
        with pytest.raises(OldSchoolPDFError, match=message):
            add_field(page, values)
    with pymupdf.open("pdf", doc.tobytes()) as saved:
        widgets = {w.field_name: w for w in saved[0].widgets()}
        assert widgets["nome completo"].field_value == "João Ção"
        assert widgets["nome completo"].field_flags & pymupdf.PDF_FIELD_IS_REQUIRED
        assert widgets["obs"].field_flags & pymupdf.PDF_TX_FIELD_IS_MULTILINE
        assert widgets["estado"].field_value == "São Paulo"
        if rotation:
            assert saved.xref_get_key(widgets["nome completo"].xref, "MK/R") == ("int", "90")
    remove_field(page, {"xref": text})
    assert "nome completo" not in {w.field_name for w in page.widgets()}
    with pytest.raises(OldSchoolPDFError, match="não está mais"):
        remove_field(page, {"xref": text})


# Continuação do texto em páginas novas
@pytest.mark.parametrize("rotation", [0, 90])
def test_text_that_does_not_fit_continues_on_new_pages(rotation):
    doc = pymupdf.open()
    page = doc.new_page(width=420, height=600)
    page.insert_text((40, 60), "Título do relatório", fontsize=16)
    page.insert_text((40, 100), "Parágrafo curto que será trocado.", fontsize=12)
    page.insert_text((40, 300), "Bloco vizinho que não pode mudar", fontsize=12)
    doc.new_page(width=420, height=600).insert_text((40, 60), "Página seguinte", fontsize=12)
    doc[0].set_rotation(rotation)
    block = next(b for b in read_blocks(doc[0]) if "curto" in b["text"])
    words = [f"palavra{n}" for n in range(300)]
    edit = {"key": block["key"], "runs": [dict(block["runs"][0], text=" ".join(words))]}
    with (
        pymupdf.open("pdf", doc.tobytes()) as refused,
        pytest.raises(OldSchoolPDFError, match="não cabe"),
    ):
        replace_blocks(refused, 0, [edit], {"shrink": "none"})
    report = replace_blocks(doc, 0, [edit], {"overflow": "new_page"})
    added = report["pages_added"]
    assert added >= 1 and report["scale"] == 1.0 and doc.page_count == 2 + added
    assert all(doc[i].rotation == rotation for i in range(added + 1))
    assert "Página seguinte" in doc[-1].get_text()
    assert "Bloco vizinho que não pode mudar" in " ".join(doc[0].get_text().split())
    found = [
        w for i in range(added + 1) for w in doc[i].get_text().split() if w.startswith("palavra")
    ]
    assert found == words
    block = next(b for b in read_blocks(doc[0]) if "Título" in b["text"])
    edit = {"key": block["key"], "runs": [dict(block["runs"][0], text="Outro")]}
    with pytest.raises(OldSchoolPDFError, match="continuação"):
        replace_blocks(doc, 0, [edit], {"overflow": "sim"})


# Fluxo pelo motor do processo leitor
def test_engine_applies_new_edits_with_undo_and_permissions(tmp_path):
    source = tmp_path / "base.pdf"
    outline_document().save(source)
    scratch = tmp_path / "trabalho"
    scratch.mkdir()
    engine = PdfEngine()
    engine.open(str(source))
    result = engine.edit("insert_blank", 0, {"where": "after", "size": "a4"}, str(scratch), False)
    assert result["page_count"] == 5 and result["page"] == 1
    result = engine.edit(
        "crop_pages",
        0,
        {"ranges": [(0, 0)], "mode": "auto", "margins": [5] * 4},
        str(scratch),
        False,
    )
    assert result["report"]["pages"] == 1
    result = engine.edit("resize_pages", 0, {"ranges": [(0, 0)], "size": "a5"}, str(scratch), False)
    assert result["report"]["pages"] == 1
    outline = engine.outline()
    entries = [{"level": 1, "title": "Início", "page": 0, "source": None}]
    engine.edit(
        "set_outline",
        0,
        {"signature": outline["signature"], "entries": entries},
        str(scratch),
        False,
    )
    assert engine.outline()["entries"][0]["title"] == "Início"
    assert engine.suggest_outline()["entries"]
    field = engine.edit(
        "add_field",
        0,
        {"kind": "checkbox", "name": "ok", "region": (0.1, 0.1, 0.2, 0.2)},
        str(scratch),
        False,
    )
    assert field["report"]["xref"]
    engine.edit("remove_field", 0, {"xref": field["report"]["xref"]}, str(scratch), False)
    engine.step(-1)
    assert engine.objects(0)["fields"]
    engine.close()

    locked = tmp_path / "restrito.pdf"
    with pymupdf.open(source) as doc:
        doc.save(locked, encryption=pymupdf.PDF_ENCRYPT_AES_256, owner_pw="dono", user_pw="",
                 permissions=pymupdf.PDF_PERM_PRINT | pymupdf.PDF_PERM_COPY)  # fmt: skip
    engine = PdfEngine()
    engine.open(str(locked))
    for action, values in (
        ("insert_blank", {"size": "same"}),
        ("crop_pages", {"ranges": [(0, 0)], "mode": "reset"}),
        ("resize_pages", {"ranges": [(0, 0)], "size": "a4"}),
        ("set_outline", {"signature": "", "entries": []}),
        ("add_field", {"kind": "text", "name": "x", "region": (0.1, 0.1, 0.5, 0.2)}),
        ("replace_text", {"blocks": [], "options": {"overflow": "new_page"}}),
    ):
        with pytest.raises(OldSchoolPDFError, match="permissões"):
            engine.edit(action, 0, values, str(scratch), False)
    engine.close()


def test_preview_shows_continuation_pages(tmp_path):
    source = tmp_path / "continua.pdf"
    with pymupdf.open() as doc:
        page = doc.new_page(width=420, height=600)
        page.insert_text((40, 100), "Parágrafo curto que será trocado.", fontsize=12)
        doc.save(source)
    engine = PdfEngine()
    engine.open(str(source))
    block = engine.text_blocks(0, 300, 400, 1.0)[0]["blocks"][0]
    edit = [{"key": block["key"], "runs": [dict(block["runs"][0], text="palavra " * 450)]}]
    options = {"overflow": "new_page"}
    first, first_pixels = engine.preview_text(0, edit, options, 300, 400, 1.0)
    assert first["report"]["pages_added"] >= 1 and first["report"]["view"] == 0
    second, second_pixels = engine.preview_text(0, edit, options, 300, 400, 1.0, view=1)
    assert second["report"]["view"] == 1 and second["frame"]["page"] == 1
    assert second_pixels != first_pixels
    clamped, _ = engine.preview_text(0, edit, options, 300, 400, 1.0, view=99)
    assert clamped["report"]["view"] == first["report"]["pages_added"]
    assert engine.document.page_count == 1
    engine.close()
