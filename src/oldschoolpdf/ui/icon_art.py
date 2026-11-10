"""Arte vetorial original dos ícones no estilo do Clássico 2000.

Cada ícone é um SVG 24x24 com degradês e contorno escuro, à maneira dos
programas de escritório do início dos anos 2000. Nenhum asset externo.
"""

DEFS = """<defs>
<linearGradient id="gB" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#bfe2ff"/><stop offset=".5" stop-color="#4c9cf0"/><stop offset="1" stop-color="#1957b8"/></linearGradient>
<linearGradient id="gY" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#fff6c2"/><stop offset=".55" stop-color="#ffd650"/><stop offset="1" stop-color="#e09a12"/></linearGradient>
<linearGradient id="gY2" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#ffe98a"/><stop offset="1" stop-color="#f0ad1c"/></linearGradient>
<linearGradient id="gG" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#ffffff"/><stop offset=".6" stop-color="#c9d0d8"/><stop offset="1" stop-color="#8e98a4"/></linearGradient>
<linearGradient id="gGr" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#d6f7b0"/><stop offset=".5" stop-color="#6cc43a"/><stop offset="1" stop-color="#2f8a16"/></linearGradient>
<linearGradient id="gR" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#ffc2b8"/><stop offset=".5" stop-color="#e8483a"/><stop offset="1" stop-color="#a51a10"/></linearGradient>
<linearGradient id="gO" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#ffe2b0"/><stop offset=".5" stop-color="#ff9a2e"/><stop offset="1" stop-color="#d0620a"/></linearGradient>
<linearGradient id="gP" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#ffffff"/><stop offset="1" stop-color="#d8e0ea"/></linearGradient>
<linearGradient id="gW" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#b07a3a"/><stop offset=".5" stop-color="#e2b07a"/><stop offset="1" stop-color="#8a5622"/></linearGradient>
<radialGradient id="gGlass" cx=".35" cy=".3" r=".8"><stop offset="0" stop-color="#ffffff"/><stop offset=".5" stop-color="#cfe9ff"/><stop offset="1" stop-color="#6aa8e0"/></radialGradient>
<radialGradient id="gLogo" cx=".35" cy=".25" r=".9"><stop offset="0" stop-color="#ffe7a0"/><stop offset=".45" stop-color="#ff9a1e"/><stop offset="1" stop-color="#b0420a"/></radialGradient>
</defs>"""


def _page(x: float = 5, y: float = 2, w: float = 14, h: float = 20) -> str:
    return (
        f'<path d="M{x} {y}h{w - 4}l4 4v{h - 4}h-{w}z" fill="url(#gP)" stroke="#5a6b80"/>'
        f'<path d="M{x + w - 4} {y}v4h4" fill="#eef2f7" stroke="#5a6b80"/>'
    )


_PAGE = _page()
_MAGNIFIER = (
    '<circle cx="10" cy="10" r="6.5" fill="url(#gGlass)" stroke="#2a3a4a" stroke-width="2"/>'
    '<path d="M15 15l6 6" stroke="#8a5a1a" stroke-width="3.5" stroke-linecap="round"/>'
)
_UNDO = (
    '<path d="M10 4 3 10l7 6v-4h4.5a4.5 4.5 0 0 1 0 9H12v2.5h2.5a7 7 0 0 0 0-14H10z" '
    'fill="url(#{fill})" stroke="{line}" stroke-linejoin="round"/>'
)
_SAVE = (
    '<rect x="3" y="3" width="18" height="18" rx="2" fill="url(#gB)" stroke="#123f7a"/>'
    '<rect x="7" y="3" width="10" height="6.5" fill="#eef3f9" stroke="#123f7a"/>'
    '<rect x="13.5" y="4.2" width="2" height="4" fill="#123f7a"/>'
    '<rect x="6" y="13" width="12" height="8" fill="#fff" stroke="#123f7a"/>'
    '<path d="M8 16h8M8 18.5h6" stroke="#99aabb"/>'
)
_IMAGE = (
    '<rect x="2" y="4" width="20" height="16" fill="#fff" stroke="#3a4a5a"/>'
    '<rect x="4" y="6" width="16" height="12" fill="url(#gGlass)"/>'
    '<path d="M4 18l5-6 4 4 3-3 4 5z" fill="url(#gGr)" stroke="#256a10" stroke-linejoin="round"/>'
    '<circle cx="16" cy="9" r="1.8" fill="#ffd650"/>'
)
_SHIELD = (
    '<path d="M12 2 4 5v6c0 5 3.5 9 8 11 4.5-2 8-6 8-11V5z" fill="url(#gB)" stroke="#123f7a" '
    'stroke-linejoin="round"/>'
    '<path d="M8 12l3 3 5-6" stroke="#fff" stroke-width="2.4" fill="none" stroke-linecap="round"/>'
)
_REDACT = (
    _PAGE + '<rect x="7" y="8" width="10" height="3" fill="#111"/>'
    '<rect x="7" y="13" width="7" height="3" fill="#111"/><path d="M7 18.5h9" stroke="#99aabb"/>'
)
_INFO = (
    '<circle cx="12" cy="12" r="10" fill="url(#gB)" stroke="#123f7a"/>'
    '<rect x="10.6" y="10" width="2.8" height="8" fill="#fff"/>'
    '<circle cx="12" cy="6.8" r="1.7" fill="#fff"/>'
)

ART: dict[str, str] = {
    "home": (
        '<path d="M12 3 2 11.5h3V21h5.5v-6h3v6H19v-9.5h3z" fill="url(#gO)" stroke="#8a3d06" '
        'stroke-linejoin="round"/>'
        '<rect x="15.5" y="4" width="2.6" height="5" fill="#a5522a" stroke="#6a2a08"/>'
    ),
    "open": (
        '<path d="M2 5h7l2 2h10v12H2z" fill="url(#gY2)" stroke="#97650a" stroke-linejoin="round"/>'
        '<path d="M2 19 4.8 10H23l-2.6 9z" fill="url(#gY)" stroke="#97650a" '
        'stroke-linejoin="round"/>'
    ),
    "save": _SAVE,
    "save_as": _SAVE + '<path d="M15 22l1-4 6-6 3 3-6 6z" fill="url(#gY)" stroke="#8a6a00" '
    'stroke-linejoin="round" transform="translate(-2 -1)"/>',
    "print": (
        '<rect x="6" y="2.5" width="12" height="7" fill="#fff" stroke="#5a6470"/>'
        '<rect x="2" y="9" width="20" height="9" rx="2" fill="url(#gG)" stroke="#3e4650"/>'
        '<circle cx="18.5" cy="12" r="1" fill="#33cc33"/>'
        '<rect x="6" y="14.5" width="12" height="7" fill="#fff" stroke="#5a6470"/>'
        '<path d="M8 17h8M8 19h6" stroke="#99aabb"/>'
    ),
    "undo": _UNDO.format(fill="gB", line="#123f7a"),
    "redo": '<g transform="translate(24 0) scale(-1 1)">'
    + _UNDO.format(fill="gGr", line="#256a10")
    + "</g>",
    "zoom_in": _MAGNIFIER + '<path d="M7 10h6M10 7v6" stroke="#1957b8" stroke-width="2"/>',
    "zoom_out": _MAGNIFIER + '<path d="M7 10h6" stroke="#1957b8" stroke-width="2"/>',
    "search": _MAGNIFIER
    + '<path d="M6.5 8.5a4 4 0 0 1 3-2.5" stroke="#fff" stroke-width="1.5" fill="none"/>',
    "select": (
        '<path d="M5 2v17l4.5-4 3 7 3-1.3-3-7H18z" fill="#fff" stroke="#111" '
        'stroke-linejoin="round"/>'
    ),
    "highlight": (
        '<rect x="2" y="19" width="13" height="3.5" fill="#ffee30" stroke="#b9a000"/>'
        '<path d="M14 2.5 21.5 10l-8.5 8.5-4.5 1 1-4.5z" fill="url(#gY)" stroke="#8a6a00" '
        'stroke-linejoin="round"/><path d="M9.5 15 13 18.5" stroke="#8a6a00"/>'
    ),
    "underline": (
        '<path d="M7 3v8a5 5 0 0 0 10 0V3" fill="none" stroke="#1957b8" stroke-width="2.6"/>'
        '<rect x="4" y="19" width="16" height="2.6" fill="#e8483a"/>'
    ),
    "comment": (
        '<path d="M3 3.5h18v13h-9l-5 4.5v-4.5H3z" fill="url(#gY)" stroke="#97650a" '
        'stroke-linejoin="round"/><path d="M6.5 8h11M6.5 11h8" stroke="#97650a"/>'
    ),
    "text": (
        '<rect x="3" y="4" width="18" height="16" fill="#fff" stroke="#3a4a5a"/>'
        '<path d="M8 8.5h8M12 8.5v8" stroke="#1957b8" stroke-width="2.6"/>'
        '<rect x="1.5" y="2.5" width="3" height="3" fill="#fff" stroke="#1957b8"/>'
        '<rect x="19.5" y="18.5" width="3" height="3" fill="#fff" stroke="#1957b8"/>'
    ),
    "stamp": (
        '<rect x="3.5" y="16" width="17" height="4.5" rx="1" fill="url(#gR)" stroke="#7a1a10"/>'
        '<path d="M9 16v-4.5a3 3 0 1 1 6 0V16z" fill="url(#gW)" stroke="#5a3410"/>'
        '<rect x="5" y="21" width="14" height="1.5" fill="#c8231a"/>'
    ),
    "rectangle": '<rect x="3" y="5" width="18" height="14" fill="url(#gB)" stroke="#123f7a"/>',
    "ellipse": '<ellipse cx="12" cy="12" rx="9.5" ry="7.5" fill="url(#gGr)" stroke="#256a10"/>',
    "image": _IMAGE,
    "merge": (
        '<rect x="2.5" y="2" width="10.5" height="14" fill="url(#gP)" stroke="#5a6b80"/>'
        '<rect x="7.5" y="6" width="10.5" height="14" fill="url(#gP)" stroke="#5a6b80"/>'
        '<circle cx="18" cy="18" r="5" fill="url(#gGr)" stroke="#256a10"/>'
        '<path d="M18 15v6M15 18h6" stroke="#fff" stroke-width="2.2"/>'
    ),
    "split": _PAGE
    + '<path d="M1.5 12.5h21" stroke="#dd2222" stroke-width="2" stroke-dasharray="3 2"/>'
    '<path d="M8 7h8M8 9h6M8 16h8M8 18h5" stroke="#99aabb"/>',
    "extract": _page(2, 2) + '<path d="M5 8h6M5 10h7M5 13h5" stroke="#99aabb"/>'
    '<path d="M12 12h5V8.5l6 5.5-6 5.5V16h-5z" fill="url(#gO)" stroke="#8a3d06" '
    'stroke-linejoin="round"/>',
    "extract_text": _page(2, 2)
    + '<path d="M12 12h5V8.5l6 5.5-6 5.5V16h-5z" fill="url(#gO)" stroke="#8a3d06" '
    'stroke-linejoin="round"/>'
    '<path d="M4.5 7h7M8 7v9" stroke="#1957b8" stroke-width="2"/>',
    "reorder": (
        '<rect x="3" y="2" width="11" height="8" fill="url(#gP)" stroke="#5a6b80"/>'
        '<rect x="3" y="14" width="11" height="8" fill="url(#gP)" stroke="#5a6b80"/>'
        '<path d="M5 5h7M5 7h5M5 17h7M5 19h5" stroke="#99aabb"/>'
        '<path d="M19 3l3.5 4H20v10h2.5L19 21l-3.5-4H18V7h-2.5z" fill="url(#gGr)" '
        'stroke="#256a10" stroke-linejoin="round"/>'
    ),
    "continuous": (
        '<rect x="5" y="1" width="14" height="10" fill="url(#gP)" stroke="#5a6b80"/>'
        '<rect x="5" y="13" width="14" height="10" fill="url(#gP)" stroke="#5a6b80"/>'
        '<path d="M7.5 4h9M7.5 6.5h7M7.5 16h9M7.5 18.5h7" stroke="#99aabb"/>'
    ),
    "fit": _page(6, 3, 12, 18)
    + '<path d="M2 12h3M19 12h3M3.5 10.5 2 12l1.5 1.5M20.5 10.5 22 12l-1.5 1.5" '
    'stroke="#1957b8" stroke-width="1.6" fill="none"/>',
    "rotate": (
        '<path d="M19 12a7 7 0 1 1-2.1-5" fill="none" stroke="#2f8a16" stroke-width="3"/>'
        '<path d="M21.5 2.5v7h-7z" fill="url(#gGr)" stroke="#256a10" stroke-linejoin="round"/>'
    ),
    "remove": _PAGE + '<circle cx="17" cy="17" r="5.5" fill="url(#gR)" stroke="#7a1a10"/>'
    '<path d="M14.5 14.5l5 5M19.5 14.5l-5 5" stroke="#fff" stroke-width="2"/>',
    "lock": (
        '<path d="M7 11V8a5 5 0 0 1 10 0v3" fill="none" stroke="#6a7480" stroke-width="2.6"/>'
        '<rect x="4" y="11" width="16" height="11" rx="2" fill="url(#gY)" stroke="#8a6a00"/>'
        '<circle cx="12" cy="15.5" r="1.8" fill="#6a4a00"/>'
        '<path d="M12 16.5v3" stroke="#6a4a00" stroke-width="1.6"/>'
    ),
    "signature": (
        '<path d="M2.5 20c3-4 4.5 1.5 7-1.5s3.5.5 6-1" fill="none" stroke="#1b3d8f" '
        'stroke-width="1.8" stroke-linecap="round"/>'
        '<path d="M15 2.5l6.5 6.5-8 8-4.5 1 1-4.5z" fill="url(#gB)" stroke="#123f7a" '
        'stroke-linejoin="round"/>'
    ),
    "redaction": _REDACT,
    "metadata": _PAGE + '<circle cx="16" cy="16" r="5.5" fill="url(#gB)" stroke="#123f7a"/>'
    '<path d="M16 14.5v5" stroke="#fff" stroke-width="2"/>'
    '<circle cx="16" cy="12.6" r="1.1" fill="#fff"/>',
    "ocr": _PAGE + '<path d="M9 16.5l2.6-8h.8l2.6 8M10 14h4" stroke="#1957b8" stroke-width="1.8" '
    'fill="none"/><path d="M2 12.5h20" stroke="#25c22a" stroke-width="1.6"/>',
    "form": (
        '<rect x="3" y="2.5" width="18" height="19" fill="url(#gP)" stroke="#5a6b80"/>'
        '<rect x="5.5" y="5.5" width="4" height="4" fill="#fff" stroke="#3a4a5a"/>'
        '<path d="M6 7.5l1.4 1.4L11 5" stroke="#2f8a16" stroke-width="1.8" fill="none"/>'
        '<rect x="5.5" y="12" width="4" height="4" fill="#fff" stroke="#3a4a5a"/>'
        '<path d="M11.5 7.5h7M11.5 14h7M5.5 19h13" stroke="#8a9ab0" stroke-width="1.4"/>'
    ),
    "document": (
        '<path d="M5 2h10l5 5v15H5z" fill="url(#gP)" stroke="#5a6b80"/>'
        '<path d="M15 2v5h5" fill="#eef2f7" stroke="#5a6b80"/>'
        '<rect x="2.5" y="11.5" width="15" height="6.5" rx="1" fill="url(#gR)" stroke="#7a1a10"/>'
        '<path d="M5 13.3v3.2M5 13.3h1.5a.9.9 0 0 1 0 1.8H5M8.6 13.3v3.2h.9a1.6 1.6 0 0 0 '
        '0-3.2zM12.6 16.5v-3.2h2.2M12.6 14.9h1.8" stroke="#fff" stroke-width=".9" fill="none"/>'
    ),
    "settings": (
        '<circle cx="12" cy="12" r="8" fill="none" stroke="#5a6470" stroke-width="4.5" '
        'stroke-dasharray="3.1 3.2"/>'
        '<circle cx="12" cy="12" r="7" fill="url(#gG)" stroke="#3e4650"/>'
        '<circle cx="12" cy="12" r="2.8" fill="#fff" stroke="#3e4650"/>'
    ),
    "help": (
        '<circle cx="12" cy="12" r="10" fill="url(#gB)" stroke="#123f7a"/>'
        '<path d="M8.8 9a3.3 3.3 0 1 1 4.6 3c-1 .5-1.4 1-1.4 2.2" fill="none" stroke="#fff" '
        'stroke-width="2.4" stroke-linecap="round"/><circle cx="12" cy="17.6" r="1.4" fill="#fff"/>'
    ),
    "info": _INFO,
    "shield": _SHIELD,
    "batch": (
        '<rect x="6" y="2" width="14" height="16" fill="url(#gP)" stroke="#5a6b80"/>'
        '<rect x="4" y="4" width="14" height="16" fill="url(#gP)" stroke="#5a6b80"/>'
        '<rect x="2" y="6" width="14" height="16" fill="url(#gP)" stroke="#5a6b80"/>'
        '<path d="M5 11h8M5 14h8M5 17h5" stroke="#99aabb"/>'
    ),
    "compress": _PAGE
    + '<path d="M12 4v5M9.5 6.5 12 9l2.5-2.5M12 20v-5M9.5 17.5 12 15l2.5 2.5" stroke="#d0620a" '
    'stroke-width="1.8" fill="none"/><path d="M8 12h8" stroke="#5a6b80" stroke-width="1.6"/>',
    "close": (
        '<path d="M5 5l14 14M19 5 5 19" stroke="#7a1a10" stroke-width="4.2" '
        'stroke-linecap="round"/>'
        '<path d="M5 5l14 14M19 5 5 19" stroke="#e8483a" stroke-width="2.4" '
        'stroke-linecap="round"/>'
    ),
    "next": (
        '<circle cx="12" cy="12" r="10" fill="url(#gB)" stroke="#123f7a"/>'
        '<path d="M10 6.5 15.5 12 10 17.5z" fill="#fff"/>'
    ),
    "previous": (
        '<circle cx="12" cy="12" r="10" fill="url(#gB)" stroke="#123f7a"/>'
        '<path d="M14 6.5 8.5 12l5.5 5.5z" fill="#fff"/>'
    ),
}

# Nomes de comandos que reaproveitam um desenho existente.
ALIASES = {
    "images": "image",
    "insert_image": "image",
    "images_pdf": "image",
    "extract_images": "image",
    "remove_object": "remove",
    "export_redaction": "redaction",
    "verify_signatures": "shield",
    "capabilities": "settings",
    "password": "lock",
}

LOGO = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">
<defs>
<linearGradient id="p" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#ffffff"/><stop offset="1" stop-color="#d8e0ea"/></linearGradient>
<radialGradient id="s" cx=".35" cy=".25" r=".9"><stop offset="0" stop-color="#ffe7a0"/><stop offset=".45" stop-color="#ff9a1e"/><stop offset="1" stop-color="#b0420a"/></radialGradient>
</defs>
<path d="M6 2h14l7 7v21H6z" fill="url(#p)" stroke="#2a3a55" stroke-width="1.4"/>
<path d="M20 2v7h7" fill="#e6ecf3" stroke="#2a3a55" stroke-width="1.4"/>
<path d="M10 10h8M10 13.5h12M10 17h7" stroke="#8aa0bb" stroke-width="1.6"/>
<circle cx="19" cy="22" r="7.5" fill="url(#s)" stroke="#7a2a06" stroke-width="1.4"/>
<path d="m19 17.2 1.5 3 3.3.4-2.4 2.3.6 3.3-3-1.6-3 1.6.6-3.3-2.4-2.3 3.3-.4z" fill="#fff6d0" stroke="#8a3d06" stroke-width=".7"/>
</svg>"""


def svg_for(kind: str) -> str:
    """Devolve o SVG completo do comando, com o ícone de informação como reserva."""
    body = ART.get(ALIASES.get(kind, kind), _INFO)
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">{DEFS}{body}</svg>'
