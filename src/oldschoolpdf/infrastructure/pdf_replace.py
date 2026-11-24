"""Localizar e substituir no texto original, usando o motor de edição de texto.

Cada ocorrência pertence a um bloco de texto da página. A substituição monta o texto novo
do bloco, mantendo o estilo do trecho onde a ocorrência começa, e passa pelas mesmas
verificações da edição manual (vizinhos intactos, texto conferido, pixels de fora iguais).
"""

import re
from dataclasses import asdict, dataclass, field, replace

import pymupdf

from oldschoolpdf.domain.errors import OldSchoolPDFError
from oldschoolpdf.domain.text_editing import MAX_EDIT_BLOCKS, TextRun
from oldschoolpdf.domain.viewer import MAX_QUERY_LENGTH
from oldschoolpdf.infrastructure.pdf_editing import indices
from oldschoolpdf.infrastructure.pdf_text_edit import read_blocks, replace_blocks

MAX_FIND_RESULTS = 500
MAX_FIND_PAGES = 200
MAX_REPLACE_ITEMS = 500
MAX_REPLACE_PAGES = 60
MAX_REPLACEMENT = 400
CONTEXT = 40
# Na substituição em lote, o texto pode usar o espaço livre ao lado e reduzir até 85%.
REPLACE_OPTIONS = {"shrink": "light", "expand": False, "system_fonts": True, "overflow": "none"}


class PageFailure(OldSchoolPDFError):
    """A página ficou pela metade; o motor recomeça numa cópia nova sem o trecho que falhou.

    Sem `key`, a falha veio de vários blocos gravados juntos: na próxima tentativa, a página
    é refeita bloco a bloco para descobrir qual deles não cabe.
    """

    def __init__(self, page: int, message: str, key: str | None = None, text: str = "") -> None:
        super().__init__(message)
        self.page = page
        self.key = key
        self.text = text


@dataclass
class ReplaceState:
    """O que as tentativas anteriores aprenderam: páginas bloco a bloco e trechos com falha."""

    split: set[int] = field(default_factory=set)
    failed: dict[tuple[int, str], dict] = field(default_factory=dict)

    def learn(self, failure: PageFailure) -> None:
        if failure.key is None:
            self.split.add(failure.page)
        else:
            self.failed[(failure.page, failure.key)] = _failure(
                failure.page, failure.text, str(failure)
            )


def _failure(page: int, text: str, reason: str) -> dict:
    return {"page": page + 1, "text": text, "reason": reason}


def search_pattern(values: dict) -> re.Pattern:
    query = values.get("query")
    if not isinstance(query, str) or len(query) > MAX_QUERY_LENGTH or not query.split():
        raise OldSchoolPDFError("Escreva o texto que deseja localizar.")
    body = r"\s+".join(re.escape(part) for part in query.split())
    if values.get("word"):
        body = rf"(?<!\w){body}(?!\w)"
    return re.compile(body, 0 if values.get("case") else re.IGNORECASE)


def _candidate(page: pymupdf.Page, pattern: re.Pattern) -> bool:
    """Filtro rápido: o texto da página, com e sem hifenização, contém a busca?"""
    text = page.get_text("text")
    return any(
        pattern.search(" ".join(variant.split()))
        for variant in (text, re.sub(r"-\s*\n\s*", "", text))
    )


def find_text(doc: pymupdf.Document, values: dict) -> dict:
    pattern = search_pattern(values)
    selected = indices(values["ranges"], doc.page_count)
    items = []
    pages = 0
    truncated = False
    for number in selected:
        page = doc[number]
        if not _candidate(page, pattern):
            continue
        if pages == MAX_FIND_PAGES:
            truncated = True
            break
        pages += 1
        for block in read_blocks(page):
            text = block["text"]
            for match in pattern.finditer(text):
                if len(items) == MAX_FIND_RESULTS:
                    truncated = True
                    break
                start, end = match.span()
                items.append(
                    {
                        "page": number,
                        "key": block["key"],
                        "start": start,
                        "end": end,
                        "before": " ".join(text[max(0, start - CONTEXT) : start].split()),
                        "match": text[start:end],
                        "after": " ".join(text[end : end + CONTEXT].split()),
                        "editable": block["editable"],
                        "reason": block["reason"],
                    }
                )
            if truncated:
                break
        if truncated:
            break
    return {"items": items, "truncated": truncated}


def splice(runs: list[TextRun], start: int, end: int, replacement: str) -> list[TextRun]:
    """Troca o trecho [start, end) do texto dos trechos, com o estilo de onde ele começa."""
    result = []
    position = 0
    inserted = False
    for run in runs:
        first, last = position, position + len(run.text)
        position = last
        if last <= start or first >= end:
            result.append(run)
            continue
        text = run.text[: max(0, start - first)]
        if not inserted:
            text += replacement
            inserted = True
        if end < last:
            text += run.text[end - first :]
        if text:
            result.append(replace(run, text=text))
    return result


def _replacement(values: dict) -> str:
    value = values.get("replacement")
    if not isinstance(value, str) or len(value) > MAX_REPLACEMENT:
        raise OldSchoolPDFError(f"O texto novo aceita até {MAX_REPLACEMENT} caracteres.")
    if "\n" in value or "\r" in value:
        raise OldSchoolPDFError("O texto novo precisa ficar numa linha só.")
    return value


def _groups(values: dict, count: int) -> dict[int, dict[str, list[tuple[int, int]]]]:
    raw = values.get("items")
    if not isinstance(raw, list) or not 1 <= len(raw) <= MAX_REPLACE_ITEMS:
        raise OldSchoolPDFError(f"Marque de 1 a {MAX_REPLACE_ITEMS} ocorrências.")
    groups: dict[int, dict[str, list[tuple[int, int]]]] = {}
    for item in raw:
        try:
            page, key = int(item["page"]), str(item["key"])
            start, end = int(item["start"]), int(item["end"])
        except (KeyError, TypeError, ValueError):
            raise OldSchoolPDFError("A lista de ocorrências chegou em formato inválido.") from None
        if not 0 <= page < count or not 0 <= start < end:
            raise OldSchoolPDFError("A lista de ocorrências chegou em formato inválido.")
        groups.setdefault(page, {}).setdefault(key, []).append((start, end))
    if len(groups) > MAX_REPLACE_PAGES:
        raise OldSchoolPDFError(
            f"Substitua em até {MAX_REPLACE_PAGES} páginas por vez. Desmarque algumas."
        )
    return groups


def replace_matches(doc: pymupdf.Document, values: dict, state: ReplaceState) -> dict:
    """Substitui as ocorrências marcadas, página por página.

    Um bloco que não pode ser alterado gera `PageFailure`; o motor recomeça numa cópia nova
    sem ele, guardando o que aprendeu em `state`.
    """
    pattern = search_pattern(values)
    replacement = _replacement(values)
    groups = _groups(values, doc.page_count)
    pages = items = 0
    skipped = []
    for number in sorted(groups):
        blocks = {block["key"]: block for block in read_blocks(doc[number])}
        edits = []
        for key, spans in groups[number].items():
            if (number, key) in state.failed:
                continue
            block = blocks.get(key)
            if block is None or not block["editable"]:
                reason = block["reason"] if block else "O texto da página mudou. Localize de novo."
                skipped.append(_failure(number, block["text"][:60] if block else "", reason))
                continue
            text = block["text"]
            runs = [TextRun(**run) for run in block["runs"]]
            # Do fim para o começo, as posições anteriores continuam valendo.
            ordered = sorted(set(spans), reverse=True)
            for later, earlier in zip(ordered, ordered[1:], strict=False):
                if earlier[1] > later[0]:
                    raise OldSchoolPDFError("Há ocorrências sobrepostas na lista.")
            if any(
                (match := pattern.search(text, start)) is None or match.span() != (start, end)
                for start, end in ordered
            ):
                skipped.append(
                    _failure(number, text[:60], "O texto da página mudou. Localize de novo.")
                )
                continue
            for start, end in ordered:
                runs = splice(runs, start, end, replacement)
            edit = {"key": key, "runs": [asdict(run) for run in runs]}
            edits.append((key, edit, len(ordered), text[:60]))
        if not edits:
            continue
        if number in state.split or len(edits) == 1:
            for key, edit, count, text in edits:
                try:
                    replace_blocks(doc, number, [edit], REPLACE_OPTIONS)
                except OldSchoolPDFError as error:
                    raise PageFailure(number, str(error), key, text) from None
                items += count
        else:
            try:
                for index in range(0, len(edits), MAX_EDIT_BLOCKS):
                    chunk = [edit for _, edit, _, _ in edits[index : index + MAX_EDIT_BLOCKS]]
                    replace_blocks(doc, number, chunk, REPLACE_OPTIONS)
            except OldSchoolPDFError as error:
                raise PageFailure(number, str(error)) from None
            items += sum(count for _, _, count, _ in edits)
        pages += 1
    failed = sorted([*state.failed.values(), *skipped], key=lambda item: item["page"])
    return {"pages": pages, "items": items, "failed": failed}
