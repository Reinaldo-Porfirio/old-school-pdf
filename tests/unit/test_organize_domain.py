from pathlib import Path

import pytest

from oldschoolpdf.domain.editing import (
    MAX_OUTLINE_DEPTH,
    check_levels,
    clean_title,
    field_name,
    normalize_levels,
    paper_size,
)
from oldschoolpdf.domain.errors import OldSchoolPDFError


def test_paper_sizes_and_orientation():
    width, height = paper_size("a4", "portrait")
    assert round(width, 1) == 595.3 and round(height, 1) == 841.9
    assert paper_size("a4", "landscape") == (height, width)
    assert paper_size("letter", "portrait") == (612.0, 792.0)
    for key, orientation in (("a3", "portrait"), ("a4", "deitado")):
        with pytest.raises(OldSchoolPDFError):
            paper_size(key, orientation)


def test_bookmark_titles_are_single_line():
    assert clean_title("  Capítulo\n1\t— Início  ") == "Capítulo 1 — Início"
    for bad in ("", "   ", None, "x" * 513):
        with pytest.raises(OldSchoolPDFError):
            clean_title(bad)


def test_levels_are_checked_and_normalized():
    check_levels([1, 2, 3, 2, 1, 2])
    for bad in ([2], [1, 3], [1, 0], [1, "2"]):
        with pytest.raises(OldSchoolPDFError):
            check_levels(bad)
    assert normalize_levels([3, 3, 1, 4, 2]) == [1, 2, 1, 2, 2]
    assert normalize_levels(list(range(1, 20)))[-1] == MAX_OUTLINE_DEPTH


def test_field_names():
    assert field_name("  Nome completo ") == "Nome completo"
    assert field_name("cpf_titular-2") == "cpf_titular-2"
    for bad in ("", "a.b", "nome/aluno", "x" * 121, 7):
        with pytest.raises(OldSchoolPDFError):
            field_name(bad)


@pytest.mark.skipif(not Path(r"C:\Windows\Fonts\cambria.ttc").exists(), reason="Sem Cambria")
def test_font_collections_are_indexed_by_their_first_face():
    from oldschoolpdf.infrastructure.system_fonts import describe_font

    assert describe_font(Path(r"C:\Windows\Fonts\cambria.ttc")) == (
        ("cambria", False, False),
        "Cambria",
    )
