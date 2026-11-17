"""Leitura, edição e sugestão dos marcadores (sumário) do PDF."""

import hashlib
import json
from collections import Counter

import pymupdf as pdf

from oldschoolpdf.domain.editing import (
    MAX_OUTLINE_ENTRIES,
    check_levels,
    clean_title,
)
from oldschoolpdf.domain.errors import OldSchoolPDFError

# Propriedades visuais de um marcador que sobrevivem à edição.
STYLE_KEYS = ("color", "bold", "italic", "collapse")
SUGGEST_PAGES = 1000
SUGGEST_LIMIT = 300
HEADING_RATIO = 1.15
MAX_HEADING_CHARS = 150
# Linhas que aparecem em muitas páginas são cabeçalhos ou rodapés repetidos.
REPEATED_SHARE = 0.3


def _raw(doc: pdf.Document) -> list:
    try:
        toc = doc.get_toc(simple=False)
    except (RuntimeError, ValueError):
        raise OldSchoolPDFError("Os marcadores deste PDF estão danificados.") from None
    if len(toc) > MAX_OUTLINE_ENTRIES:
        raise OldSchoolPDFError(
            f"Este PDF tem mais de {MAX_OUTLINE_ENTRIES} marcadores. A edição não está disponível."
        )
    return toc


def _entries(toc: list) -> list[dict]:
    entries = []
    for level, title, page, dest in toc:
        kind = dest.get("kind", pdf.LINK_NONE) if isinstance(dest, dict) else pdf.LINK_NONE
        entries.append(
            {
                "level": int(level),
                "title": " ".join(str(title).split())[:512] or "(sem título)",
                "page": page - 1 if page > 0 else -1,
                "external": kind in (pdf.LINK_URI, pdf.LINK_LAUNCH, pdf.LINK_GOTOR),
            }
        )
    return entries


def _signature(entries: list[dict]) -> str:
    encoded = json.dumps(entries, ensure_ascii=False, sort_keys=True).encode()
    return hashlib.sha1(encoded).hexdigest()[:20]


def read_outline(doc: pdf.Document) -> dict:
    entries = _entries(_raw(doc))
    return {"entries": entries, "signature": _signature(entries)}


def set_outline(doc: pdf.Document, values: dict) -> dict:
    """Recria o sumário. Marcadores mantidos guardam destino exato, cor e estilo."""
    toc = _raw(doc)
    if values.get("signature") != _signature(_entries(toc)):
        raise OldSchoolPDFError(
            "Os marcadores mudaram desde a abertura do editor. Abra-o novamente."
        )
    requested = values.get("entries")
    if not isinstance(requested, list) or len(requested) > MAX_OUTLINE_ENTRIES:
        raise OldSchoolPDFError("A lista de marcadores chegou em formato inválido.")
    check_levels([item.get("level") if isinstance(item, dict) else None for item in requested])
    count = doc.page_count
    result = []
    expected = []
    for number, item in enumerate(requested, 1):
        title = clean_title(item.get("title"))
        page = item.get("page")
        source = item.get("source")
        original = toc[source] if isinstance(source, int) and 0 <= source < len(toc) else None
        dest = original[3] if original and isinstance(original[3], dict) else {}
        same = original is not None and page == (original[2] - 1 if original[2] > 0 else -1)
        if same:
            # Destino original intacto: posição exata, links externos e ações nomeadas.
            kept = {key: value for key, value in dest.items() if key != "xref"}
            entry = [item["level"], title, original[2], kept]
            target = original[2]
        else:
            if not isinstance(page, int) or not 0 <= page < count:
                raise OldSchoolPDFError(f"O marcador {number} aponta para uma página inexistente.")
            style = {key: dest[key] for key in STYLE_KEYS if key in dest}
            entry = [item["level"], title, page + 1, {"kind": pdf.LINK_GOTO, **style}]
            target = page + 1
        result.append(entry)
        expected.append((item["level"], title, target))
    doc.set_toc(result, collapse=0)
    written = [(level, " ".join(title.split()), page) for level, title, page in doc.get_toc()]
    if written != [(level, title, page if page > 0 else -1) for level, title, page in expected]:
        raise OldSchoolPDFError("Os marcadores gravados não conferiram. Nada foi alterado.")
    return {"entries": len(result)}


def _line_text(line: dict) -> str:
    return " ".join("".join(span["text"] for span in line["spans"]).split())


def suggest_outline(doc: pdf.Document) -> dict:
    """Sugere marcadores pelos títulos: linhas curtas com fonte maior que o texto comum."""
    pages = min(doc.page_count, SUGGEST_PAGES)
    sizes: Counter = Counter()
    lines = []
    seen_on: dict[str, set[int]] = {}
    for number in range(pages):
        data = doc[number].get_text("dict", flags=pdf.TEXT_PRESERVE_WHITESPACE)
        for block in data["blocks"]:
            if block.get("type") != 0:
                continue
            for line in block["lines"]:
                text = _line_text(line)
                if not text:
                    continue
                size = max(round(span["size"] * 2) / 2 for span in line["spans"])
                for span in line["spans"]:
                    sizes[round(span["size"] * 2) / 2] += len(span["text"].strip())
                lines.append((number, block["number"], line["bbox"][1], size, text))
                seen_on.setdefault(text.casefold(), set()).add(number)
    if not sizes:
        raise OldSchoolPDFError(
            "O PDF não tem texto para sugerir marcadores. Digitalizações precisam de OCR."
        )
    body = sizes.most_common(1)[0][0]
    threshold = max(2, pages * REPEATED_SHARE)
    repeated = {key for key, where in seen_on.items() if len(where) > threshold}
    candidates = []
    for number, block, top, size, text in lines:
        if size < body * HEADING_RATIO or len(text) > MAX_HEADING_CHARS:
            continue
        if text.casefold() in repeated or sum(ch.isalpha() for ch in text) < 2:
            continue
        previous = candidates[-1] if candidates else None
        if previous and previous[:2] == (number, block) and previous[3] == size:
            # Título quebrado em duas linhas do mesmo bloco.
            candidates[-1] = (number, block, previous[2], size, previous[4] + " " + text)
        else:
            candidates.append((number, block, top, size, text))
    largest = sorted({candidate[3] for candidate in candidates}, reverse=True)[:3]
    levels = {size: index + 1 for index, size in enumerate(largest)}
    entries = []
    previous = 0
    for number, _block, _top, size, text in candidates:
        if size not in levels:
            continue
        level = min(levels[size], previous + 1)
        previous = level
        entries.append({"level": level, "title": text[:512], "page": number, "external": False})
        if len(entries) == SUGGEST_LIMIT:
            break
    return {"entries": entries, "scanned": pages}
