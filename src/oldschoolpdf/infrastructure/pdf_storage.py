"""Revisões de trabalho e validação dos PDFs antes da publicação."""

import os
import tempfile
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path

import pymupdf

from oldschoolpdf.domain.errors import OldSchoolPDFError
from oldschoolpdf.infrastructure.local_files import check_local, check_pdf, file_stamp

MAX_PAGES = 100_000
MAX_REVISIONS = 40
HISTORY_BYTES = 256 * 1024 * 1024


def open_pdf(path: Path, password: str | None = None) -> pymupdf.Document:
    check_pdf(path)
    document = pymupdf.open(path, filetype="pdf")
    try:
        if not document.is_pdf:
            raise OldSchoolPDFError("O conteúdo do arquivo não é um PDF.")
        pymupdf.mupdf.pdf_disable_js(pymupdf._as_pdf_document(document))
        if password is not None and document.is_encrypted and not document.authenticate(password):
            raise OldSchoolPDFError("O PDF de trabalho não pôde ser autenticado.")
    except Exception:
        document.close()
        raise
    return document


def has_signature(document: pymupdf.Document) -> bool:
    return (
        document.get_sigflags() > 0
        or document.xref_get_key(document.pdf_catalog(), "Perms")[0] != "null"
        or pymupdf.mupdf.pdf_count_signatures(pymupdf._as_pdf_document(document)) > 0
    )


def has_xfa(document: pymupdf.Document) -> bool:
    return document.xref_get_key(document.pdf_catalog(), "AcroForm/XFA")[0] != "null"


def ensure_signature_ack(document: pymupdf.Document, confirmed: bool) -> None:
    if not confirmed and has_signature(document):
        raise OldSchoolPDFError("Confirme o risco de invalidação da assinatura antes de continuar.")


def check_stage(path: Path) -> None:
    check_local(path)
    info = path.stat()
    if not path.is_file() or info.st_size or info.st_nlink != 1:
        raise OldSchoolPDFError("O arquivo temporário de saída mudou.")


def save_validated(
    document: pymupdf.Document, stage: Path, password: str | None, *, compact: bool = False
) -> None:
    """Mantém a proteção existente e exige que a saída possa ser reaberta."""
    try:
        check_stage(stage)
        count = document.page_count
        encryption = (document.metadata or {}).get("encryption")
        document.save(
            stage,
            encryption=pymupdf.PDF_ENCRYPT_KEEP,
            garbage=4 if compact else 1,
            deflate=True,
            use_objstms=int(compact),
        )
        with stage.open("r+b") as stream:
            os.fsync(stream.fileno())
        with open_pdf(stage, password) as result:
            if (
                result.is_encrypted
                or result.is_repaired
                or result.page_count != count
                or (result.metadata or {}).get("encryption") != encryption
            ):
                raise OldSchoolPDFError("A validação da saída não confirmou páginas e proteção.")
            for page in {0, count - 1}:
                result.load_page(page)
    except (OSError, RuntimeError, ValueError):
        raise OldSchoolPDFError("Não foi possível gravar ou validar o PDF temporário.") from None


@dataclass(frozen=True, slots=True)
class Revision:
    serial: int
    path: Path
    page: int
    size: int = 0


class PdfHistory:
    def __init__(self, origin: Path) -> None:
        self.origin = origin
        self.original_stamp = file_stamp(origin)
        self.revisions = [Revision(0, origin, 0)]
        self.position = 0
        self.serial = 0

    @property
    def current(self) -> Revision:
        return self.revisions[self.position]

    def read(self, revision: Revision, password: str | None) -> pymupdf.Document:
        if revision.serial == 0:
            check_local(self.origin)
            if file_stamp(self.origin) != self.original_stamp:
                raise OldSchoolPDFError(
                    "O PDF de base mudou fora do Old School PDF. Abra-o novamente."
                )
        return open_pdf(revision.path, password)

    def add(
        self, document: pymupdf.Document, scratch: str, password: str | None, page: int
    ) -> pymupdf.Document:
        folder = Path(scratch)
        check_local(folder)
        descriptor, name = tempfile.mkstemp(prefix="revision-", suffix=".pdf", dir=folder)
        os.close(descriptor)
        path = Path(name)
        try:
            save_validated(document, path, password)
            size = path.stat().st_size
            verified = open_pdf(path, password)
        except Exception:
            path.unlink(missing_ok=True)
            raise
        self.serial += 1
        self._drop(self.revisions[self.position + 1 :])
        del self.revisions[self.position + 1 :]
        self.revisions.append(Revision(self.serial, path, page, size))
        while len(self.revisions) > 2 and (
            len(self.revisions) > MAX_REVISIONS
            or sum(item.size for item in self.revisions[:-2]) > HISTORY_BYTES
        ):
            self._drop([self.revisions.pop(0)])
        self.position = len(self.revisions) - 1
        return verified

    @staticmethod
    def _drop(revisions: list[Revision]) -> None:
        for revision in revisions:
            if revision.serial:
                with suppress(OSError):
                    revision.path.unlink(missing_ok=True)

    def step(self, direction: int, password: str | None) -> pymupdf.Document:
        target = self.position + direction
        if direction not in (-1, 1) or not 0 <= target < len(self.revisions):
            raise OldSchoolPDFError("Não há uma revisão nessa direção.")
        verified = self.read(self.revisions[target], password)
        self.position = target
        return verified


def inspect_inputs(paths: list[str]) -> dict:
    items = []
    total = 0
    for raw in paths:
        path = Path(raw)
        try:
            with open_pdf(path) as document:
                if document.is_encrypted or (document.metadata or {}).get("encryption"):
                    raise OldSchoolPDFError("Use PDFs sem criptografia na mesclagem.")
                count = document.page_count
                if not 0 < count <= MAX_PAGES:
                    raise OldSchoolPDFError("Um dos PDFs tem uma contagem de páginas incompatível.")
                total += count
                items.append(
                    {"pages": count, "signed": has_signature(document), "stamp": file_stamp(path)}
                )
        except (OSError, RuntimeError, ValueError):
            raise OldSchoolPDFError("Um dos PDFs de entrada não pôde ser lido.") from None
    if total > MAX_PAGES:
        raise OldSchoolPDFError("A mesclagem excede o limite de 100 mil páginas.")
    return {"items": items}


def merge(inputs: list[dict], stage: str, confirmed: bool) -> dict:
    if len(inputs) < 2:
        raise OldSchoolPDFError("Adicione ao menos dois PDFs para mesclar.")
    with pymupdf.open() as result:
        for item in inputs:
            path = Path(item["path"])
            with open_pdf(path) as document:
                if file_stamp(path) != tuple(item["stamp"]):
                    raise OldSchoolPDFError("Um PDF de entrada mudou. Revise novamente a prévia.")
                if document.is_encrypted or (document.metadata or {}).get("encryption"):
                    raise OldSchoolPDFError("Use PDFs sem criptografia na mesclagem.")
                ensure_signature_ack(document, confirmed)
                if result.page_count + document.page_count > MAX_PAGES:
                    raise OldSchoolPDFError("A mesclagem excede o limite de 100 mil páginas.")
                result.insert_pdf(document, links=True, annots=True, widgets=True)
        save_validated(result, Path(stage), None)
        return {"page_count": result.page_count}
