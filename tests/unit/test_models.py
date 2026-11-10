from pathlib import Path

import pytest

from docforge.domain.models import DocumentSession, PageReference, SignatureState


def test_sessions_have_independent_mutable_state(tmp_path):
    first = DocumentSession(tmp_path / "cópia 漢字 📝.pdf")
    second = DocumentSession(tmp_path / "second.pdf")
    first.page_map.append(PageReference(0))
    assert second.page_map == []
    assert first.session_id != second.session_id
    assert first.signature_state == SignatureState.UNKNOWN
    assert not first.dirty
    assert not first.source_path.exists()


@pytest.mark.parametrize("zoom", [0, -1, 9, float("nan"), float("inf")])
def test_session_rejects_invalid_initial_zoom(zoom):
    with pytest.raises(ValueError, match="Zoom"):
        DocumentSession(Path("never-opened.pdf"), zoom=zoom)


def test_working_copy_cannot_be_the_source(tmp_path):
    original = tmp_path / "original.pdf"
    original.write_bytes(b"user data untouched")
    with pytest.raises(ValueError, match="diferente"):
        DocumentSession(original, tmp_path / "sub" / ".." / "original.pdf")
    assert original.read_bytes() == b"user data untouched"


@pytest.mark.parametrize("index,rotation", [(-1, 0), (0, 45), (0, -90)])
def test_page_reference_invariants(index, rotation):
    with pytest.raises(ValueError):
        PageReference(index, rotation)
