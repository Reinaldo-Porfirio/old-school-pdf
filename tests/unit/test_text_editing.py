import pytest

from oldschoolpdf.domain.errors import OldSchoolPDFError
from oldschoolpdf.domain.text_editing import (
    clean_font_name,
    compare_form,
    css_color,
    detect_alignment,
    font_family_key,
    join_lines,
    validate_text,
)


@pytest.mark.parametrize(
    "name, key",
    [
        ("ABCDEF+Arial-BoldMT", "arial"),
        ("TimesNewRomanPS-BoldItalicMT", "timesnewroman"),
        ("TimesNewRomanPSMT", "timesnewroman"),
        ("Calibri,Bold", "calibri"),
        ("ArialNarrow-Bold", "arialnarrow"),
        ("Segoe UI", "segoeui"),
        ("Helvetica", "helvetica"),
    ],
)
def test_font_family_key_matches_pdf_and_system_names(name, key):
    assert font_family_key(name) == key


def test_clean_font_name_drops_subset_prefix():
    assert clean_font_name("QWERTY+Georgia-Italic") == "Georgia-Italic"
    assert clean_font_name("") == "Desconhecida"


def test_join_lines_rebuilds_paragraphs_and_hyphenation():
    lines = ["É preciso consi-", "derar a primeira etapa.", "Segundo parágrafo aqui", "continua."]
    fill = [1.0, 0.5, 1.0, 0.3]
    assert join_lines(lines, fill) == (
        "É preciso considerar a primeira etapa.\nSegundo parágrafo aqui continua."
    )
    # Hífen de palavra composta, seguido de maiúscula, é mantido.
    assert join_lines(["Rio-", "Grande"], [1.0, 0.4]) == "Rio- Grande"


def test_detect_alignment():
    assert detect_alignment([(10, 200)], 10, 200) == "left"
    assert detect_alignment([(10, 200), (10, 120)], 10, 200) == "left"
    assert detect_alignment([(40, 160), (70, 130)], 40, 160) == "center"
    assert detect_alignment([(60, 200), (120, 200)], 10, 200) == "right"
    assert detect_alignment([(10, 200), (10, 200), (10, 90)], 10, 200) == "justify"


def test_validate_text_accepts_portuguese_and_rejects_unsafe_input():
    assert validate_text("Ação\r\n€ — ñ\tfim") == "Ação\n€ — ñ    fim"
    with pytest.raises(OldSchoolPDFError, match="controle"):
        validate_text("abc\x07")
    with pytest.raises(OldSchoolPDFError, match="direita para a esquerda"):
        validate_text("שלום")
    with pytest.raises(OldSchoolPDFError, match="até"):
        validate_text("x" * 4001)


def test_compare_form_and_css_color():
    assert compare_form("Texto  com\n  espaços­") == "Texto com espaços"
    assert css_color(0x1F3556) == "#1f3556"
    assert css_color(-5) == "#000000"
