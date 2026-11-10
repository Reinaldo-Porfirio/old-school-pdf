"""Transformações de cópias e auditoria da saída no processo do PDF."""

import math
import os
from collections import defaultdict
from collections.abc import Callable
from pathlib import Path

import pymupdf as pdf

from docforge.domain.errors import DocForgeError
from docforge.domain.security import (
    MAX_REDACTION_AREAS,
    MAX_REDACTION_PAGES,
    MAX_REDACTION_PIXELS,
    METADATA_FIELDS,
    REDACTION_DPI,
    RedactionArea,
    validate_passwords,
)
from docforge.infrastructure.pdf_ocr import raster
from docforge.infrastructure.pdf_storage import check_stage, open_pdf, save_validated

PERMISSION_BITS = {
    "print": pdf.PDF_PERM_PRINT | pdf.PDF_PERM_PRINT_HQ,
    "copy": pdf.PDF_PERM_COPY,
    "modify": pdf.PDF_PERM_MODIFY,
    "annotate": pdf.PDF_PERM_ANNOTATE,
    "form": pdf.PDF_PERM_FORM,
    "assemble": pdf.PDF_PERM_ASSEMBLE,
}
PERMISSION_MASK = sum(PERMISSION_BITS.values())
Progress = Callable[[int, int, str], None]


def protected(document: pdf.Document) -> bool:
    return bool((document.metadata or {}).get("encryption"))


def require_owner(document: pdf.Document, authenticated: bool, password: str) -> None:
    if (
        protected(document)
        and not authenticated
        and (not password or not document.authenticate(password) & 4)
    ):
        raise DocForgeError("A senha de proprietário do PDF atual é necessária.")


def strip_metadata(
    document: pdf.Document,
    stage: Path,
    password: str | None,
    fields: list[str],
    xml: bool,
) -> str:
    selected = set(fields)
    if selected - METADATA_FIELDS.keys() or not (selected or xml):
        raise DocForgeError("Selecione os metadados que deseja remover.")
    if selected == METADATA_FIELDS.keys():
        document.set_metadata({})
    elif selected:
        document.set_metadata(dict.fromkeys(selected))
    if xml:
        document.del_xml_metadata()
    save_validated(document, stage, password, compact=True)
    with open_pdf(stage, password) as copy:
        metadata = copy.metadata or {}
        if (
            any(metadata.get(field) for field in selected)
            or (selected == METADATA_FIELDS.keys() and copy.xref_get_key(-1, "Info")[0] != "null")
            or (xml and copy.get_xml_metadata())
        ):
            raise DocForgeError("A saída ainda contém metadados selecionados para remoção.")
    return "Metadados selecionados removidos e conferidos na cópia"


def encrypt_copy(
    document: pdf.Document, stage: Path, user: str, owner: str, allowed: list[str]
) -> str:
    validate_passwords(user, owner)
    selected = set(allowed)
    if selected - PERMISSION_BITS.keys():
        raise DocForgeError("Há permissões de PDF desconhecidas.")
    permissions = sum(PERMISSION_BITS[key] for key in selected)
    check_stage(stage)
    document.save(
        stage,
        encryption=pdf.PDF_ENCRYPT_AES_256,
        user_pw=user,
        owner_pw=owner,
        permissions=permissions | pdf.PDF_PERM_ACCESSIBILITY,
        garbage=1,
        deflate=True,
    )
    with stage.open("r+b") as stream:
        os.fsync(stream.fileno())
    with open_pdf(stage) as output:
        if (
            not output.needs_pass
            or output.authenticate(user) != 2
            or (output.permissions & PERMISSION_MASK) != permissions
            or "256-bit AES" not in (output.metadata or {}).get("encryption", "")
            or output.is_repaired
            or output.page_count != document.page_count
            or not output.authenticate(owner) & 4
        ):
            raise DocForgeError("A saída não passou na validação de senhas e permissões.")
        output.load_page(0)
    return "Cópia AES-256 com senhas e permissões conferidas"


def _pixel_bounds(pixmap: pdf.Pixmap, area: RedactionArea) -> pdf.IRect:
    x0, y0, x1, y1 = area.region
    width, height = pixmap.width, pixmap.height
    return pdf.IRect(
        max(0, math.floor(x0 * width) - 1),
        max(0, math.floor(y0 * height) - 1),
        min(width, math.ceil(x1 * width) + 1),
        min(height, math.ceil(y1 * height) + 1),
    )


def _audit_redaction(stage: Path, expected: list[tuple[int, int, tuple[pdf.IRect, ...]]]) -> None:
    with open_pdf(stage) as output:
        catalog = output.pdf_catalog()
        # MuPDF escreve seu próprio identificador de produtor no catálogo.
        info = output.xref_get_key(catalog, "Info")
        if (
            output.get_xml_metadata()
            or output.embfile_count()
            or output.is_form_pdf
            or output.get_ocgs()
            or output.get_toc()
            or any(output.xref_get_key(-1, key)[0] != "null" for key in ("Info", "Prev", "Encrypt"))
            or info not in (("null", "null"), ("dict", f"<</Producer(MuPDF {pdf.mupdf_version})>>"))
            or set(output.xref_get_keys(catalog)) - {"Type", "Pages", "Info"}
        ):
            raise DocForgeError("A cópia rasterizada contém estruturas inesperadas.")
        for page, (width, height, areas) in zip(output, expected, strict=True):
            images = page.get_images()
            if (
                page.get_text().strip()
                or page.get_fonts()
                or page.get_links()
                or page.first_annot
                or len(images) != 1
                or images[0][1] != 0
            ):
                raise DocForgeError("Uma página da cópia contém objetos inesperados.")
            pixmap = pdf.Pixmap(output, images[0][0])
            if (pixmap.width, pixmap.height, pixmap.n) != (width, height, 3):
                raise DocForgeError("A imagem exportada não preservou as dimensões esperadas.")
            if areas:
                samples = pixmap.samples
                stride = pixmap.stride
                for area in areas:
                    if any(
                        samples[y * stride + area.x0 * 3 : y * stride + area.x1 * 3].strip(b"\0")
                        for y in range(area.y0, area.y1)
                    ):
                        raise DocForgeError("Os pixels de uma área marcada não foram removidos.")


def redact_copy(document: pdf.Document, stage: Path, marks: list[dict], progress: Progress) -> str:
    if not 1 <= len(marks) <= MAX_REDACTION_AREAS or not 1 <= len(document) <= MAX_REDACTION_PAGES:
        raise DocForgeError("A redação aceita até 100 áreas e um PDF de até 100 páginas.")
    regions: dict[int, list[RedactionArea]] = defaultdict(list)
    for item in marks:
        area = RedactionArea(page=item["page"], region=tuple(item["region"]))
        if area.page >= len(document):
            raise DocForgeError("Uma marca de redação aponta para uma página indisponível.")
        regions[area.page].append(area)
    expected = []
    total = 0
    with pdf.open() as result:
        for index, page in enumerate(document):
            progress(index, len(document) + 1, f"Rasterizando e expurgando página {index + 1}")
            pixmap = raster(page, REDACTION_DPI)
            total += pixmap.width * pixmap.height
            if total > MAX_REDACTION_PIXELS:
                raise DocForgeError("O PDF excede o limite de 100 milhões de pixels para redação.")
            boxes = tuple(_pixel_bounds(pixmap, area) for area in regions.get(index, ()))
            for box in boxes:
                if not pixmap.set_rect(box + (pixmap.x, pixmap.y, pixmap.x, pixmap.y), (0, 0, 0)):
                    raise DocForgeError("Não foi possível expurgar uma área marcada.")
            page_copy = result.new_page(width=page.rect.width, height=page.rect.height)
            page_copy.insert_image(page_copy.rect, pixmap=pixmap, keep_proportion=False)
            expected.append((pixmap.width, pixmap.height, boxes))
        progress(len(document), len(document) + 1, "Auditando pixels e estrutura da saída")
        save_validated(result, stage, None)
    _audit_redaction(stage, expected)
    return (
        f"{len(marks)} área(s) expurgada(s) em {len(regions)} página(s)"
        " · cópia rasterizada auditada"
    )
