"""Fontes instaladas no sistema que podem substituir as fontes em subconjunto do PDF.

Lê só o diretório de tabelas, a tabela "name" e a "OS/2" de cada arquivo, sem
carregar a fonte inteira. Fontes cuja licença proíbe incorporação ou subconjunto
ficam fora do índice.
"""

import hashlib
import os
import struct
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from oldschoolpdf.domain.text_editing import TextStyle, clean_font_name, font_family_key

MAX_FONT_BYTES = 40 * 1024 * 1024
MAX_FONT_FILES = 4000
# Fontes padrão do PDF e as equivalentes que acompanham o Windows.
ALIASES = {
    "helvetica": "arial",
    "helv": "arial",
    "arialmt": "arial",
    "times": "timesnewroman",
    "timesroman": "timesnewroman",
    "tiro": "timesnewroman",
    "courier": "couriernew",
    "cour": "couriernew",
}
SERIF_HINTS = ("times", "georgia", "garamond", "cambria", "bookantiqua", "palatino", "serif")
MONO_HINTS = ("courier", "consolas", "mono", "lucidaconsole")


@dataclass(frozen=True, slots=True)
class FontChoice:
    """Fonte que será usada no texto novo e como explicá-la ao usuário."""

    css: str
    path: str | None
    label: str
    exact: bool


def font_folders() -> list[Path]:
    folders = []
    windows = os.environ.get("WINDIR") or os.environ.get("SYSTEMROOT")
    if windows:
        folders.append(Path(windows) / "Fonts")
    if local := os.environ.get("LOCALAPPDATA"):
        folders.append(Path(local) / "Microsoft" / "Windows" / "Fonts")
    return [folder for folder in folders if folder.is_dir()]


def _tables(stream) -> dict[bytes, tuple[int, int]]:
    header = stream.read(12)
    if header[:4] == b"ttcf":
        # Coleção (.ttc): vale a primeira fonte, a mesma que o MuPDF carrega do arquivo.
        # Os deslocamentos das tabelas de cada fonte já contam do início do arquivo.
        first = stream.read(4)
        if len(header) < 12 or len(first) < 4 or not struct.unpack(">I", header[8:12])[0]:
            return {}
        stream.seek(struct.unpack(">I", first)[0])
        header = stream.read(12)
    if len(header) < 12 or header[:4] not in (b"\x00\x01\x00\x00", b"OTTO", b"true"):
        return {}
    count = struct.unpack(">H", header[4:6])[0]
    records = stream.read(16 * count)
    tables = {}
    for index in range(min(count, len(records) // 16)):
        tag, _, offset, length = struct.unpack(">4sIII", records[16 * index : 16 * index + 16])
        tables[tag] = (offset, length)
    return tables


def _names(stream, offset: int, length: int) -> dict[int, str]:
    """Nomes 1, 2, 16 e 17, preferindo o inglês dos EUA entre as traduções."""
    stream.seek(offset)
    data = stream.read(min(length, 256 * 1024))
    if len(data) < 6:
        return {}
    _, count, storage = struct.unpack(">HHH", data[:6])
    best: dict[int, tuple[int, str]] = {}
    for index in range(count):
        start = 6 + 12 * index
        if start + 12 > len(data):
            break
        platform, encoding, language, name_id, size, position = struct.unpack(
            ">HHHHHH", data[start : start + 12]
        )
        if name_id not in (1, 2, 16, 17):
            continue
        raw = data[storage + position : storage + position + size]
        if platform == 3 and encoding in (0, 1, 10):
            rank = 0 if language == 0x0409 else 2
            text = raw.decode("utf-16-be", "ignore")
        elif platform == 1 and encoding == 0 and language == 0:
            rank = 1
            text = raw.decode("mac_roman", "ignore")
        else:
            continue
        if text and (name_id not in best or rank < best[name_id][0]):
            best[name_id] = (rank, text)
    return {name_id: text for name_id, (_, text) in best.items()}


def describe_font(path: Path) -> tuple[tuple[str, bool, bool], str] | None:
    """Chave (família, negrito, itálico) e nome legível, ou None se não puder ser embutida."""
    try:
        if path.stat().st_size > MAX_FONT_BYTES:
            return None
        with path.open("rb") as stream:
            tables = _tables(stream)
            if b"name" not in tables or b"OS/2" not in tables:
                return None
            names = _names(stream, *tables[b"name"])
            offset, length = tables[b"OS/2"]
            if length < 64:
                return None
            stream.seek(offset)
            os2 = stream.read(64)
    except (OSError, struct.error):
        return None
    fs_type = struct.unpack(">H", os2[8:10])[0]
    selection = struct.unpack(">H", os2[62:64])[0]
    # Bit 1 isolado: licença restrita. 0x100: sem subconjunto. 0x200: só bitmap.
    if fs_type & 0x000F == 0x0002 or fs_type & 0x0300:
        return None
    family = names.get(16) or names.get(1)
    if not family:
        return None
    subfamily = (names.get(17) or names.get(2) or "").lower()
    bold = bool(selection & 0x20) or "bold" in subfamily
    italic = bool(selection & 0x01) or "italic" in subfamily or "oblique" in subfamily
    plain = subfamily in ("", "regular", "normal", "roman", "book", "bold", "italic", "bold italic")
    key = font_family_key(family) if plain else font_family_key(family + subfamily)
    regular = subfamily in ("", "regular", "normal", "roman", "book")
    display = family if regular else f"{family} {(names.get(17) or names.get(2) or '').strip()}"
    return (key, bold, italic), display.strip()


@lru_cache(maxsize=1)
def system_fonts() -> dict[tuple[str, bool, bool], tuple[str, str]]:
    """Índice (família, negrito, itálico) -> (arquivo, nome), montado uma vez por processo."""
    index: dict[tuple[str, bool, bool], tuple[str, str]] = {}
    files = 0
    for folder in font_folders():
        try:
            entries = sorted(folder.iterdir())
        except OSError:
            continue
        for path in entries:
            if path.suffix.lower() not in (".ttf", ".otf", ".ttc"):
                continue
            files += 1
            if files > MAX_FONT_FILES:
                return index
            described = describe_font(path)
            if described and described[0][0]:
                index.setdefault(described[0], (str(path), described[1]))
    return index


def _generic(style: TextStyle, key: str) -> tuple[str, str]:
    if style.mono or any(hint in key for hint in MONO_HINTS):
        return "monospace", "fonte padrão monoespaçada"
    if style.serif or any(hint in key for hint in SERIF_HINTS):
        return "serif", "fonte padrão com serifa"
    return "sans-serif", "fonte padrão sem serifa"


def resolve_font(style: TextStyle, bold: bool, italic: bool, *, use_system: bool) -> FontChoice:
    """Escolhe a fonte do texto novo: a mesma família instalada, ou uma padrão parecida."""
    key = font_family_key(style.font)
    key = ALIASES.get(key, key)
    if use_system and key:
        fonts = system_fonts()
        for wanted, exact in (((key, bold, italic), True), ((key, False, False), False)):
            found = fonts.get(wanted)
            if found:
                path, name = found
                original = clean_font_name(style.font)
                label = f"{original} → {name}" if exact else f"{original} → {name} (sem ênfase)"
                css = "sys" + hashlib.sha1(path.encode("utf-8")).hexdigest()[:10]
                return FontChoice(css, path, label, exact)
    css, description = _generic(style, key)
    return FontChoice(css, None, f"{clean_font_name(style.font)} → {description}", False)
